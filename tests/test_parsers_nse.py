"""Tests for the NSE parsers (investorlens.parsers.nse)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from investorlens.parsers import nse

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def nse_csv_text() -> str:
    return (FIXTURES / "nse_equity_l.csv").read_text(encoding="utf-8")


class TestIterEquityLRows:
    def test_returns_dicts(self, nse_csv_text: str) -> None:
        rows = list(nse.iter_equity_l_rows(nse_csv_text))
        # 1 header + 10 data rows in the fixture.
        assert len(rows) == 10
        assert "SYMBOL" in rows[0]
        assert rows[0]["SYMBOL"] == "20MICRONS"

    def test_strips_whitespace_in_keys_and_values(self) -> None:
        text = "SYMBOL , ISIN NUMBER\n  ABC , INE001A01018 \n"
        rows = list(nse.iter_equity_l_rows(text))
        assert rows[0] == {"SYMBOL": "ABC", "ISIN NUMBER": "INE001A01018"}


class TestParseEquityLCsv:
    def test_parses_all_rows(self, nse_csv_text: str) -> None:
        records = nse.parse_equity_l_csv(nse_csv_text)
        assert len(records) == 10

    def test_first_record_fields(self, nse_csv_text: str) -> None:
        records = nse.parse_equity_l_csv(nse_csv_text)
        r = records[0]
        assert r.isin == "INE144J01027"
        assert r.nse_symbol == "20MICRONS"
        assert r.company_name == "20MICRONS"  # EQUITY_L.csv has only symbols
        assert r.security_type.value == "equity"
        assert r.exchange == "NSE"
        assert r.active is True
        assert r.face_value == Decimal("10.00")
        assert r.effective_from == date(2008, 10, 10)

    def test_provenance_attached(self, nse_csv_text: str) -> None:
        records = nse.parse_equity_l_csv(nse_csv_text)
        prov = records[0].provenance
        assert prov.source == "nse"
        assert prov.extraction_method.value == "bulk_download"
        assert prov.confidence.value == "high"
        assert prov.source_url is not None
        assert "EQUITY_L.csv" in str(prov.source_url)

    def test_id_starts_with_isin_prefix(self, nse_csv_text: str) -> None:
        records = nse.parse_equity_l_csv(nse_csv_text)
        for r in records:
            assert r.id.startswith("isin_")

    def test_id_deterministic(self, nse_csv_text: str) -> None:
        a = nse.parse_equity_l_csv(nse_csv_text)
        b = nse.parse_equity_l_csv(nse_csv_text)
        assert [r.id for r in a] == [r.id for r in b]

    def test_skips_rows_without_isin(self) -> None:
        text = (
            "SYMBOL,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "GOODONE,EQ,10-Oct-2008,10.00,1,INE144J01027,10.00\n"
            "BADONE,EQ,10-Oct-2008,10.00,1,,10.00\n"  # missing ISIN
        )
        records = nse.parse_equity_l_csv(text)
        assert len(records) == 1
        assert records[0].nse_symbol == "GOODONE"

    def test_dedupes_isin(self) -> None:
        """NSE can list the same ISIN under multiple series (EQ + BE). We keep the first."""
        text = (
            "SYMBOL,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "ABC,EQ,10-Oct-2008,10.00,1,INE144J01027,10.00\n"
            "ABC,BE,10-Oct-2008,10.00,1,INE144J01027,10.00\n"  # same ISIN, different series
        )
        records = nse.parse_equity_l_csv(text)
        assert len(records) == 1

    def test_empty_input_returns_empty_list(self) -> None:
        text = "SYMBOL,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
        records = nse.parse_equity_l_csv(text)
        assert records == []

    def test_retrieved_at_propagates_to_provenance(self, nse_csv_text: str) -> None:
        from datetime import datetime, timezone

        ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)
        records = nse.parse_equity_l_csv(nse_csv_text, retrieved_at=ts)
        assert records[0].provenance.retrieved_at == ts
