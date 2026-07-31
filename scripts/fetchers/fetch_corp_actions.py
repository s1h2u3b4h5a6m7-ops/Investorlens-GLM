"""
Fetch NSE Corporate Actions bulk CSV.

Source: https://archives.nseindia.com/corporates/CORPACT.csv

The CSV contains ALL corporate actions for ALL listed companies (splits,
bonuses, dividends, rights, mergers, etc.) — typically ~5 MB.

Output:
  - Raw CSV cached to: data/raw/nse/corpact/<YYYY-MM-DD>.csv
  - Parsed CorporateAction records upserted to: data/processed/corporate_actions.jsonl

The parser resolves NSE symbols → ISINs via the ISIN master. Symbols not in
the master are skipped (with a warning).

Idempotent: re-running on the same date reads from cache (no HTTP), upserts
with no duplicates.

Usage:
    python scripts/fetchers/fetch_corp_actions.py
    python scripts/fetchers/fetch_corp_actions.py --date 2024-09-30
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import CachedSession, FetchError, read_jsonl, upsert_records  # noqa: E402
from investorlens.parsers import corp_actions  # noqa: E402

log = logging.getLogger("fetch_corp_actions")

URL = "https://archives.nseindia.com/corporates/CORPACT.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "corporate_actions.jsonl"
ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
RAW_DIR = ROOT / "data" / "raw" / "nse" / "corpact"


def fetch(date_str: str | None = None) -> int:
    """Fetch and parse NSE corporate actions, upserting to corporate_actions.jsonl.

    Returns 0 on success, 1 on failure.
    """
    # 1. Load ISIN master for symbol → ISIN resolution.
    isin_master = []
    if ISIN_MASTER_PATH.exists():
        isin_master = read_jsonl(ISIN_MASTER_PATH)
        log.info("Loaded %d records from ISIN master.", len(isin_master))
    else:
        log.warning("ISIN master not found at %s — all corp actions will be skipped.", ISIN_MASTER_PATH)

    # 2. Get the CSV (from cache or HTTP).
    retrieved_at = datetime.now(timezone.utc)
    date_str = date_str or retrieved_at.strftime("%Y-%m-%d")
    raw_path = RAW_DIR / f"{date_str}.csv"

    csv_text: str | None = None
    if raw_path.exists():
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Reading cached CSV: %s", rel)
        csv_text = raw_path.read_text(encoding="utf-8", errors="replace")
    else:
        log.info("Fetching NSE corporate actions from %s", URL)
        try:
            with CachedSession(
                source_slug="nse",
                rate_limit_per_sec=1.0,
                max_retries=3,
            ) as session:
                body = session.get(URL, date_str=date_str)
                csv_text = body.decode("utf-8", errors="replace")
        except FetchError as e:
            log.error("Fetch failed: %s", e)
            return 1

        # Cache the raw CSV for future runs.
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = raw_path.with_suffix(".csv.tmp")
        tmp.write_text(csv_text, encoding="utf-8")
        tmp.replace(raw_path)
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Cached CSV to %s", rel)

    # 3. Parse → CorporateAction records.
    log.info("Parsing %d bytes of CSV", len(csv_text))
    records = corp_actions.parse_corpact_csv(
        csv_text,
        isin_master=isin_master,
        retrieved_at=retrieved_at,
        source_url=URL,
    )
    log.info("Parsed %d corporate action records", len(records))

    if not records:
        log.warning("Parser produced 0 records — possibly an empty CSV or all symbols missing from ISIN master.")
        return 1

    # 4. Upsert into corporate_actions.jsonl.
    payload = [r.model_dump(mode="json", exclude_none=True) for r in records]
    stats = upsert_records(OUTPUT_PATH, payload, key="id")
    try:
        out_rel = str(OUTPUT_PATH.relative_to(ROOT))
    except ValueError:
        out_rel = str(OUTPUT_PATH)
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
    parser.add_argument("--date", type=str, default=None, help="Cache date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return fetch(date_str=args.date)


if __name__ == "__main__":
    sys.exit(main())
