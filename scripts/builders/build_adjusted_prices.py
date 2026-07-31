"""
Build adjusted close prices from raw price_close observations + CorporateAction records.

Reads:
  - data/processed/observations.jsonl      (raw price_close + Yahoo price_close_adj)
  - data/processed/corporate_actions.jsonl (corp actions from fetch_corp_actions.py)

Writes:
  - data/processed/observations.jsonl      (upserted with InvestorLens-computed
                                            price_close_adj observations)

The InvestorLens adjusted prices have a DISTINCT provenance (source="investorlens",
extraction_method="derived") from Yahoo's adjclose (source="yahoo",
extraction_method="official_api"). Both coexist in observations.jsonl so Phase 4
can cross-validate them.

Idempotent: re-running with the same inputs produces byte-identical output.

Usage:
    python scripts/builders/build_adjusted_prices.py
    python scripts/builders/build_adjusted_prices.py --retrieved-at 2024-09-30T18:30:00Z
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

from investorlens.builders import build_adjusted_prices  # noqa: E402
from investorlens.io import read_jsonl, upsert_records  # noqa: E402
from investorlens.models import CorporateAction, Observation, Provenance  # noqa: E402

log = logging.getLogger("build_adjusted_prices")

OBS_PATH = ROOT / "data" / "processed" / "observations.jsonl"
CA_PATH = ROOT / "data" / "processed" / "corporate_actions.jsonl"


def _load_observations() -> list[Observation]:
    if not OBS_PATH.exists():
        log.warning("Observations file not found: %s", OBS_PATH)
        return []
    raw = read_jsonl(OBS_PATH)
    out: list[Observation] = []
    for i, row in enumerate(raw):
        try:
            # Provenance may be missing in malformed rows; synthesize if so.
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown",
                    notes=f"synthesized during build (obs row {i})",
                ).model_dump(mode="json")
            out.append(Observation(**row))
        except Exception as e:
            log.warning("Failed to load observation row %d: %s — %s", i, e, json.dumps(row)[:200])
    try:
        rel = str(OBS_PATH.relative_to(ROOT))
    except ValueError:
        rel = str(OBS_PATH)
    log.info("Loaded %d observations from %s", len(out), rel)
    return out


def _load_corp_actions() -> list[CorporateAction]:
    if not CA_PATH.exists():
        log.warning("Corp actions file not found: %s", CA_PATH)
        return []
    raw = read_jsonl(CA_PATH)
    out: list[CorporateAction] = []
    for i, row in enumerate(raw):
        try:
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown",
                    notes=f"synthesized during build (ca row {i})",
                ).model_dump(mode="json")
            out.append(CorporateAction(**row))
        except Exception as e:
            log.warning("Failed to load corp action row %d: %s — %s", i, e, json.dumps(row)[:200])
    try:
        rel = str(CA_PATH.relative_to(ROOT))
    except ValueError:
        rel = str(CA_PATH)
    log.info("Loaded %d corp actions from %s", len(out), rel)
    return out


def build(retrieved_at: datetime | None = None) -> int:
    observations = _load_observations()
    corp_actions = _load_corp_actions()

    if not observations:
        log.error("No observations found. Run fetchers first.")
        return 1
    if not corp_actions:
        log.warning("No corp actions found. Adjusted prices will equal raw prices (factor=1, no dividend adj).")

    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    log.info("Building adjusted prices...")
    adj = build_adjusted_prices(
        price_observations=observations,
        corp_actions=corp_actions,
        retrieved_at=retrieved_at,
    )
    log.info("Built %d adjusted-price observations", len(adj))

    if not adj:
        log.warning("Builder produced 0 observations — possibly no price_close observations in input.")
        return 1

    payload = [o.model_dump(mode="json", exclude_none=True) for o in adj]
    stats = upsert_records(OBS_PATH, payload, key="id")
    try:
        out_rel = str(OBS_PATH.relative_to(ROOT))
    except ValueError:
        out_rel = str(OBS_PATH)
    log.info(
        "Upserted to %s: inserted=%d updated=%d total=%d",
        out_rel,
        stats["inserted"],
        stats["updated"],
        stats["total"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retrieved-at",
        type=str,
        default=None,
        help="ISO-8601 UTC timestamp for provenance. Defaults to now().",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
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

    return build(retrieved_at=retrieved_at)


if __name__ == "__main__":
    sys.exit(main())
