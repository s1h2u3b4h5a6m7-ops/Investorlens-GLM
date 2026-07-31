"""Tests for the Yahoo Finance chart parser (investorlens.parsers.yahoo)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investorlens.models import DataStatus, ObservationKind
from investorlens.parsers import yahoo

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def chart_response() -> dict:
    return json.loads((FIXTURES / "yahoo_chart_reliance_5d.json").read_text(encoding="utf-8"))


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def subject_id() -> str:
    """RELIANCE ISIN is INE002A01018 — the Security ID derived from it."""
    from investorlens.ids import make_id
    return make_id("sec", {"isin": "INE002A01018"})


class TestExtractMeta:
    def test_returns_meta_dict(self, chart_response: dict) -> None:
        meta = yahoo.extract_meta(chart_response)
        assert meta["symbol"] == "RELIANCE.NS"
        assert meta["currency"] == "INR"
        assert meta["exchangeName"] == "NSI"

    def test_raises_on_error(self) -> None:
        bad = {"chart": {"result": [], "error": {"code": "Bad Request", "description": "Invalid symbol"}}}
        with pytest.raises(ValueError, match="Yahoo API error"):
            yahoo.extract_meta(bad)

    def test_raises_on_missing_chart(self) -> None:
        with pytest.raises(ValueError, match="missing 'chart'"):
            yahoo.extract_meta({})

    def test_raises_on_missing_result(self) -> None:
        # chart present but no result list
        with pytest.raises(ValueError, match="missing 'chart.result'"):
            yahoo.extract_meta({"chart": {"result": None}})


class TestExtractOhlcvSeries:
    def test_returns_aligned_lists(self, chart_response: dict) -> None:
        s = yahoo.extract_ohlcv_series(chart_response)
        assert len(s["timestamps"]) == 5
        assert len(s["open"]) == 5
        assert len(s["high"]) == 5
        assert len(s["low"]) == 5
        assert len(s["close"]) == 5
        assert len(s["adjclose"]) == 5
        assert len(s["volume"]) == 5

    def test_first_timestamp_parsed_as_date(self, chart_response: dict) -> None:
        s = yahoo.extract_ohlcv_series(chart_response)
        # 1727654400 = 2024-09-30 in UTC
        assert s["timestamps"][0] == date(2024, 9, 30)

    def test_values_match_fixture(self, chart_response: dict) -> None:
        s = yahoo.extract_ohlcv_series(chart_response)
        assert s["open"][0] == 2740.0
        assert s["high"][0] == 2760.0
        assert s["low"][0] == 2730.0
        assert s["close"][0] == 2750.0
        assert s["volume"][0] == 1000000
        assert s["adjclose"][0] == 2745.0

    def test_pads_short_arrays(self) -> None:
        # If Yahoo returns arrays of different lengths, pad with None.
        response = {
            "chart": {
                "result": [{
                    "timestamp": [1, 2, 3, 4, 5],
                    "indicators": {
                        "quote": [{"open": [10, 20]}],  # only 2 values for 5 timestamps
                        "adjclose": [],
                    }
                }]
            }
        }
        s = yahoo.extract_ohlcv_series(response)
        assert len(s["open"]) == 5
        assert s["open"][0] == 10
        assert s["open"][1] == 20
        assert s["open"][2] is None
        assert s["open"][3] is None
        assert s["open"][4] is None
        assert len(s["adjclose"]) == 5
        assert all(v is None for v in s["adjclose"])


class TestParseYahooChart:
    def test_produces_30_observations_for_5_days(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        """5 days × 6 kinds = 30 observations (assuming all OHLCV+adjclose present)."""
        obs = yahoo.parse_yahoo_chart(
            chart_response, subject_id=subject_id, retrieved_at=fixed_ts, yahoo_symbol="RELIANCE.NS"
        )
        assert len(obs) == 30

    def test_kinds_present(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        obs = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        kinds = {o.kind for o in obs}
        assert kinds == {
            ObservationKind.PRICE_OPEN,
            ObservationKind.PRICE_HIGH,
            ObservationKind.PRICE_LOW,
            ObservationKind.PRICE_CLOSE,
            ObservationKind.PRICE_CLOSE_ADJ,
            ObservationKind.VOLUME,
        }

    def test_first_day_observations(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        obs = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        # Filter to first day (2024-09-30)
        day1 = [o for o in obs if o.as_of == date(2024, 9, 30)]
        assert len(day1) == 6

        by_kind = {o.kind: o for o in day1}
        assert by_kind[ObservationKind.PRICE_OPEN].value == 2740.0
        assert by_kind[ObservationKind.PRICE_HIGH].value == 2760.0
        assert by_kind[ObservationKind.PRICE_LOW].value == 2730.0
        assert by_kind[ObservationKind.PRICE_CLOSE].value == 2750.0
        assert by_kind[ObservationKind.PRICE_CLOSE_ADJ].value == 2745.0
        assert by_kind[ObservationKind.VOLUME].value == 1000000

    def test_currency_attached_to_prices_not_volume(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        obs = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        for o in obs:
            if o.kind == ObservationKind.VOLUME:
                assert o.currency is None
            else:
                assert o.currency == "INR"

    def test_units(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        obs = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        for o in obs:
            if o.kind == ObservationKind.VOLUME:
                assert o.unit == "shares"
            else:
                assert o.unit == "INR/share"

    def test_provenance_attached(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        obs = yahoo.parse_yahoo_chart(
            chart_response,
            subject_id=subject_id,
            retrieved_at=fixed_ts,
            yahoo_symbol="RELIANCE.NS",
            source_url="https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS",
        )
        prov = obs[0].provenance
        assert prov.source == "yahoo"
        assert prov.extraction_method.value == "official_api"
        assert prov.confidence.value == "high"
        assert prov.retrieved_at == fixed_ts
        assert "RELIANCE.NS" in (prov.notes or "")
        assert "yahoo" in str(prov.source_url).lower()

    def test_id_deterministic(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        a = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        b = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        assert [o.id for o in a] == [o.id for o in b]

    def test_id_includes_subject_kind_period(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        """Each observation has a unique (subject, kind, period) — no duplicates."""
        obs = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        keys = {(o.subject_id, o.kind.value, o.period) for o in obs}
        assert len(keys) == len(obs)

    def test_output_sorted(
        self, chart_response: dict, subject_id: str, fixed_ts: datetime
    ) -> None:
        obs = yahoo.parse_yahoo_chart(chart_response, subject_id=subject_id, retrieved_at=fixed_ts)
        keys = [(o.subject_id, o.kind.value, o.as_of.isoformat()) for o in obs]
        assert keys == sorted(keys)

    def test_skips_days_with_all_none(
        self, subject_id: str, fixed_ts: datetime
    ) -> None:
        """If a day has all-None OHLCV (e.g. weekend/holiday), skip it entirely."""
        response = {
            "chart": {
                "result": [{
                    "meta": {"symbol": "X.NS", "currency": "INR"},
                    "timestamp": [1727654400, 1727740800],
                    "indicators": {
                        "quote": [{
                            "open": [100.0, None],
                            "high": [101.0, None],
                            "low": [99.0, None],
                            "close": [100.5, None],
                            "volume": [1000, None],
                        }],
                        "adjclose": [{"adjclose": [100.4, None]}],
                    }
                }]
            }
        }
        obs = yahoo.parse_yahoo_chart(response, subject_id=subject_id, retrieved_at=fixed_ts)
        # Only the first day should produce observations.
        assert len(obs) == 6
        for o in obs:
            assert o.as_of == date(2024, 9, 30)

    def test_adjclose_missing_skipped(
        self, subject_id: str, fixed_ts: datetime
    ) -> None:
        """If adjclose is absent, only 5 observations per day (not 6)."""
        response = {
            "chart": {
                "result": [{
                    "meta": {"symbol": "X.NS", "currency": "INR"},
                    "timestamp": [1727654400],
                    "indicators": {
                        "quote": [{
                            "open": [100.0], "high": [101.0], "low": [99.0],
                            "close": [100.5], "volume": [1000],
                        }],
                        # No adjclose
                    }
                }]
            }
        }
        obs = yahoo.parse_yahoo_chart(response, subject_id=subject_id, retrieved_at=fixed_ts)
        assert len(obs) == 5
        assert not any(o.kind == ObservationKind.PRICE_CLOSE_ADJ for o in obs)

    def test_none_price_marked_unavailable(
        self, subject_id: str, fixed_ts: datetime
    ) -> None:
        """If a single price field is None (but other fields aren't), emit an
        UNAVAILABLE observation rather than skipping."""
        response = {
            "chart": {
                "result": [{
                    "meta": {"symbol": "X.NS", "currency": "INR"},
                    "timestamp": [1727654400],
                    "indicators": {
                        "quote": [{
                            "open": [100.0], "high": [None], "low": [99.0],
                            "close": [100.5], "volume": [1000],
                        }],
                        "adjclose": [{"adjclose": [100.4]}],
                    }
                }]
            }
        }
        obs = yahoo.parse_yahoo_chart(response, subject_id=subject_id, retrieved_at=fixed_ts)
        high = next(o for o in obs if o.kind == ObservationKind.PRICE_HIGH)
        assert high.data_status == DataStatus.UNAVAILABLE
        assert high.value is None
        # Other prices should still be observed.
        open_ = next(o for o in obs if o.kind == ObservationKind.PRICE_OPEN)
        assert open_.data_status == DataStatus.OBSERVED


class TestParseYahooChartEdgeCases:
    def test_empty_result_raises(self, subject_id: str, fixed_ts: datetime) -> None:
        with pytest.raises(ValueError):
            yahoo.parse_yahoo_chart({"chart": {"result": []}}, subject_id=subject_id, retrieved_at=fixed_ts)

    def test_malformed_response_raises(self, subject_id: str, fixed_ts: datetime) -> None:
        with pytest.raises(ValueError):
            yahoo.parse_yahoo_chart({}, subject_id=subject_id, retrieved_at=fixed_ts)
