"""Tests for the BSE parsers (investorlens.parsers.bse)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from investorlens.parsers import bse

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def bse_csv_text() -> str:
    return (FIXTURES / "bse_scrips.csv").read_text(encoding="utf-8")


class TestNormalizeRowKeys:
    def test_canonical_aliases(self) -> None:
        row = {"Scrip Code": "524715", "ISIN": "INE044A01026", "Issuer Name": "Sun Pharma"}
        out = bse.normalize_row_keys(row)
        assert out == {"scrip_code": "524715", "isin": "INE044A01026", "issuer_name": "Sun Pharma"}

    def test_unknown_keys_preserved_lowercase(self) -> None:
        row = {"Scrip Code": "524715", "Some Weird Column": "x"}
        out = bse.normalize_row_keys(row)
        assert "some weird column" in out
        assert out["scrip_code"] == "524715"


class TestIterListScripsRows:
    def test_returns_normalized_dicts(self, bse_csv_text: str) -> None:
        rows = list(bse.iter_list_scrips_rows(bse_csv_text))
        assert len(rows) == 10
        assert rows[0]["scrip_code"] == "524715"
        assert rows[0]["isin"] == "INE044A01026"
        assert rows[0]["issuer_name"] == "Sun Pharmaceutical Industries Limited"

    def test_skips_blank_rows(self) -> None:
        text = "Scrip Code,ISIN\n524715,INE044A01026\n,\n,\n"
        rows = list(bse.iter_list_scrips_rows(text))
        assert len(rows) == 1


class TestParseListScripsCsv:
    def test_parses_all_rows(self, bse_csv_text: str) -> None:
        records = bse.parse_list_scrips_csv(bse_csv_text)
        assert len(records) == 10

    def test_first_record_fields(self, bse_csv_text: str) -> None:
        records = bse.parse_list_scrips_csv(bse_csv_text)
        r = records[0]
        assert r.isin == "INE044A01026"
        assert r.bse_code == "524715"
        assert r.company_name == "Sun Pharmaceutical Industries Limited"
        assert r.nse_symbol is None  # BSE doesn't provide NSE symbol
        assert r.security_type.value == "equity"
        assert r.exchange == "BSE"
        assert r.sector == "Pharmaceuticals"
        assert r.face_value == Decimal("1")
        assert r.effective_from == date(1994, 10, 10)

    def test_provenance_attached(self, bse_csv_text: str) -> None:
        records = bse.parse_list_scrips_csv(bse_csv_text)
        prov = records[0].provenance
        assert prov.source == "bse"
        assert prov.extraction_method.value == "bulk_download"
        assert prov.confidence.value == "high"

    def test_id_deterministic(self, bse_csv_text: str) -> None:
        a = bse.parse_list_scrips_csv(bse_csv_text)
        b = bse.parse_list_scrips_csv(bse_csv_text)
        assert [r.id for r in a] == [r.id for r in b]

    def test_skips_rows_without_isin(self) -> None:
        text = "Scrip Code,ISIN,Issuer Name,Security Type\n1,INE044A01026,Sun Pharma,Equity\n2,,Bad Row,Equity\n"
        records = bse.parse_list_scrips_csv(text)
        assert len(records) == 1

    def test_skips_short_isin(self) -> None:
        """A clearly malformed ISIN (<12 chars) must be dropped."""
        text = "Scrip Code,ISIN,Issuer Name,Security Type\n1,INE044,Sun Pharma,Equity\n"
        records = bse.parse_list_scrips_csv(text)
        assert records == []

    def test_security_type_other_for_unknown(self) -> None:
        text = (
            "Scrip Code,ISIN,Issuer Name,Security Type\n"
            "1,INE044A01026,Sun Pharma,Convertibond\n"  # unknown type
        )
        records = bse.parse_list_scrips_csv(text)
        assert records[0].security_type.value == "other"

    def test_status_active_parsed_correctly(self) -> None:
        text = (
            "Scrip Code,ISIN,Issuer Name,Status,Security Type\n"
            "1,INE044A01026,Sun Pharma,Active,Equity\n"
            "2,INE044A01027,Old Co,Suspended,Equity\n"
            "3,INE044A01028,Dead Co,De-listed,Equity\n"
        )
        records = bse.parse_list_scrips_csv(text)
        statuses = [r.active for r in records]
        assert statuses == [True, False, False]

    def test_tolerates_column_name_variations(self) -> None:
        """BSE's column names vary across years; parser should accept any alias."""
        text = (
            "SC_CODE,SC_NAME,ISIN NO,Issuer,FaceValue,Sector\n"
            "524715,SUNPHARMA,INE044A01026,Sun Pharma,1,Pharma\n"
        )
        records = bse.parse_list_scrips_csv(text)
        assert len(records) == 1
        assert records[0].bse_code == "524715"
        assert records[0].face_value == Decimal("1")
        assert records[0].sector == "Pharma"

    def test_uses_scrip_name_when_issuer_missing(self) -> None:
        text = "Scrip Code,ISIN,Scrip Name,Security Type\n1,INE044A01026,SUNPHARMA,Equity\n"
        records = bse.parse_list_scrips_csv(text)
        assert len(records) == 1
        assert records[0].company_name == "SUNPHARMA"
