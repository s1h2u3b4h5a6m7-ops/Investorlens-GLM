"""
Fetch BSE's List of Securities — the canonical list of all listed securities
on BSE (formerly Bombay Stock Exchange).

Source: https://www.bseindia.com/corporates/List_Scrips.aspx

BSE's site requires a form submission (POST with parameters like segment,
status, etc.). For simplicity, we use the bulk download endpoint that returns
the full CSV in one shot. If BSE changes the endpoint, only this URL needs
updating — the parser is independent.

Output: data/master/bse_scrips.jsonl  (one ISINMaster record per row)

Idempotent: re-running on the same date reads from cache, and upserts with
no duplicates if the data hasn't changed.

Usage:
    python scripts/fetchers/fetch_bse_equities_list.py
    python scripts/fetchers/fetch_bse_equities_list.py --date 2024-09-30
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
from investorlens.parsers import bse  # noqa: E402

log = logging.getLogger("fetch_bse_scrips")

# BSE's List_Scrips page exposes a "Download" CSV. The exact endpoint has varied
# historically; this URL targets the active securities CSV.
# If it changes, update ONLY this constant — the parser is URL-agnostic.
URL = "https://www.bseindia.com/corporates/List_Scrips.aspx"
DOWNLOAD_URL = "https://www.bseindia.com/markets/equity/EQReports/EquityArchive.aspx"

OUTPUT_PATH = ROOT / "data" / "master" / "bse_scrips.jsonl"


def fetch(date_str: str | None = None) -> int:
    """Fetch and parse BSE's securities list, upserting into the JSONL output.

    Returns 0 on success, 1 on fetch failure (errors are logged, not raised,
    so the daily pipeline can continue with other sources).
    """
    log.info("Fetching BSE securities list")
    try:
        with CachedSession(
            source_slug="bse",
            rate_limit_per_sec=1.0,
            max_retries=3,
            extra_headers={
                "Referer": "https://www.bseindia.com/corporates/List_Scrips.aspx",
            },
        ) as session:
            # Try the page first to establish cookies; then the CSV endpoint.
            try:
                session.get_text(URL, date_str=date_str, use_cache=True)
            except FetchError as e:
                log.warning("Could not load BSE list page (continuing to CSV): %s", e)
            csv_text = session.get_text(DOWNLOAD_URL, date_str=date_str)
    except FetchError as e:
        log.error("BSE fetch failed: %s", e)
        return 1

    log.info("Parsing %d bytes of BSE CSV", len(csv_text))
    retrieved_at = datetime.now(timezone.utc)
    records = bse.parse_list_scrips_csv(csv_text, retrieved_at=retrieved_at)
    log.info("Parsed %d BSE scrip records", len(records))

    if not records:
        log.warning("BSE fetch returned 0 records — site may have changed layout.")
        return 1

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
