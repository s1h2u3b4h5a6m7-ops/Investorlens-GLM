"""
Seed historical price observations from Yahoo chart API fixture.

DEV UTILITY — uses the test fixture as the Yahoo response, bypassing all HTTP.
Useful for verifying the historical-prices pipeline end-to-end when live
fetching is blocked (Yahoo rate-limits this sandbox).

This script:
  1. Builds a small ISIN master with RELIANCE (if not present)
  2. Patches YahooChartClient to return the test fixture
  3. Runs the standard fetch_hist_prices.fetch() pipeline
  4. Verifies 30 observations (5 days × 6 kinds) are upserted

Usage:
    python scripts/seed_hist_prices_from_fixtures.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Import the fetcher by path
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "fetch_hist_prices",
    ROOT / "scripts" / "fetchers" / "fetch_hist_prices.py",
)
assert _spec is not None and _spec.loader is not None
fetch_hist_prices = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_hist_prices)

FIXTURE = ROOT / "tests" / "fixtures" / "yahoo_chart_reliance_5d.json"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("seed_hist_prices")
    log.warning("SEED MODE: using Yahoo chart fixture, NOT live data.")
    log.warning("For production use, run scripts/fetchers/fetch_hist_prices.py --symbols <X> instead.")

    if not FIXTURE.exists():
        log.error("Fixture missing: %s", FIXTURE)
        return 1

    chart_response = json.loads(FIXTURE.read_text(encoding="utf-8"))

    # Patch YahooChartClient.get_chart to return the fixture for any symbol.
    def fake_get_chart(self, symbol, *, interval="1d", range_="5d", period1=None, period2=None, use_cache=True):
        return json.loads(json.dumps(chart_response))
    from investorlens.io.yahoo import YahooChartClient
    YahooChartClient.get_chart = fake_get_chart  # type: ignore[assignment]

    # Run the fetcher using the existing ISIN master (built in Milestone 1.1).
    rc = fetch_hist_prices.fetch(
        symbols=["RELIANCE"],
        incremental=True,
    )
    if rc != 0:
        log.error("Fetch returned %d", rc)
        return rc

    log.info("Done. Observations upserted to data/processed/observations.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
