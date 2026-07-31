"""
Seed observations.jsonl from bhavcopy test fixtures.

DEV UTILITY — pre-populates data/raw/nse/bhavcopy/2024-09-30.zip with a real
zip built from the test fixture, then runs the standard fetch_bhavcopy.fetch().
Useful for verifying the pipeline end-to-end when live fetching is blocked.

Usage:
    python scripts/seed_bhavcopy_from_fixtures.py
"""

from __future__ import annotations

import io
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Import the fetcher module by path
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "fetch_bhavcopy",
    ROOT / "scripts" / "fetchers" / "fetch_bhavcopy.py",
)
assert _spec is not None and _spec.loader is not None
fetch_bhavcopy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_bhavcopy)

FIXTURE = ROOT / "tests" / "fixtures" / "bhavcopy_modern.csv"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("seed_bhavcopy")
    log.warning("SEED MODE: using test fixtures, NOT live data.")
    log.warning("For production use, run scripts/fetchers/fetch_bhavcopy.py --date <YYYY-MM-DD> instead.")

    if not FIXTURE.exists():
        log.error("Fixture missing: %s", FIXTURE)
        return 1

    trade_date = date(2024, 9, 30)
    raw_path = fetch_bhavcopy.RAW_DIR / f"{trade_date.isoformat()}.zip"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    if raw_path.exists():
        log.info("Cached zip already exists at %s — removing to rebuild from fixture.", raw_path)
        raw_path.unlink()

    # Build a real zip from the fixture CSV.
    csv_text = FIXTURE.read_text(encoding="utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("BhavCopy_NSE_CM_0_0_20240930_F_0000.csv", csv_text)
    raw_path.write_bytes(buf.getvalue())
    log.info("Wrote fake bhavcopy zip from fixture (%d bytes)", len(buf.getvalue()))

    # Run the standard fetcher; it will find the cached zip and skip the network.
    rc = fetch_bhavcopy.fetch(trade_date)
    if rc != 0:
        log.error("Fetch returned %d", rc)
        return rc

    log.info("Done. Observations written to data/processed/observations.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
