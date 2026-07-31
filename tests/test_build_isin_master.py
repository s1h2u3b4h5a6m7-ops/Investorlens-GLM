"""Tests for the ISIN master builder (investorlens.builders.isin_master)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from investorlens.builders import build_isin_master, merge_two_isin_records
from investorlens.models import ISINMaster, Provenance, SecurityType
from investorlens.models.provenance import Confidence


@pytest.fixture
def prov_nse() -> Provenance:
    return Provenance(
        source="nse",
        extraction_method="bulk_download",
        confidence=Confidence.HIGH,
        reporting_period="current",
    )


@pytest.fixture
def prov_bse() -> Provenance:
    return Provenance(
        source="bse",
        extraction_method="bulk_download",
        confidence=Confidence.HIGH,
        reporting_period="current",
    )


@pytest.fixture
def nse_record(prov_nse: Provenance) -> ISINMaster:
    """NSE record: only symbol, no company name (matches EQUITY_L.csv reality)."""
    return ISINMaster(
        isin="INE044A01026",
        company_name="SUNPHARMA",
        nse_symbol="SUNPHARMA",
        bse_code=None,
        security_type=SecurityType.EQUITY,
        exchange="NSE",
        sector=None,
        industry=None,
        active=True,
        face_value=Decimal("1"),
        provenance=prov_nse,
    )


@pytest.fixture
def bse_record(prov_bse: Provenance) -> ISINMaster:
    """BSE record: full company name, scrip code, sector."""
    return ISINMaster(
        isin="INE044A01026",
        company_name="Sun Pharmaceutical Industries Limited",
        nse_symbol=None,
        bse_code="524715",
        security_type=SecurityType.EQUITY,
        exchange="BSE",
        sector="Pharmaceuticals",
        industry=None,
        active=True,
        face_value=Decimal("1"),
        provenance=prov_bse,
    )


class TestMergeTwoIsinRecords:
    def test_both_none_returns_none(self) -> None:
        assert merge_two_isin_records(None, None) is None

    def test_only_nse(self, nse_record: ISINMaster) -> None:
        merged = merge_two_isin_records(nse_record, None)
        assert merged is not None
        assert merged.exchange == "NSE"
        assert merged.nse_symbol == "SUNPHARMA"
        assert merged.bse_code is None
        assert merged.provenance.source == "nse"  # unchanged

    def test_only_bse(self, bse_record: ISINMaster) -> None:
        merged = merge_two_isin_records(None, bse_record)
        assert merged is not None
        assert merged.exchange == "BSE"
        assert merged.bse_code == "524715"
        assert merged.nse_symbol is None
        assert merged.provenance.source == "bse"

    def test_merge_takes_company_name_from_bse(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        merged = merge_two_isin_records(nse_record, bse_record)
        assert merged is not None
        assert merged.company_name == "Sun Pharmaceutical Industries Limited"
        assert merged.nse_symbol == "SUNPHARMA"
        assert merged.bse_code == "524715"
        assert merged.exchange == "NSE+BSE"

    def test_merge_takes_sector_from_bse(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        merged = merge_two_isin_records(nse_record, bse_record)
        assert merged is not None
        assert merged.sector == "Pharmaceuticals"

    def test_merge_active_conservative(self, prov_nse: Provenance, prov_bse: Provenance) -> None:
        """If NSE says active=False but BSE says active=True, merged should be True (conservative)."""
        inactive_nse = ISINMaster(
            isin="INE044A01026",
            company_name="X",
            exchange="NSE",
            active=False,
            provenance=prov_nse,
        )
        active_bse = ISINMaster(
            isin="INE044A01026",
            company_name="X Co Ltd",
            exchange="BSE",
            active=True,
            provenance=prov_bse,
        )
        merged = merge_two_isin_records(inactive_nse, active_bse)
        assert merged is not None
        assert merged.active is True

    def test_merge_provenance_source_is_combined(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        merged = merge_two_isin_records(nse_record, bse_record)
        assert merged is not None
        assert merged.provenance.source == "nse+bse"
        assert merged.provenance.confidence == Confidence.HIGH

    def test_merge_id_deterministic(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        """Re-merging the same pair produces the same ID."""
        a = merge_two_isin_records(nse_record, bse_record)
        b = merge_two_isin_records(nse_record, bse_record)
        assert a is not None
        assert b is not None
        assert a.id == b.id


class TestBuildIsinMaster:
    def test_empty_inputs_returns_empty(self) -> None:
        assert build_isin_master([], []) == []

    def test_only_nse_records(self, nse_record: ISINMaster) -> None:
        result = build_isin_master([nse_record], [])
        assert len(result) == 1
        assert result[0].exchange == "NSE"

    def test_only_bse_records(self, bse_record: ISINMaster) -> None:
        result = build_isin_master([], [bse_record])
        assert len(result) == 1
        assert result[0].exchange == "BSE"

    def test_merge_overlapping(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        result = build_isin_master([nse_record], [bse_record])
        assert len(result) == 1
        assert result[0].exchange == "NSE+BSE"
        assert result[0].nse_symbol == "SUNPHARMA"
        assert result[0].bse_code == "524715"

    def test_disjoint_isins_kept_separate(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        # Different ISINs — should appear as two separate records.
        bse_record2 = bse_record.model_copy(update={"isin": "INE999A99999"})
        result = build_isin_master([nse_record], [bse_record2])
        assert len(result) == 2
        exchanges = {r.exchange for r in result}
        assert exchanges == {"NSE", "BSE"}

    def test_output_sorted_by_isin(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        """Output ordering must be deterministic regardless of input order."""
        nse_record_b = nse_record.model_copy(update={"isin": "INE999A99999", "nse_symbol": "OTHER"})
        nse_record_a = nse_record  # INE044A01026

        result1 = build_isin_master([nse_record_a, nse_record_b], [])
        result2 = build_isin_master([nse_record_b, nse_record_a], [])  # reversed input

        isins1 = [r.isin for r in result1]
        isins2 = [r.isin for r in result2]
        assert isins1 == isins2  # same set, same order
        assert isins1 == sorted(isins1)  # sorted ascending

    def test_idempotent_output(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        """Same input → byte-identical output (excluding retrieved_at which we control)."""
        ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)
        a = build_isin_master([nse_record], [bse_record], retrieved_at=ts)
        b = build_isin_master([nse_record], [bse_record], retrieved_at=ts)
        assert [r.model_dump(mode="json") for r in a] == [r.model_dump(mode="json") for r in b]

    def test_duplicate_within_source_kept_first(
        self, nse_record: ISINMaster, bse_record: ISINMaster, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If the same ISIN appears twice within NSE input, only the first is kept (with a warning)."""
        import logging

        nse_dup = nse_record.model_copy(update={"nse_symbol": "DIFFERENT"})
        with caplog.at_level(logging.WARNING):
            result = build_isin_master([nse_record, nse_dup], [bse_record])
        assert len(result) == 1
        assert result[0].nse_symbol == "SUNPHARMA"  # first wins
        assert any("duplicate ISIN" in rec.message for rec in caplog.records)


class TestBuildIsinMasterRoundTrip:
    """End-to-end: serialize merged records to JSON, reload them, verify round-trip."""

    def test_roundtrip_through_json(self, nse_record: ISINMaster, bse_record: ISINMaster) -> None:
        import json

        merged = build_isin_master([nse_record], [bse_record])
        serialized = json.dumps([r.model_dump(mode="json") for r in merged], sort_keys=True)
        reloaded = json.loads(serialized)
        assert len(reloaded) == 1
        # Reconstruct ISINMaster from the dict
        reloaded_rec = ISINMaster(**reloaded[0])
        assert reloaded_rec.isin == "INE044A01026"
        assert reloaded_rec.exchange == "NSE+BSE"
        assert reloaded_rec.nse_symbol == "SUNPHARMA"
        assert reloaded_rec.bse_code == "524715"
        assert reloaded_rec.sector == "Pharmaceuticals"
