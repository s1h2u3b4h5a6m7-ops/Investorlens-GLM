"""
Fetch NSE's EQUITY_L.csv — the canonical list of all currently-listed equity
symbols on the National Stock Exchange of India.

Source URL: https://archives.nseindia.com/content/equities/EQUITY_L.csv

Output: data/master/nse_equities.jsonl  (one ISINMaster record per row)

Idempotent: re-running on the same date reads from cache (no HTTP), and
upserts with no duplicates if the data hasn't changed.

Usage:
    python scripts/fetchers/fetch_nse_equities_list.py
    python scripts/fetchers/fetch_nse_equities_list.py --date 2024-09-30
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import CachedSession, FetchError, upsert_records  # noqa: E402
from investorlens.parsers import nse  # noqa: E402

log = logging.getLogger("fetch_nse_equities")

URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
OUTPUT_PATH = ROOT / "data" / "master" / "nse_equities.jsonl"


def fetch(date_str: str | None = None) -> int:
    """Fetch and parse NSE EQUITY_L.csv, upserting into the JSONL output.

    Returns the number of records upserted.
    """
    log.info("Fetching NSE EQUITY_L.csv from %s", URL)
    try:
        with CachedSession(
            source_slug="nse",
            rate_limit_per_sec=1.0,  # NSE is strict; be very polite
            max_retries=3,
        ) as session:
            csv_text = session.get_text(URL, date_str=date_str)
    except FetchError as e:
        log.error("Fetch failed: %s", e)
        return 1

    log.info("Parsing %d bytes of CSV", len(csv_text))
    retrieved_at = datetime.now(timezone.utc)
    records = nse.parse_equity_l_csv(csv_text, retrieved_at=retrieved_at)
    log.info("Parsed %d NSE equity records", len(records))

    # Serialize to plain dicts for upsert (Pydantic v2 model_dump).
    payload = [r.model_dump(mode="json", exclude_none=True) for r in records]

    stats = upsert_records(OUTPUT_PATH, payload, key="id")
    log.info(
        "Upserted to %s: inserted=%d updated=%d total=%d",
        OUTPUT_PATH.relative_to(ROOT),
        stats["inserted"],
        stats["updated"],
        stats["total"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date string (YYYY-MM-DD) for cache keying. Defaults to today (UTC).",
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

    return fetch(date_str=args.date)


if __name__ == "__main__":
    sys.exit(main())
