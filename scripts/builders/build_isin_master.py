"""
Build the canonical ISIN master by merging NSE and BSE records.

Reads:
  - data/master/nse_equities.jsonl   (output of fetch_nse_equities_list.py)
  - data/master/bse_scrips.jsonl     (output of fetch_bse_equities_list.py)

Writes:
  - data/master/isin_master.jsonl    (canonical, merged, one row per ISIN)

Idempotent: re-running with the same inputs produces byte-identical output.

Usage:
    python scripts/builders/build_isin_master.py
    python scripts/builders/build_isin_master.py --check   # dry-run; report stats only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.builders import build_isin_master  # noqa: E402
from investorlens.io import read_jsonl, upsert_records  # noqa: E402
from investorlens.models import ISINMaster, Provenance  # noqa: E402

log = logging.getLogger("build_isin_master")

NSE_PATH = ROOT / "data" / "master" / "nse_equities.jsonl"
BSE_PATH = ROOT / "data" / "master" / "bse_scrips.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "isin_master.jsonl"


def _load_records(path: Path, source_label: str) -> list[ISINMaster]:
    """Load JSONL records from disk, rehydrating them as ISINMaster Pydantic models.

    Provenance is preserved as-is from the fetcher; if the JSONL has a slightly
    different shape (e.g. source_url was None and stripped), Provenance defaults
    fill in sensibly.
    """
    if not path.exists():
        log.warning("%s file not found: %s — treating as empty", source_label, path)
        return []

    raw = read_jsonl(path)
    records: list[ISINMaster] = []
    for i, row in enumerate(raw):
        try:
            # Provenance is required by the model; if missing from a malformed
            # row, synthesize a low-confidence one with a clear note.
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source=source_label.lower(),
                    notes=f"synthesized during build (row {i} of {source_label})",
                ).model_dump(mode="json")
            records.append(ISINMaster(**row))
        except Exception as e:
            log.error("Failed to load %s row %d: %s — %s", source_label, i, e, json.dumps(row)[:300])
    log.info("Loaded %d records from %s", len(records), path.relative_to(ROOT))
    return records


def build(check_only: bool = False, retrieved_at: datetime | None = None) -> int:
    """Build the canonical ISIN master.

    Args:
        check_only: if True, don't write the output file; just report stats.
        retrieved_at: optional timestamp to attach to merged records' provenance.
            Defaults to now(UTC). Useful for tests/dev to get byte-identical output.
    """
    nse_records = _load_records(NSE_PATH, "NSE")
    bse_records = _load_records(BSE_PATH, "BSE")

    if not nse_records and not bse_records:
        log.error("No input records found. Run fetchers first.")
        return 1

    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)
    merged = build_isin_master(nse_records, bse_records, retrieved_at=retrieved_at)

    # Stats for visibility.
    n_only = sum(1 for r in merged if r.exchange == "NSE")
    b_only = sum(1 for r in merged if r.exchange == "BSE")
    both = sum(1 for r in merged if r.exchange == "NSE+BSE")
    log.info(
        "ISIN master: total=%d  NSE-only=%d  BSE-only=%d  NSE+BSE=%d",
        len(merged),
        n_only,
        b_only,
        both,
    )

    payload = [r.model_dump(mode="json", exclude_none=True) for r in merged]
    if check_only:
        log.info("Check-only mode — no file written.")
        return 0

    stats = upsert_records(OUTPUT_PATH, payload, key="id")
    log.info(
        "Wrote %s: inserted=%d updated=%d total=%d",
        OUTPUT_PATH.relative_to(ROOT),
        stats["inserted"],
        stats["updated"],
        stats["total"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run: report stats without writing the output file.",
    )
    parser.add_argument(
        "--retrieved-at",
        type=str,
        default=None,
        help="ISO-8601 UTC timestamp for provenance. Defaults to now(). Useful for byte-identical re-runs.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    retrieved_at = None
    if args.retrieved_at:
        retrieved_at = datetime.fromisoformat(args.retrieved_at)
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)

    return build(check_only=args.check, retrieved_at=retrieved_at)


if __name__ == "__main__":
    sys.exit(main())
