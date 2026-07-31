"""
Thin Yahoo Finance Chart API client.

Yahoo publishes historical OHLCV data via a public (no API key required) endpoint:

    GET https://query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>
        ?interval=1d&range=5d

We use this directly rather than depending on the `yfinance` library because:
  - yfinance adds ~50 MB of transitive deps (pandas, numpy, curl_cffi, ...).
  - yfinance's cookie-and-crumb dance is brittle and frequently breaks.
  - The Chart API returns clean JSON we can parse ourselves in ~30 lines.

This module handles HTTP only. Parsing of the JSON response into Observation
records lives in `investorlens.parsers.yahoo` (pure function, testable).

Indian ticker mapping:
  - NSE symbols: append ".NS"  (e.g. RELIANCE → RELIANCE.NS)
  - BSE codes:   append ".BO"  (e.g. 524715 → 524715.BO)

Rate limiting: Yahoo is sensitive; default ≤ 1 req/sec.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .http import CachedSession, FetchError

__all__ = ["YahooChartClient", "YahooError", "to_yahoo_symbol"]


log = logging.getLogger(__name__)

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooError(RuntimeError):
    """Raised when the Yahoo Finance API returns an error or unexpected response."""


def to_yahoo_symbol(nse_symbol: str | None = None, bse_code: str | None = None) -> str | None:
    """Convert an NSE symbol or BSE code to a Yahoo Finance ticker.

    Prefer NSE (.NS) because Yahoo's NSE coverage is generally better.
    Fall back to BSE (.BO) if only BSE is available.

    Returns None if neither is provided.
    """
    if nse_symbol:
        return f"{nse_symbol.upper()}.NS"
    if bse_code:
        return f"{bse_code}.BO"
    return None


class YahooChartClient:
    """Client for the Yahoo Finance v8 chart API.

    Wraps CachedSession for rate limiting, retries, and per-date caching.
    All responses are cached under data/raw/yahoo/<date>/ so re-runs on the
    same day don't re-hit the network.
    """

    def __init__(
        self,
        *,
        rate_limit_per_sec: float = 1.0,
        max_retries: int = 3,
        timeout: float = 30.0,
        cache_root=None,
    ) -> None:
        # We piggyback on CachedSession (already handles rate-limiting, retries,
        # browser-like headers, atomic caching).
        self._session = CachedSession(
            source_slug="yahoo",
            rate_limit_per_sec=rate_limit_per_sec,
            max_retries=max_retries,
            timeout=timeout,
            cache_root=cache_root,
        )

    def get_chart(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        range_: str = "5d",
        period1: int | None = None,
        period2: int | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Fetch the chart data for a Yahoo ticker.

        Args:
            symbol: Yahoo ticker, e.g. "RELIANCE.NS".
            interval: bar interval — "1d", "1wk", "1mo".
            range_: how far back to look — "5d", "1mo", "3mo", "1y", "5y", "max".
                Ignored if period1/period2 are given.
            period1, period2: explicit Unix timestamps for start/end.
                When provided, `range_` is ignored.
            use_cache: if True, return cached response if available for today.

        Returns:
            Parsed JSON dict from Yahoo's response. The chart data is under
            result["chart"]["result"][0].

        Raises:
            YahooError: if Yahoo returns no data, an error, or an unexpected shape.
            FetchError: if the HTTP fetch fails after retries.
        """
        url = _CHART_URL.format(symbol=symbol)
        params: dict[str, Any] = {"interval": interval}
        if period1 is not None and period2 is not None:
            params["period1"] = period1
            params["period2"] = period2
        else:
            params["range"] = range_

        body = self._session.get(url, params=params, use_cache=use_cache)
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise YahooError(f"Yahoo response was not valid JSON: {e}") from e

        # Yahoo wraps everything in {"chart": {"result": [...], "error": null}}
        chart = data.get("chart")
        if chart is None:
            raise YahooError(f"Yahoo response missing 'chart' key: {str(data)[:300]}")
        if chart.get("error"):
            err = chart["error"]
            raise YahooError(f"Yahoo API error for {symbol}: {err}")
        result = chart.get("result")
        if not result:
            raise YahooError(f"Yahoo returned no result for {symbol}")
        return data

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "YahooChartClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
