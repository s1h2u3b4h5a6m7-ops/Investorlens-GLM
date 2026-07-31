"""
Fetch NSE Equity bhavcopy for a given trading day.

The bhavcopy is a ZIP file containing a CSV with one row per (symbol, series)
traded that day. Each row gives OHLC, volume, turnover, and ISIN.

Source URLs:
  Modern (late 2024 onwards):
    https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_YYYYMMDD_F_0000.csv.zip
  Legacy (pre-2024):
    https://archives.nseindia.com/content/equities/cm<DDMMMYYYY>bhav.csv.zip

Output:
  - Raw zip cached to: data/raw/nse/bhavcopy/<YYYY-MM-DD>.zip
  - Parsed Observations upserted to: data/processed/observations.jsonl

Idempotent: re-running on the same date reads the cached zip from disk (no
HTTP) and upserts with no duplicate observations.

Usage:
    python scripts/fetchers/fetch_bhavcopy.py                    # today (IST)
    python scripts/fetchers/fetch_bhavcopy.py --date 2024-09-30
    python scripts/fetchers/fetch_bhavcopy.py --date 2024-09-30 --only-isins INE002A01018,INE467B01029
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import CachedSession, FetchError, upsert_records  # noqa: E402
from investorlens.parsers import bhavcopy  # noqa: E402

log = logging.getLogger("fetch_bhavcopy")

OUTPUT_PATH = ROOT / "data" / "processed" / "observations.jsonl"
RAW_DIR = ROOT / "data" / "raw" / "nse" / "bhavcopy"

# IST is UTC+5:30. NSE market closes at 15:30 IST; bhavcopy is published ~16:00 IST.
_IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> date:
    return datetime.now(_IST_OFFSET).date()


def _build_urls(trade_date: date) -> list[str]:
    """Build candidate URLs for the given trade date. Try modern first, then legacy."""
    yyyymmdd = trade_date.strftime("%Y%m%d")
    ddmmmmyyyy = trade_date.strftime("%d%b%Y").upper()
    return [
        # Modern UDiFF format
        f"https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_{yyyymmdd}_F_0000.csv.zip",
        # Legacy format
        f"https://archives.nseindia.com/content/equities/cm{ddmmmmyyyy}bhav.csv.zip",
    ]


def _extract_csv_from_zip(zip_bytes: bytes) -> str:
    """Extract the largest CSV from a bhavcopy zip file.

    The modern NSE zip contains one CSV. The legacy zip also contains one CSV
    but sometimes has a metadata file alongside. Picking the largest CSV is
    a robust heuristic that works for both.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise FetchError(f"No CSV files found in bhavcopy zip; contents: {zf.namelist()}")
        # Pick the largest CSV (the equity bhavcopy is much larger than metadata sidecars).
        largest = max(csv_names, key=lambda n: zf.getinfo(n).file_size)
        log.info("Extracting %s (%d bytes) from zip", largest, zf.getinfo(largest).file_size)
        return zf.read(largest).decode("utf-8", errors="replace")


def fetch(
    trade_date: date,
    *,
    only_isins: set[str] | None = None,
) -> int:
    """Fetch and parse the bhavcopy for `trade_date`, upserting observations.

    Returns 0 on success, 1 on failure.
    """
    raw_path = RAW_DIR / f"{trade_date.isoformat()}.zip"

    # 1. Get the zip bytes (from cache or HTTP).
    zip_bytes: bytes | None = None
    if raw_path.exists():
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Reading cached zip: %s", rel)
        zip_bytes = raw_path.read_bytes()
    else:
        log.info("Fetching bhavcopy for %s", trade_date.isoformat())
        urls = _build_urls(trade_date)
        with CachedSession(
            source_slug="nse",
            rate_limit_per_sec=1.0,
            max_retries=3,
        ) as session:
            for url in urls:
                try:
                    zip_bytes = session.get(url, use_cache=True)
                    log.info("Got zip from %s (%d bytes)", url, len(zip_bytes))
                    break
                except FetchError as e:
                    log.warning("Failed %s: %s", url, e)
                    continue
        if zip_bytes is None:
            log.error("All bhavcopy URLs failed for %s", trade_date.isoformat())
            return 1

        # Cache the raw zip for future runs.
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = raw_path.with_suffix(".zip.tmp")
        tmp.write_bytes(zip_bytes)
        tmp.replace(raw_path)
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Cached zip to %s", rel)

    # 2. Extract the CSV.
    try:
        csv_text = _extract_csv_from_zip(zip_bytes)
    except (FetchError, zipfile.BadZipFile) as e:
        log.error("Failed to extract CSV from zip: %s", e)
        return 1

    # 3. Parse → Observations.
    retrieved_at = datetime.now(timezone.utc)
    source_url = _build_urls(trade_date)[0]  # primary URL for provenance
    observations = bhavcopy.parse_bhavcopy_csv(
        csv_text,
        retrieved_at=retrieved_at,
        source_url=source_url,
        only_isins=only_isins,
    )
    log.info(
        "Parsed %d observations from bhavcopy for %s",
        len(observations),
        trade_date.isoformat(),
    )

    if not observations:
        log.warning("Bhavcopy parser produced 0 observations — possibly a holiday or empty file.")
        return 1

    # 4. Upsert into observations.jsonl.
    payload = [o.model_dump(mode="json", exclude_none=True) for o in observations]
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
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Trade date YYYY-MM-DD (default: today IST).",
    )
    parser.add_argument(
        "--only-isins",
        type=str,
        default=None,
        help="Comma-separated ISINs to filter to (useful for testing).",
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

    trade_date = (
        date.fromisoformat(args.date) if args.date else _today_ist()
    )
    only_isins = (
        {i.strip().upper() for i in args.only_isins.split(",") if i.strip()}
        if args.only_isins
        else None
    )

    return fetch(trade_date, only_isins=only_isins)


if __name__ == "__main__":
    sys.exit(main())
