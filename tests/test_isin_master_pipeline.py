"""
End-to-end test for the ISIN master pipeline:
  fixture CSVs → parsers → builder → upsert → reload → verify

This is the integration test for Milestone 1.1. It confirms:
  - Parsers correctly read the realistic fixtures.
  - The builder correctly merges NSE + BSE records.
  - The full pipeline is idempotent (running it twice produces no changes).
  - Output written to disk is valid JSONL and round-trips back to ISINMaster models.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from investorlens.builders import build_isin_master
from investorlens.io import read_jsonl, upsert_records
from investorlens.models import ISINMaster
from investorlens.parsers import bse, nse

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixed_timestamp() -> datetime:
    """A fixed timestamp so the test output is byte-identical across runs."""
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def parsed_nse_records(fixed_timestamp: datetime) -> list[ISINMaster]:
    csv_text = (FIXTURES / "nse_equity_l.csv").read_text(encoding="utf-8")
    return nse.parse_equity_l_csv(csv_text, retrieved_at=fixed_timestamp)


@pytest.fixture
def parsed_bse_records(fixed_timestamp: datetime) -> list[ISINMaster]:
    csv_text = (FIXTURES / "bse_scrips.csv").read_text(encoding="utf-8")
    return bse.parse_list_scrips_csv(csv_text, retrieved_at=fixed_timestamp)


class TestIsinMasterPipelineE2E:
    def test_fixtures_have_expected_counts(
        self, parsed_nse_records: list[ISINMaster], parsed_bse_records: list[ISINMaster]
    ) -> None:
        assert len(parsed_nse_records) == 10
        assert len(parsed_bse_records) == 10

    def test_merge_produces_correct_counts(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
    ) -> None:
        """The fixtures share 5 ISINs (SUNPHARMA, RELIANCE, TCS, INFY, HDFCBANK).
        NSE has 5 more (20MICRONS, 21STCENMGM, 3MINDIA, AARTIIND, ABB).
        BSE has 5 more (JSWSTEEL, BRITANNIA, SHRIRAMFIN, ZOMATO, SIEMENS).
        So merged should be 15 records: 5 NSE+BSE + 5 NSE-only + 5 BSE-only.
        """
        merged = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        assert len(merged) == 15

        by_exchange = {"NSE": 0, "BSE": 0, "NSE+BSE": 0}
        for r in merged:
            by_exchange[r.exchange] += 1
        assert by_exchange == {"NSE": 5, "BSE": 5, "NSE+BSE": 5}

    def test_overlapping_records_merged_correctly(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
    ) -> None:
        merged = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        by_isin = {r.isin: r for r in merged}

        # SUNPHARMA: NSE symbol "SUNPHARMA" + BSE code "524715" + BSE company name + BSE sector
        sunpharma = by_isin["INE044A01026"]
        assert sunpharma.exchange == "NSE+BSE"
        assert sunpharma.nse_symbol == "SUNPHARMA"
        assert sunpharma.bse_code == "524715"
        assert sunpharma.company_name == "Sun Pharmaceutical Industries Limited"
        assert sunpharma.sector == "Pharmaceuticals"
        assert sunpharma.provenance.source == "nse+bse"

    def test_nse_only_records_have_no_bse_code(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
    ) -> None:
        merged = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        by_isin = {r.isin: r for r in merged}

        # 20MICRONS is in NSE only
        rec = by_isin["INE144J01027"]
        assert rec.exchange == "NSE"
        assert rec.bse_code is None
        assert rec.nse_symbol == "20MICRONS"
        assert rec.provenance.source == "nse"

    def test_bse_only_records_have_no_nse_symbol(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
    ) -> None:
        merged = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        by_isin = {r.isin: r for r in merged}

        # JSWSTEEL is in BSE only
        rec = by_isin["INE017A01036"]
        assert rec.exchange == "BSE"
        assert rec.nse_symbol is None
        assert rec.bse_code == "532281"
        assert rec.company_name == "JSW Steel Limited"
        assert rec.provenance.source == "bse"

    def test_pipeline_idempotent_on_disk(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
        tmp_path: Path,
    ) -> None:
        """End-to-end idempotency: writing twice must produce 0 inserts/updates on the 2nd pass."""
        out_path = tmp_path / "isin_master.jsonl"
        merged = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        payload = [r.model_dump(mode="json", exclude_none=True) for r in merged]

        stats1 = upsert_records(out_path, payload, key="id")
        stats2 = upsert_records(out_path, payload, key="id")

        assert stats1["inserted"] == 15
        assert stats1["updated"] == 0
        assert stats1["total"] == 15
        # Second pass must be a no-op (byte-identical content).
        assert stats2["inserted"] == 0
        assert stats2["updated"] == 0
        assert stats2["total"] == 15

    def test_output_round_trips_to_models(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
        tmp_path: Path,
    ) -> None:
        """JSONL on disk must round-trip back to valid ISINMaster models."""
        out_path = tmp_path / "isin_master.jsonl"
        merged = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        payload = [r.model_dump(mode="json", exclude_none=True) for r in merged]
        upsert_records(out_path, payload, key="id")

        # Read back as dicts, reconstruct as models.
        reloaded = read_jsonl(out_path)
        assert len(reloaded) == 15
        for row in reloaded:
            rec = ISINMaster(**row)
            assert rec.id.startswith("isin_")
            assert rec.isin  # always populated
            assert rec.exchange in {"NSE", "BSE", "NSE+BSE"}

    def test_output_is_canonical_byte_identical(
        self,
        parsed_nse_records: list[ISINMaster],
        parsed_bse_records: list[ISINMaster],
        fixed_timestamp: datetime,
        tmp_path: Path,
    ) -> None:
        """Two independent runs must produce byte-identical output."""
        out1 = tmp_path / "run1.jsonl"
        out2 = tmp_path / "run2.jsonl"

        merged1 = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)
        merged2 = build_isin_master(parsed_nse_records, parsed_bse_records, retrieved_at=fixed_timestamp)

        from investorlens.io import write_jsonl

        write_jsonl(out1, [r.model_dump(mode="json", exclude_none=True) for r in merged1])
        write_jsonl(out2, [r.model_dump(mode="json", exclude_none=True) for r in merged2])

        assert out1.read_bytes() == out2.read_bytes()
