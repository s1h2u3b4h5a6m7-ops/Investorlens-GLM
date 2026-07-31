"""
Seed the ISIN master pipeline from test fixtures.

This is a DEVELOPMENT utility — useful for verifying the pipeline end-to-end
when live NSE/BSE fetching is blocked (e.g. by CDN/WAF in sandbox environments).

It:
  1. Reads tests/fixtures/nse_equity_l.csv and tests/fixtures/bse_scrips.csv
  2. Parses them with the production parsers
  3. Writes the parsed records to data/master/nse_equities.jsonl and bse_scrips.jsonl
  4. Then runs the standard build_isin_master.py flow

The result is a small (15-row) canonical ISIN master at data/master/isin_master.jsonl
that exercises every code path in the pipeline.

Usage:
    python scripts/seed_isin_master_from_fixtures.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import upsert_records  # noqa: E402
from investorlens.parsers import bse, nse  # noqa: E402

log = logging.getLogger("seed_isin_master")

FIXTURES = ROOT / "tests" / "fixtures"
NSE_FIXTURE = FIXTURES / "nse_equity_l.csv"
BSE_FIXTURE = FIXTURES / "bse_scrips.csv"

NSE_OUT = ROOT / "data" / "master" / "nse_equities.jsonl"
BSE_OUT = ROOT / "data" / "master" / "bse_scrips.jsonl"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log.warning("SEED MODE: using test fixtures, NOT live data.")
    log.warning("For production use, run scripts/fetchers/fetch_nse_equities_list.py instead.")

    if not NSE_FIXTURE.exists() or not BSE_FIXTURE.exists():
        log.error("Fixtures missing: %s, %s", NSE_FIXTURE, BSE_FIXTURE)
        return 1

    # Use a FIXED timestamp for seed mode so re-runs produce truly byte-identical
    # output. (Live fetchers use the real `now()` because re-fetching is real.)
    # The date is deliberately the project start date — fixture data, not "today".
    retrieved_at = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)

    # 1. Parse fixtures.
    nse_records = nse.parse_equity_l_csv(NSE_FIXTURE.read_text(encoding="utf-8"), retrieved_at=retrieved_at)
    bse_records = bse.parse_list_scrips_csv(BSE_FIXTURE.read_text(encoding="utf-8"), retrieved_at=retrieved_at)
    log.info("Parsed %d NSE records and %d BSE records from fixtures", len(nse_records), len(bse_records))

    # 2. Serialize to JSONL — same shape the live fetchers produce.
    nse_payload = [r.model_dump(mode="json", exclude_none=True) for r in nse_records]
    bse_payload = [r.model_dump(mode="json", exclude_none=True) for r in bse_records]

    # 3. Write to data/master/.
    nse_stats = upsert_records(NSE_OUT, nse_payload, key="id")
    bse_stats = upsert_records(BSE_OUT, bse_payload, key="id")
    log.info("NSE JSONL: %s", nse_stats)
    log.info("BSE JSONL: %s", bse_stats)

    # 4. Run the standard builder with the SAME fixed timestamp so the merged
    # records' provenance is also deterministic across runs.
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "builders" / "build_isin_master.py"),
            "--retrieved-at",
            retrieved_at.isoformat(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    log.info("Done. ISIN master at: data/master/isin_master.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
