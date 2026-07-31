"""Tests for the NSE corporate actions parser (investorlens.parsers.corp_actions)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from investorlens.parsers import corp_actions
from investorlens.parsers.corp_actions import (
    classify_subject,
    extract_dividend_amount,
    extract_ratio,
    parse_corpact_csv,
)
from investorlens.models import CorporateActionType
from investorlens.ids import make_id

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def csv_text() -> str:
    return (FIXTURES / "nse_corpact.csv").read_text(encoding="utf-8")


@pytest.fixture
def isin_master() -> list[dict]:
    """ISIN master matching the symbols in the corp-actions fixture."""
    return [
        {"isin": "INE002A01018", "nse_symbol": "RELIANCE"},
        {"isin": "INE467B01029", "nse_symbol": "TCS"},
        {"isin": "INE009A01021", "nse_symbol": "INFY"},
        {"isin": "INE044A01026", "nse_symbol": "SUNPHARMA"},
        {"isin": "INE040A01034", "nse_symbol": "HDFCBANK"},
        {"isin": "INE075A01022", "nse_symbol": "WIPRO"},
        {"isin": "INE030A01027", "nse_symbol": "HINDUNILVR"},
        {"isin": "INE000A00001", "nse_symbol": "SYMBOLCHANGE"},
        {"isin": "INE000A00002", "nse_symbol": "MERGERTEST"},
        # NOTE: UNKNOWNCO is intentionally NOT in the ISIN master
    ]


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# classify_subject
# ---------------------------------------------------------------------------


class TestClassifySubject:
    def test_bonus(self) -> None:
        assert classify_subject("Bonus - 1:1") == CorporateActionType.BONUS
        assert classify_subject("Bonus Issue 2:1") == CorporateActionType.BONUS

    def test_split(self) -> None:
        assert classify_subject("Stock Split from Rs.10/- to Rs.2/-") == CorporateActionType.SPLIT
        assert classify_subject("Sub-division of equity shares") == CorporateActionType.SPLIT

    def test_dividend(self) -> None:
        assert classify_subject("Dividend - Rs.5/- per Share") == CorporateActionType.DIVIDEND
        assert classify_subject("Interim Dividend Rs.21/-") == CorporateActionType.DIVIDEND
        assert classify_subject("Annual General Meeting / Dividend") == CorporateActionType.DIVIDEND

    def test_rights(self) -> None:
        assert classify_subject("Rights Issue 1:5 @ Rs.100") == CorporateActionType.RIGHTS

    def test_merger(self) -> None:
        assert classify_subject("Scheme of Amalgamation") == CorporateActionType.MERGER
        assert classify_subject("Merger of subsidiary") == CorporateActionType.MERGER

    def test_demerger(self) -> None:
        assert classify_subject("Demerger of divisions") == CorporateActionType.DEMERGER
        assert classify_subject("Spin-off of subsidiary") == CorporateActionType.DEMERGER

    def test_symbol_change(self) -> None:
        assert classify_subject("Change of Symbol from OLD to NEW") == CorporateActionType.SYMBOL_CHANGE

    def test_other_when_no_match(self) -> None:
        assert classify_subject("Some random corporate action") == CorporateActionType.OTHER

    def test_empty_returns_other(self) -> None:
        assert classify_subject("") == CorporateActionType.OTHER
        assert classify_subject(None) == CorporateActionType.OTHER

    def test_bonus_preferred_over_dividend_when_both_present(self) -> None:
        """The Subject can contain both keywords. Bonus should win because it's
        checked first (and bonus issues often come with interim dividends)."""
        result = classify_subject("Bonus 1:1 and Dividend Rs.5")
        assert result == CorporateActionType.BONUS

    def test_split_preferred_over_face_value(self) -> None:
        """Split rows mention face value; we want them classified as SPLIT."""
        result = classify_subject("Stock Split from Rs.10/- to Rs.1/-, face value change")
        assert result == CorporateActionType.SPLIT


# ---------------------------------------------------------------------------
# extract_ratio
# ---------------------------------------------------------------------------


class TestExtractRatio:
    def test_simple_ratio(self) -> None:
        assert extract_ratio("Bonus 1:1") == (1.0, 1.0)
        assert extract_ratio("Bonus 2:5") == (2.0, 5.0)
        assert extract_ratio("Rights 1:3") == (1.0, 3.0)

    def test_ratio_with_spaces(self) -> None:
        assert extract_ratio("Bonus 1 : 1") == (1.0, 1.0)
        assert extract_ratio("Bonus 10 : 3") == (10.0, 3.0)

    def test_ratio_with_decimal(self) -> None:
        assert extract_ratio("Bonus 1.5:1") == (1.5, 1.0)

    def test_no_ratio_returns_none(self) -> None:
        assert extract_ratio("Dividend - Rs.5/-") == (None, None)
        assert extract_ratio("") == (None, None)
        assert extract_ratio(None) == (None, None)

    def test_picks_first_ratio_in_text(self) -> None:
        """If the text has multiple ratios, the first one is picked."""
        assert extract_ratio("Bonus 1:1 and 2:5") == (1.0, 1.0)


# ---------------------------------------------------------------------------
# extract_dividend_amount
# ---------------------------------------------------------------------------


class TestExtractDividendAmount:
    def test_rs_format_with_slash(self) -> None:
        assert extract_dividend_amount("Dividend - Rs.5/- per Share") == Decimal("5")
        assert extract_dividend_amount("Rs.21/-") == Decimal("21")

    def test_rs_format_without_slash(self) -> None:
        assert extract_dividend_amount("Rs.73 per share") == Decimal("73")
        assert extract_dividend_amount("Rs.7") == Decimal("7")

    def test_inr_format(self) -> None:
        assert extract_dividend_amount("INR 10 per share") == Decimal("10")

    def test_no_amount_returns_none(self) -> None:
        assert extract_dividend_amount("Bonus 1:1") is None
        assert extract_dividend_amount("") is None
        assert extract_dividend_amount(None) is None

    def test_decimal_amount(self) -> None:
        assert extract_dividend_amount("Rs.12.50 per share") == Decimal("12.50")


# ---------------------------------------------------------------------------
# parse_corpact_csv
# ---------------------------------------------------------------------------


class TestParseCorpactCsv:
    def test_parses_known_count(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        """The fixture has 13 rows. UNKNOWNCO is not in ISIN master → skipped.
        So we expect 12 parsed records."""
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        assert len(records) == 12

    def test_skips_symbols_not_in_master(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        """UNKNOWNCO appears in the fixture but not in the ISIN master."""
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        # None should be for the UNKNOWNCO row.
        for r in records:
            assert "UNKNOWNCO" not in (r.notes or "")

    def test_classifies_action_types_correctly(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        # Group by action type.
        from collections import Counter
        types = Counter(r.action_type for r in records)
        # Expected based on the fixture:
        # - DIVIDEND: RELIANCE×1, TCS×1, INFY×1 = 3
        # - SPLIT: SUNPHARMA×1, HDFCBANK×1, HINDUNILVR×1 = 3
        # - BONUS: TCS×1, RELIANCE×1, INFY×1, WIPRO×1 = 4
        # - SYMBOL_CHANGE: 1
        # - MERGER: 1
        assert types[CorporateActionType.DIVIDEND] == 3
        assert types[CorporateActionType.SPLIT] == 3
        assert types[CorporateActionType.BONUS] == 4
        assert types[CorporateActionType.SYMBOL_CHANGE] == 1
        assert types[CorporateActionType.MERGER] == 1

    def test_dividend_amount_extracted(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        dividends = [r for r in records if r.action_type == CorporateActionType.DIVIDEND]
        assert len(dividends) == 3
        amounts = {(r.security_id, r.amount_per_share) for r in dividends}
        # RELIANCE dividend Rs.7, TCS Rs.73, INFY Rs.21
        rel_sid = make_id("sec", {"isin": "INE002A01018"})
        tcs_sid = make_id("sec", {"isin": "INE467B01029"})
        infy_sid = make_id("sec", {"isin": "INE009A01021"})
        assert (rel_sid, Decimal("7")) in amounts
        assert (tcs_sid, Decimal("73")) in amounts
        assert (infy_sid, Decimal("21")) in amounts

    def test_bonus_ratio_extracted(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        bonuses = [r for r in records if r.action_type == CorporateActionType.BONUS]
        assert len(bonuses) == 4
        # Find the 1:3 WIPRO bonus
        wipro_sid = make_id("sec", {"isin": "INE075A01022"})
        wipro_bonus = next(r for r in bonuses if r.security_id == wipro_sid)
        assert wipro_bonus.ratio_numerator == 1.0
        assert wipro_bonus.ratio_denominator == 3.0
        assert wipro_bonus.ex_date == date(2019, 3, 15)

    def test_split_ratio_inferred_from_face_value(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        """SUNPHARMA split from Rs.10 to Rs.1 → 10:1 ratio inferred."""
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        sunpharma_sid = make_id("sec", {"isin": "INE044A01026"})
        splits = [r for r in records if r.action_type == CorporateActionType.SPLIT and r.security_id == sunpharma_sid]
        assert len(splits) == 1
        s = splits[0]
        assert s.ratio_numerator == 10.0  # 10/1 = 10
        assert s.ratio_denominator == 1.0
        assert s.new_face_value == Decimal("1")
        assert s.ex_date == date(2023, 12, 20)

    def test_split_ratio_handles_re_point_1_singular(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        """NSE uses 'Re.1' (singular) for 1 rupee. The HDFCBANK split 'Rs.2/- to Re.1/-'
        should be parsed as a 2:1 ratio."""
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        hdfc_sid = make_id("sec", {"isin": "INE040A01034"})
        splits = [r for r in records if r.action_type == CorporateActionType.SPLIT and r.security_id == hdfc_sid]
        assert len(splits) == 1
        s = splits[0]
        assert s.ratio_numerator == 2.0
        assert s.ratio_denominator == 1.0
        assert s.new_face_value == Decimal("1")
        assert s.ex_date == date(2019, 9, 19)

    def test_security_id_derived_from_isin(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        rel_sid = make_id("sec", {"isin": "INE002A01018"})
        rel_records = [r for r in records if r.security_id == rel_sid]
        assert len(rel_records) == 2  # RELIANCE has 1 dividend + 1 bonus

    def test_provenance_attached(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        prov = records[0].provenance
        assert prov.source == "nse"
        assert prov.extraction_method.value == "bulk_download"
        assert prov.confidence.value == "high"
        assert prov.retrieved_at == fixed_ts

    def test_id_deterministic(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        a = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        b = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        assert [r.id for r in a] == [r.id for r in b]

    def test_id_includes_security_action_date(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        """Each record has a unique (security_id, action_type, ex_date)."""
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        keys = {(r.security_id, r.action_type.value, r.ex_date.isoformat()) for r in records}
        assert len(keys) == len(records)
        for r in records:
            assert r.id.startswith("ca_")

    def test_output_sorted(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        keys = [(r.security_id, r.ex_date.isoformat(), r.action_type.value) for r in records]
        assert keys == sorted(keys)

    def test_record_date_parsed(self, csv_text: str, isin_master: list[dict], fixed_ts: datetime) -> None:
        records = parse_corpact_csv(csv_text, isin_master=isin_master, retrieved_at=fixed_ts)
        # All records in the fixture have record_date == ex_date.
        for r in records:
            assert r.record_date == r.ex_date

    def test_deduplicates_within_file(self, isin_master: list[dict], fixed_ts: datetime) -> None:
        """If the same (security, action_type, ex_date) appears twice, keep only one."""
        text = (
            "Symbol,Series,Subject,Ex-Date,Record-Date,Broadcast-Date,Dividend Amount / Share,Purpose\n"
            "RELIANCE,EQ,Dividend - Rs.7/- per Share,10-SEP-2024,10-SEP-2024,30-AUG-2024,7,Annual Dividend\n"
            "RELIANCE,EQ,Dividend - Rs.7/- per Share,10-SEP-2024,10-SEP-2024,30-AUG-2024,7,Duplicate row\n"
        )
        records = parse_corpact_csv(text, isin_master=isin_master, retrieved_at=fixed_ts)
        assert len(records) == 1

    def test_empty_csv_returns_empty(self, isin_master: list[dict], fixed_ts: datetime) -> None:
        text = "Symbol,Series,Subject,Ex-Date\n"
        records = parse_corpact_csv(text, isin_master=isin_master, retrieved_at=fixed_ts)
        assert records == []

    def test_handles_missing_isin_master(self, csv_text: str, fixed_ts: datetime) -> None:
        """If isin_master is None or empty, all rows are skipped (with warnings)."""
        records = parse_corpact_csv(csv_text, isin_master=None, retrieved_at=fixed_ts)
        assert records == []
        records2 = parse_corpact_csv(csv_text, isin_master=[], retrieved_at=fixed_ts)
        assert records2 == []
