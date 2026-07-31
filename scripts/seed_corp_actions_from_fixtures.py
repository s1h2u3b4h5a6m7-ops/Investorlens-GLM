"""
Seed corporate actions + adjusted prices from test fixtures.

DEV UTILITY — pre-populates the raw CSV cache with the test fixture, then runs
the standard fetch_corp_actions.fetch() + build_adjusted_prices.build() pipeline.
Useful for verifying the corp-actions pipeline end-to-end when live fetching is
blocked (NSE CDN blocks this sandbox).

Usage:
    python scripts/seed_corp_actions_from_fixtures.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Import fetcher + builder by path
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "fetch_corp_actions", ROOT / "scripts" / "fetchers" / "fetch_corp_actions.py"
)
assert _spec is not None and _spec.loader is not None
fetch_corp_actions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_corp_actions)

_spec2 = importlib.util.spec_from_file_location(
    "build_adjusted_prices", ROOT / "scripts" / "builders" / "build_adjusted_prices.py"
)
assert _spec2 is not None and _spec2.loader is not None
build_adjusted_prices_script = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(build_adjusted_prices_script)


FIXTURE = ROOT / "tests" / "fixtures" / "nse_corpact.csv"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("seed_corp_actions")
    log.warning("SEED MODE: using test fixtures, NOT live data.")
    log.warning("For production use, run scripts/fetchers/fetch_corp_actions.py instead.")

    if not FIXTURE.exists():
        log.error("Fixture missing: %s", FIXTURE)
        return 1

    # 1. Pre-populate the cache with the fixture CSV.
    cache_path = fetch_corp_actions.RAW_DIR / "2024-09-30.csv"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        cache_path.unlink()
    cache_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    log.info("Pre-populated cache: %s", cache_path)

    # 2. Run the corp-actions fetcher (will read from cache, skip HTTP).
    rc = fetch_corp_actions.fetch(date_str="2024-09-30")
    if rc != 0:
        log.error("Corp actions fetch returned %d", rc)
        return rc

    # 3. Run the adjusted-prices builder with a fixed timestamp for determinism.
    fixed_ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)
    rc = build_adjusted_prices_script.build(retrieved_at=fixed_ts)
    if rc != 0:
        log.warning("Adjusted prices builder returned %d (this is OK if there are no price_close observations yet)", rc)

    log.info("Done. Corp actions at data/processed/corporate_actions.jsonl; adjusted prices upserted to data/processed/observations.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
