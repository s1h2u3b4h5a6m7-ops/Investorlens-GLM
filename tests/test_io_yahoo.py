"""Tests for the Yahoo Finance chart API client (investorlens.io.yahoo).

We test the client by monkeypatching CachedSession.get to return a known
fixture response — no real HTTP.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from investorlens.io.yahoo import YahooChartClient, YahooError, to_yahoo_symbol

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def chart_response_bytes() -> bytes:
    return (FIXTURES / "yahoo_chart_reliance_5d.json").read_bytes()


class TestToYahooSymbol:
    def test_nse_symbol_preferred(self) -> None:
        assert to_yahoo_symbol(nse_symbol="RELIANCE", bse_code="500325") == "RELIANCE.NS"

    def test_bse_fallback(self) -> None:
        assert to_yahoo_symbol(nse_symbol=None, bse_code="500325") == "500325.BO"

    def test_uppercases_nse(self) -> None:
        assert to_yahoo_symbol(nse_symbol="reliance") == "RELIANCE.NS"

    def test_returns_none_if_neither(self) -> None:
        assert to_yahoo_symbol() is None


class TestYahooChartClient:
    def test_get_chart_returns_parsed_json(
        self,
        chart_response_bytes: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The client should parse the HTTP response body as JSON."""
        captured: dict = {}

        def fake_get(self, url, params=None, use_cache=True):
            captured["url"] = url
            captured["params"] = params
            return chart_response_bytes

        # Patch the underlying CachedSession.get
        from investorlens.io.http import CachedSession
        monkeypatch.setattr(CachedSession, "get", fake_get)

        with YahooChartClient(rate_limit_per_sec=10) as client:
            data = client.get_chart("RELIANCE.NS", interval="1d", range_="5d")

        assert "chart" in data
        assert data["chart"]["result"][0]["meta"]["symbol"] == "RELIANCE.NS"
        # Verify URL construction
        assert "RELIANCE.NS" in captured["url"]
        assert captured["params"] == {"interval": "1d", "range": "5d"}

    def test_get_chart_uses_period1_period2_when_given(
        self,
        chart_response_bytes: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict = {}

        def fake_get(self, url, params=None, use_cache=True):
            captured["params"] = params
            return chart_response_bytes

        from investorlens.io.http import CachedSession
        monkeypatch.setattr(CachedSession, "get", fake_get)

        with YahooChartClient(rate_limit_per_sec=10) as client:
            client.get_chart("RELIANCE.NS", period1=1727654400, period2=1728000000)

        assert captured["params"] == {
            "interval": "1d",
            "period1": 1727654400,
            "period2": 1728000000,
        }
        # range_ should NOT be in params when period1/2 are given
        assert "range" not in captured["params"]

    def test_get_chart_raises_on_invalid_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from investorlens.io.http import CachedSession
        monkeypatch.setattr(CachedSession, "get", lambda self, url, params=None, use_cache=True: b"not json")

        with YahooChartClient(rate_limit_per_sec=10) as client:
            with pytest.raises(YahooError, match="not valid JSON"):
                client.get_chart("RELIANCE.NS")

    def test_get_chart_raises_on_yahoo_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from investorlens.io.http import CachedSession
        bad_response = b'{"chart": {"result": [], "error": {"code": "Bad Request", "description": "Invalid symbol"}}}'
        monkeypatch.setattr(CachedSession, "get", lambda self, url, params=None, use_cache=True: bad_response)

        with YahooChartClient(rate_limit_per_sec=10) as client:
            with pytest.raises(YahooError, match="Yahoo API error"):
                client.get_chart("INVALID.NS")

    def test_get_chart_raises_on_empty_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from investorlens.io.http import CachedSession
        empty = b'{"chart": {"result": [], "error": null}}'
        monkeypatch.setattr(CachedSession, "get", lambda self, url, params=None, use_cache=True: empty)

        with YahooChartClient(rate_limit_per_sec=10) as client:
            with pytest.raises(YahooError, match="no result"):
                client.get_chart("RELIANCE.NS")

    def test_get_chart_raises_on_missing_chart(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from investorlens.io.http import CachedSession
        monkeypatch.setattr(CachedSession, "get", lambda self, url, params=None, use_cache=True: b'{"foo": "bar"}')

        with YahooChartClient(rate_limit_per_sec=10) as client:
            with pytest.raises(YahooError, match="missing 'chart'"):
                client.get_chart("RELIANCE.NS")

    def test_context_manager_closes_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        closed = {"called": False}
        original_close = None

        from investorlens.io.http import CachedSession

        def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(CachedSession, "close", fake_close)

        with YahooChartClient(rate_limit_per_sec=10):
            pass
        assert closed["called"] is True
