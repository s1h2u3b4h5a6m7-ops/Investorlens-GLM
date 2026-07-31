"""
Seed macro observations (RBI rates + FX + MOSPI CPI) from test fixtures.

DEV UTILITY — pre-populates the raw cache directories with the test fixtures,
then runs each of the three macro fetchers. Useful for verifying the macro
pipeline end-to-end when live fetching is blocked (RBI returns error pages
to cloud IPs in this sandbox; MOSPI may also block).

Usage:
    python scripts/seed_macro_from_fixtures.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import importlib.util

_spec_rates = importlib.util.spec_from_file_location(
    "fetch_rbi_rates", ROOT / "scripts" / "fetchers" / "fetch_rbi_rates.py"
)
assert _spec_rates is not None and _spec_rates.loader is not None
fetch_rbi_rates = importlib.util.module_from_spec(_spec_rates)
_spec_rates.loader.exec_module(fetch_rbi_rates)

_spec_fx = importlib.util.spec_from_file_location(
    "fetch_rbi_fx", ROOT / "scripts" / "fetchers" / "fetch_rbi_fx.py"
)
assert _spec_fx is not None and _spec_fx.loader is not None
fetch_rbi_fx = importlib.util.module_from_spec(_spec_fx)
_spec_fx.loader.exec_module(fetch_rbi_fx)

_spec_cpi = importlib.util.spec_from_file_location(
    "fetch_mospi_cpi", ROOT / "scripts" / "fetchers" / "fetch_mospi_cpi.py"
)
assert _spec_cpi is not None and _spec_cpi.loader is not None
fetch_mospi_cpi = importlib.util.module_from_spec(_spec_cpi)
_spec_cpi.loader.exec_module(fetch_mospi_cpi)

FIXTURES = ROOT / "tests" / "fixtures"


def _seed_one(name: str, fetcher_module, fixture_name: str, date_str: str, ext: str) -> int:
    log = logging.getLogger("seed_macro")
    cache_dir = fetcher_module.RAW_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{date_str}.{ext}"

    if not cache_path.exists():
        cache_path.write_text((FIXTURES / fixture_name).read_text(encoding="utf-8"), encoding="utf-8")
        log.info("[%s] Pre-populated cache: %s", name, cache_path)
    else:
        log.info("[%s] Cache already present: %s", name, cache_path)

    # Patch datetime to fixed_ts for byte-identical re-runs.
    fixed_ts = datetime(2024, 10, 9, 13, 30, tzinfo=timezone.utc)
    original_dt = fetcher_module.datetime

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_ts if tz is not None else fixed_ts.replace(tzinfo=None)

    try:
        fetcher_module.datetime = _FrozenDatetime  # type: ignore[assignment]
        rc = fetcher_module.fetch(date_str=date_str)
    finally:
        fetcher_module.datetime = original_dt  # type: ignore[assignment]
    return rc


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("seed_macro")
    log.warning("SEED MODE: using test fixtures, NOT live data.")
    log.warning("For production use, run the individual fetchers instead.")

    # 1. RBI Policy Rates (use fixture date 2024-10-09)
    rc = _seed_one("RBI rates", fetch_rbi_rates, "rbi_policy_rates.html", "2024-10-09", "html")
    if rc != 0:
        log.error("RBI rates fetch returned %d", rc)
        return rc

    # 2. RBI FX Reference Rates (same date)
    rc = _seed_one("RBI FX", fetch_rbi_fx, "rbi_fx_reference.html", "2024-10-09", "html")
    if rc != 0:
        log.error("RBI FX fetch returned %d", rc)
        return rc

    # 3. MOSPI CPI (use fixture date 2024-10-14)
    rc = _seed_one("MOSPI CPI", fetch_mospi_cpi, "mospi_cpi.csv", "2024-10-14", "csv")
    if rc != 0:
        log.error("MOSPI CPI fetch returned %d", rc)
        return rc

    log.info("Done. Macro observations upserted to data/processed/observations.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
