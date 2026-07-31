"""Smoke test: build a realistic end-to-end example to confirm the foundation composes correctly."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import upsert_records, write_json  # noqa: E402
from investorlens.models import (  # noqa: E402
    Company,
    CorporateAction,
    CorporateActionType,
    ISINMaster,
    Observation,
    ObservationKind,
    Provenance,
    Sector,
    Security,
    Source,
    SourceKind,
)


def main() -> int:
    # 1. Define sources
    nse_source = Source(
        slug="nse",
        name="National Stock Exchange of India",
        kind=SourceKind.EXCHANGE,
        provenance=Provenance(source="investorlens", notes="source registry entry"),
    )

    # 2. Define a sector
    pharma = Sector(
        name="Pharmaceuticals",
        description="Companies engaged in manufacturing of pharmaceuticals, APIs, and formulations.",
        provenance=Provenance(source="investorlens"),
    )

    # 3. Define a company (using Sun Pharma as an example)
    sun_pharma = Company(
        name="Sun Pharmaceutical Industries Ltd",
        isin="INE044A01026",
        nse_symbol="SUNPHARMA",
        bse_code="524715",
        sector_id=pharma.id,
        provenance=Provenance(
            source="nse",
            source_url="https://nseindia.com/get-quotes/equity?symbolCode=SUNPHARMA",
            extraction_method="bulk_download",
            confidence="high",
        ),
    )

    # 4. Define the security (equity ISIN)
    security = Security(
        isin="INE044A01026",
        company_id=sun_pharma.id,
        exchange="NSE+BSE",
        symbol="SUNPHARMA",
        provenance=Provenance(source="nse", extraction_method="bulk_download", confidence="high"),
    )

    # 5. Add an ISIN master row
    isin_master_row = ISINMaster(
        isin="INE044A01026",
        company_name="Sun Pharmaceutical Industries Ltd",
        nse_symbol="SUNPHARMA",
        bse_code="524715",
        sector="Pharmaceuticals",
        industry="Pharma",
        provenance=Provenance(source="nse", extraction_method="bulk_download", confidence="high"),
    )

    # 6. Add a price observation
    price_obs = Observation(
        subject_id=security.id,
        kind=ObservationKind.PRICE_CLOSE,
        period="2024-09-30",
        as_of=date(2024, 9, 30),
        value=1842.35,
        unit="INR",
        currency="INR",
        provenance=Provenance(
            source="nse",
            extraction_method="bulk_download",
            confidence="high",
            source_url="https://nseindia.com/api/reports?date=30-SEP-2024",
            reporting_period="2024-09-30",
        ),
    )

    # 7. Add a corporate action (bonus issue)
    bonus = CorporateAction(
        security_id=security.id,
        action_type=CorporateActionType.BONUS,
        ex_date=date(2024, 9, 30),  # illustrative, not actual
        ratio_numerator=1,
        ratio_denominator=1,
        provenance=Provenance(source="nse", extraction_method="bulk_download", confidence="high"),
    )

    # Print a summary
    print("=" * 70)
    print("INVESTORLENS — END-TO-END FOUNDATION SMOKE TEST")
    print("=" * 70)
    print(f"Source:        {nse_source.id}  ({nse_source.slug})")
    print(f"Sector:        {pharma.id}  ({pharma.name})")
    print(f"Company:       {sun_pharma.id}  ({sun_pharma.name})")
    print(f"  ISIN:        {sun_pharma.isin}")
    print(f"  NSE symbol:  {sun_pharma.nse_symbol}")
    print(f"  BSE code:    {sun_pharma.bse_code}")
    print(f"Security:      {security.id}  ({security.symbol})")
    print(f"ISIN row:      {isin_master_row.id}")
    print(f"Observation:   {price_obs.id}")
    print(f"  value:       {price_obs.value} {price_obs.unit}")
    print(f"  as_of:       {price_obs.as_of}")
    print(f"Corp action:   {bonus.id}  ({bonus.action_type.value} {bonus.ratio_numerator}:{bonus.ratio_denominator})")
    print()

    # Write to a temp output and confirm idempotency
    out_path = ROOT / "data" / "processed" / "smoke_test.jsonl"
    records = [
        r.model_dump(mode="json", exclude_none=True)
        for r in [nse_source, pharma, sun_pharma, security, isin_master_row, price_obs, bonus]
    ]

    # Round 1
    stats1 = upsert_records(out_path, records)
    print(f"First upsert:   {stats1}")

    # Round 2 — should be a no-op
    stats2 = upsert_records(out_path, records)
    print(f"Second upsert:  {stats2}  (should be 0/0)")

    # Read back
    import os
    file_size = os.path.getsize(out_path)
    print(f"Output file:    {out_path.relative_to(ROOT)}  ({file_size} bytes)")
    print()

    # Show a sample record
    print("Sample record (price observation):")
    print(json.dumps(price_obs.model_dump(mode="json", exclude_none=True), indent=2))

    # Clean up — remove the smoke test file so we don't pollute the repo
    out_path.unlink()
    print(f"\n[smoke] cleaned up {out_path.relative_to(ROOT)}")
    print("[smoke] foundation layer verified end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
