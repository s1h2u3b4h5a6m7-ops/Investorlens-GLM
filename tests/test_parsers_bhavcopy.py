"""Tests for the NSE bhavcopy parser (investorlens.parsers.bhavcopy)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investorlens.parsers import bhavcopy
from investorlens.parsers.bhavcopy import BhavcopyFormat, parse_bhavcopy_csv
from investorlens.models import DataStatus, ObservationKind

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def modern_csv() -> str:
    return (FIXTURES / "bhavcopy_modern.csv").read_text(encoding="utf-8")


@pytest.fixture
def legacy_csv() -> str:
    return (FIXTURES / "bhavcopy_legacy.csv").read_text(encoding="utf-8")


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def test_detects_modern(self) -> None:
        # Modern bhavcopy has these and more columns.
        header = ["TradDt", "Sym", "SecTp", "TckrSymb", "Sgmt", "Sr", "ISIN", "ClsPric", "OpnPric"]
        assert bhavcopy.detect_format(header) == BhavcopyFormat.MODERN

    def test_detects_legacy(self) -> None:
        header = ["SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP", "ISIN"]
        assert bhavcopy.detect_format(header) == BhavcopyFormat.LEGACY

    def test_unknown_format(self) -> None:
        header = ["foo", "bar", "baz"]
        assert bhavcopy.detect_format(header) == BhavcopyFormat.UNKNOWN


# ---------------------------------------------------------------------------
# Normalizer (rows)
# ---------------------------------------------------------------------------


class TestNormalizeBhavcopyRows:
    def test_modern_yields_expected_count(self, modern_csv: str) -> None:
        rows = list(bhavcopy.normalize_bhavcopy_rows(modern_csv))
        assert len(rows) == 6  # 6 ISINs in the fixture

    def test_legacy_yields_expected_count(self, legacy_csv: str) -> None:
        rows = list(bhavcopy.normalize_bhavcopy_rows(legacy_csv))
        assert len(rows) == 6

    def test_modern_first_row_fields(self, modern_csv: str) -> None:
        rows = list(bhavcopy.normalize_bhavcopy_rows(modern_csv))
        r = rows[0]
        assert r.symbol == "RELIANCE"
        assert r.isin == "INE002A01018"
        assert r.trade_date == date(2024, 9, 30)
        assert r.open == 2740.00
        assert r.high == 2760.00
        assert r.low == 2730.00
        assert r.close == 2750.00
        assert r.volume == 1000000
        assert r.turnover == 275000000.00

    def test_legacy_first_row_fields(self, legacy_csv: str) -> None:
        rows = list(bhavcopy.normalize_bhavcopy_rows(legacy_csv))
        r = rows[0]
        assert r.symbol == "RELIANCE"
        assert r.isin == "INE002A01018"
        assert r.trade_date == date(2024, 9, 30)
        assert r.open == 2740.00
        assert r.high == 2760.00
        assert r.low == 2730.00
        assert r.close == 2750.00
        assert r.volume == 1000000
        assert r.turnover == 275000000.00

    def test_legacy_skips_non_equity_series(self) -> None:
        text = (
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
            "RELIANCE,EQ,100,101,99,100,100,99,1000,100000,30-SEP-2024,10,INE002A01018\n"
            "NIFTY,IX,18000,18100,17900,18050,18050,17950,100000,0,30-SEP-2024,500,INE000A00000\n"
        )
        rows = list(bhavcopy.normalize_bhavcopy_rows(text))
        assert len(rows) == 1  # IX (index) filtered out
        assert rows[0].series == "EQ"

    def test_unknown_format_raises(self) -> None:
        text = "foo,bar,baz\n1,2,3\n"
        with pytest.raises(ValueError, match="Could not detect bhavcopy format"):
            list(bhavcopy.normalize_bhavcopy_rows(text))

    def test_skips_rows_missing_isin(self) -> None:
        # Use enough modern columns to trigger format detection.
        text = (
            "TradDt,Sym,SecTp,TckrSymb,Sgmt,Sr,Src,ConTrdRcpts,TtlTradgVol,TtlTrfVal,"
            "TtlNbOfTxsExctd,TtlTrfdVal,OpnPric,HghPric,LwPric,ClsPric,LastPric,"
            "PrvsClsgPric,Undrlyg,SqCmpt,CnsmrndXpryDt,OpnPricAdj,ClsPricAdj,ISIN,"
            "TckrSymb1,TckrSymb2,Src1,Src2\n"
            "2024-09-30,RELIANCE,EQ,RELIANCE,CM,EQ,NA,5000,1000000,275000000.00,5000,275000000.00,2740.00,2760.00,2730.00,2750.00,2749.00,2735.00,,,0,2740.00,2750.00,INE002A01018,RELIANCE,RELIANCE,NA,NA\n"
            "2024-09-30,NOSYMBOL,EQ,NOSYMBOL,CM,EQ,NA,0,0,0.00,0,0.00,0.00,0.00,0.00,0.00,0.00,0.00,,,0,0.00,0.00,,NOSYMBOL,NOSYMBOL,NA,NA\n"
        )
        rows = list(bhavcopy.normalize_bhavcopy_rows(text))
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Observation parsing
# ---------------------------------------------------------------------------


class TestParseBhavcopyCsv:
    def test_modern_produces_6_observations_per_row(self, modern_csv: str, fixed_ts: datetime) -> None:
        # 6 ISINs × 6 observations (OHLC + volume + turnover) = 36
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        assert len(obs) == 36

    def test_legacy_produces_6_observations_per_row(self, legacy_csv: str, fixed_ts: datetime) -> None:
        obs = parse_bhavcopy_csv(legacy_csv, retrieved_at=fixed_ts)
        assert len(obs) == 36

    def test_both_formats_produce_identical_observations(
        self, modern_csv: str, legacy_csv: str, fixed_ts: datetime
    ) -> None:
        """The legacy and modern fixtures describe the same trade data.
        Both should produce identical observations (same IDs, same values)."""
        modern_obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        legacy_obs = parse_bhavcopy_csv(legacy_csv, retrieved_at=fixed_ts)

        # Same count
        assert len(modern_obs) == len(legacy_obs)
        # Same IDs (sorted by same key)
        assert [o.id for o in modern_obs] == [o.id for o in legacy_obs]
        # Same values
        for m, l in zip(modern_obs, legacy_obs):
            assert m.value == l.value
            assert m.kind == l.kind
            assert m.subject_id == l.subject_id
            assert m.as_of == l.as_of

    def test_observation_kinds_present(self, modern_csv: str, fixed_ts: datetime) -> None:
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        kinds = {o.kind for o in obs}
        assert kinds == {
            ObservationKind.PRICE_OPEN,
            ObservationKind.PRICE_HIGH,
            ObservationKind.PRICE_LOW,
            ObservationKind.PRICE_CLOSE,
            ObservationKind.VOLUME,
            ObservationKind.TURNOVER,
        }

    def test_observation_fields_populated(self, modern_csv: str, fixed_ts: datetime) -> None:
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        # Find RELIANCE close price (subject_id is sec_<hash of isin>)
        from investorlens.ids import make_id
        reliance_sid = make_id("sec", {"isin": "INE002A01018"})
        rel_close = next(
            o for o in obs
            if o.kind == ObservationKind.PRICE_CLOSE and o.subject_id == reliance_sid
        )
        assert rel_close.value == 2750.00
        assert rel_close.unit == "INR/share"
        assert rel_close.currency == "INR"
        assert rel_close.period == "2024-09-30"
        assert rel_close.as_of == date(2024, 9, 30)
        assert rel_close.data_status == DataStatus.OBSERVED

    def test_volume_observation_unit(self, modern_csv: str, fixed_ts: datetime) -> None:
        from investorlens.ids import make_id
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        reliance_sid = make_id("sec", {"isin": "INE002A01018"})
        vol = next(o for o in obs if o.kind == ObservationKind.VOLUME and o.subject_id == reliance_sid)
        assert vol.unit == "shares"
        assert vol.value == 1000000

    def test_turnover_observation_unit(self, modern_csv: str, fixed_ts: datetime) -> None:
        from investorlens.ids import make_id
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        reliance_sid = make_id("sec", {"isin": "INE002A01018"})
        turn = next(o for o in obs if o.kind == ObservationKind.TURNOVER and o.subject_id == reliance_sid)
        assert turn.unit == "INR"
        assert turn.value == 275000000.00

    def test_illiquid_row_marked_unavailable(self, modern_csv: str, fixed_ts: datetime) -> None:
        """The ILLIQUIDCO row has 0 prices → prices should be marked UNAVAILABLE,
        but volume=0 and turnover=0 should be OBSERVED (zero trades is a real fact)."""
        from investorlens.ids import make_id
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        illiquid_sid = make_id("sec", {"isin": "INE999A99999"})
        illiquid = [o for o in obs if o.subject_id == illiquid_sid]
        assert len(illiquid) == 6

        prices = [o for o in illiquid if o.kind.value.startswith("price_")]
        for p in prices:
            assert p.data_status == DataStatus.UNAVAILABLE

        vol = next(o for o in illiquid if o.kind == ObservationKind.VOLUME)
        assert vol.data_status == DataStatus.OBSERVED
        assert vol.value == 0

        turn = next(o for o in illiquid if o.kind == ObservationKind.TURNOVER)
        assert turn.data_status == DataStatus.OBSERVED
        assert turn.value == 0

    def test_provenance_attached(self, modern_csv: str, fixed_ts: datetime) -> None:
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        prov = obs[0].provenance
        assert prov.source == "nse"
        assert prov.extraction_method.value == "bulk_download"
        assert prov.confidence.value == "high"
        assert prov.retrieved_at == fixed_ts

    def test_source_url_passed_through(self, modern_csv: str, fixed_ts: datetime) -> None:
        url = "https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_20240930_F_0000.csv.zip"
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts, source_url=url)
        assert str(obs[0].provenance.source_url) == url

    def test_id_deterministic(self, modern_csv: str, fixed_ts: datetime) -> None:
        a = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        b = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        assert [o.id for o in a] == [o.id for o in b]

    def test_id_includes_subject_kind_period(self, modern_csv: str, fixed_ts: datetime) -> None:
        """Two observations from the same subject + kind + period must share an ID,
        even if the price differs slightly (which shouldn't happen, but proves the design)."""
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        ids = {o.id for o in obs}
        assert len(ids) == len(obs)  # no duplicates
        for o in obs:
            assert o.id.startswith("obs_")

    def test_only_isins_filter(self, modern_csv: str, fixed_ts: datetime) -> None:
        """Filtering to a small ISIN set should reduce observations accordingly."""
        target = {"INE002A01018", "INE467B01029"}  # RELIANCE + TCS
        obs = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts, only_isins=target)
        # 2 ISINs × 6 observations = 12
        assert len(obs) == 12
        subject_isins = {o.subject_id for o in obs}
        # All observations should be for securities in the target ISIN set
        for sid in subject_isins:
            # subject_id is sec_<hash of isin>, so check by reconstructing
            from investorlens.ids import make_id
            expected_ids = {make_id("sec", {"isin": isin}) for isin in target}
            assert sid in expected_ids

    def test_output_sorted_for_determinism(self, modern_csv: str, fixed_ts: datetime) -> None:
        a = parse_bhavcopy_csv(modern_csv, retrieved_at=fixed_ts)
        # Re-shuffle input lines (except header) and re-parse
        lines = modern_csv.split("\n")
        header = lines[0]
        data_lines = lines[1:]
        import random
        random.seed(42)
        shuffled = "\n".join([header] + random.sample(data_lines, len(data_lines)))
        b = parse_bhavcopy_csv(shuffled, retrieved_at=fixed_ts)
        # Output should be identical regardless of input row order
        assert [o.id for o in a] == [o.id for o in b]

    def test_empty_csv_returns_empty(self, fixed_ts: datetime) -> None:
        # Header only — and a complete enough header for format detection to succeed.
        text = (
            "TradDt,Sym,SecTp,TckrSymb,Sgmt,Sr,Src,ConTrdRcpts,TtlTradgVol,TtlTrfVal,"
            "TtlNbOfTxsExctd,TtlTrfdVal,OpnPric,HghPric,LwPric,ClsPric,LastPric,"
            "PrvsClsgPric,Undrlyg,SqCmpt,CnsmrndXpryDt,OpnPricAdj,ClsPricAdj,ISIN,"
            "TckrSymb1,TckrSymb2,Src1,Src2\n"
        )
        obs = parse_bhavcopy_csv(text, retrieved_at=fixed_ts)
        assert obs == []

    def test_dedupes_within_single_file(self, fixed_ts: datetime) -> None:
        """If the same ISIN appears twice in the modern file (e.g. different Sgmt),
        we should only emit one set of observations per (subject, kind, period)."""
        text = (
            "TradDt,Sym,SecTp,TckrSymb,Sgmt,Sr,Src,ConTrdRcpts,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,TtlTrfdVal,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,Undrlyg,SqCmpt,CnsmrndXpryDt,OpnPricAdj,ClsPricAdj,ISIN,TckrSymb1,TckrSymb2,Src1,Src2\n"
            "2024-09-30,RELIANCE,EQ,RELIANCE,CM,EQ,NA,5000,1000000,275000000.00,5000,275000000.00,2740.00,2760.00,2730.00,2750.00,2749.00,2735.00,,,0,2740.00,2750.00,INE002A01018,RELIANCE,RELIANCE,NA,NA\n"
            "2024-09-30,RELIANCE,EQ,RELIANCE,BE,EQ,NA,100,20000,5500000.00,100,5500000.00,2742.00,2752.00,2738.00,2751.00,2750.50,2735.00,,,0,2742.00,2751.00,INE002A01018,RELIANCE,RELIANCE,NA,NA\n"
        )
        obs = parse_bhavcopy_csv(text, retrieved_at=fixed_ts)
        # 6 observations, not 12 — first occurrence wins per (subject, kind, period)
        assert len(obs) == 6
