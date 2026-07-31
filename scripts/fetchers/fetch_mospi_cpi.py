"""
Fetch MOSPI Consumer Price Index (CPI) monthly release.

Source: https://mospi.gov.in/web/mospi/cpi-publications
MOSPI publishes the CPI as an Excel file. We model the CSV shape we'd extract
from the .xlsx — the parser handles the CSV directly, so the fetcher can be
adapted to either download the .xlsx and convert to CSV, or fetch a pre-built
CSV mirror.

For now, the fetcher downloads the configured URL (defaults to a placeholder)
and parses the resulting CSV. The exact URL must be confirmed against the
current MOSPI publication page; the parser is URL-agnostic.

Output:
  - Raw CSV cached to: data/raw/mospi/cpi/<YYYY-MM-DD>.csv
  - Parsed Observations upserted to: data/processed/observations.jsonl

Each (year, month, indicator) becomes a single Observation. YoY %s use
kind=CPI_YOY; raw indices use kind=OTHER. The subject_id is a `drv_cpi_*`
ID (macro driver).

Idempotent: re-running on the same date reads from cache, upserts with no
duplicates.

Usage:
    python scripts/fetchers/fetch_mospi_cpi.py
    python scripts/fetchers/fetch_mospi_cpi.py --date 2024-10-14
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
from investorlens.parsers import mospi  # noqa: E402

log = logging.getLogger("fetch_mospi_cpi")

# NOTE: MOSPI's actual CPI download URL changes with each monthly release.
# The fetcher is URL-agnostic — update this constant when wiring up the live
# pipeline. For now, point at the publications index page; a future task
# can implement an URL discovery step (the page links to the latest release).
URL = "https://mospi.gov.in/web/mospi/cpi-publications"
OUTPUT_PATH = ROOT / "data" / "processed" / "observations.jsonl"
RAW_DIR = ROOT / "data" / "raw" / "mospi" / "cpi"


def fetch(date_str: str | None = None, csv_url: str | None = None) -> int:
    """Fetch and parse MOSPI CPI CSV, upserting to observations.jsonl.

    Args:
        date_str: YYYY-MM-DD for cache keying. Defaults to today.
        csv_url: override the URL to fetch (useful for testing with a specific
            monthly release URL). Defaults to the publications page URL.
    """
    retrieved_at = datetime.now(timezone.utc)
    date_str = date_str or retrieved_at.strftime("%Y-%m-%d")
    raw_path = RAW_DIR / f"{date_str}.csv"
    target_url = csv_url or URL

    csv_text: str | None = None
    if raw_path.exists():
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Reading cached CSV: %s", rel)
        csv_text = raw_path.read_text(encoding="utf-8", errors="replace")
    else:
        log.info("Fetching MOSPI CPI from %s", target_url)
        try:
            with CachedSession(
                source_slug="mospi",
                rate_limit_per_sec=1.0,
                max_retries=3,
            ) as session:
                body = session.get(target_url, date_str=date_str)
                csv_text = body.decode("utf-8", errors="replace")
        except FetchError as e:
            log.error("Fetch failed: %s", e)
            return 1

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = raw_path.with_suffix(".csv.tmp")
        tmp.write_text(csv_text, encoding="utf-8")
        tmp.replace(raw_path)
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Cached CSV to %s", rel)

    log.info("Parsing %d bytes of CSV", len(csv_text))
    observations = mospi.parse_cpi_csv(
        csv_text,
        retrieved_at=retrieved_at,
        source_url=target_url,
    )
    log.info("Parsed %d CPI observations", len(observations))

    if not observations:
        log.warning("Parser produced 0 observations — possibly CSV format changed.")
        return 1

    payload = [o.model_dump(mode="json", exclude_none=True) for o in observations]
    stats = upsert_records(OUTPUT_PATH, payload, key="id")
    try:
        out_rel = str(OUTPUT_PATH.relative_to(ROOT))
    except ValueError:
        out_rel = str(OUTPUT_PATH)
    log.info(
        "Upserted to %s: inserted=%d updated=%d total=%d",
        out_rel, stats["inserted"], stats["updated"], stats["total"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD for cache keying. Defaults to today.")
    parser.add_argument("--url", type=str, default=None, help="Override the CSV URL (for specific monthly releases).")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return fetch(date_str=args.date, csv_url=args.url)


if __name__ == "__main__":
    sys.exit(main())
