"""
Parser for Yahoo Finance Chart API responses.

Input: a dict (parsed JSON) from Yahoo's v8 chart API.
Output: a list of `Observation` records (one per (kind, day)).

Yahoo's response shape (abridged):
    {
      "chart": {
        "result": [{
          "meta": {"symbol": "RELIANCE.NS", "currency": "INR", ...},
          "timestamp": [1727654400, 1727740800, ...],
          "indicators": {
            "quote": [{
              "open": [...], "high": [...], "low": [...],
              "close": [...], "volume": [...]
            }],
            "adjclose": [{"adjclose": [...]}]
          }
        }],
        "error": null
      }
    }

We emit one Observation per (kind, day). Kinds:
  - price_open, price_high, price_low, price_close  (raw, unadjusted)
  - price_close_adj  (split + dividend adjusted; only if adjclose present)
  - volume

The subject_id is the Security ID, derived from the Yahoo ticker symbol.
Because Yahoo tickers aren't ISINs, the caller must supply an explicit
`subject_id` (typically the ISIN-derived sec_<hash>). This keeps the parser
pure and lets the fetcher do the symbol → ISIN lookup.

Pure function: takes dict + args, returns list[Observation]. No I/O.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ..ids import make_id
from ..models import DataStatus, Observation, ObservationKind, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = ["parse_yahoo_chart", "extract_meta", "extract_ohlcv_series"]


def extract_meta(response: dict[str, Any]) -> dict[str, Any]:
    """Pull the 'meta' block from a Yahoo chart response. Raises ValueError if malformed."""
    chart = response.get("chart")
    if not chart or not isinstance(chart, dict):
        raise ValueError("Yahoo response missing 'chart' object")
    if chart.get("error"):
        raise ValueError(f"Yahoo API error: {chart['error']}")
    result = chart.get("result")
    if not result or not isinstance(result, list):
        raise ValueError("Yahoo response missing 'chart.result' list")
    first = result[0]
    if not isinstance(first, dict):
        raise ValueError("Yahoo response 'chart.result[0]' is not a dict")
    meta = first.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("Yahoo response missing 'meta' dict")
    return meta


def extract_ohlcv_series(response: dict[str, Any]) -> dict[str, list]:
    """Extract aligned (timestamp, open, high, low, close, adjclose, volume) lists.

    Returns a dict with keys: timestamps (list[date]), open, high, low, close,
    adjclose, volume (each a list of float|None, same length as timestamps).

    Adjclose is None for entries where Yahoo didn't provide adjusted close.

    Raises ValueError if the response is malformed.
    """
    chart = response.get("chart", {})
    result_list = chart.get("result", [])
    if not result_list:
        raise ValueError("Yahoo response missing 'chart.result'")
    result = result_list[0]

    raw_ts = result.get("timestamp") or []
    timestamps: list[date] = []
    for ts in raw_ts:
        if ts is None:
            timestamps.append(None)  # type: ignore[arg-type]
            continue
        try:
            # Yahoo timestamps are Unix seconds, UTC.
            timestamps.append(datetime.fromtimestamp(int(ts), tz=timezone.utc).date())
        except (ValueError, OSError, OverflowError):
            timestamps.append(None)  # type: ignore[arg-type]

    indicators = result.get("indicators") or {}
    quote_list = indicators.get("quote") or []
    quote = quote_list[0] if quote_list else {}
    adjclose_list = indicators.get("adjclose") or []
    adjclose = (adjclose_list[0] if adjclose_list else {}).get("adjclose") or []

    n = len(timestamps)
    open_ = _pad_to(quote.get("open") or [], n)
    high = _pad_to(quote.get("high") or [], n)
    low = _pad_to(quote.get("low") or [], n)
    close = _pad_to(quote.get("close") or [], n)
    volume = _pad_to(quote.get("volume") or [], n)
    adjclose_padded = _pad_to(adjclose, n)

    return {
        "timestamps": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "adjclose": adjclose_padded,
        "volume": volume,
    }


def _pad_to(values: list, n: int) -> list:
    """Pad or truncate a list to length n. Missing slots become None."""
    if len(values) >= n:
        return list(values[:n])
    return list(values) + [None] * (n - len(values))


def parse_yahoo_chart(
    response: dict[str, Any],
    *,
    subject_id: str,
    retrieved_at: datetime | None = None,
    source_url: str | None = None,
    yahoo_symbol: str | None = None,
) -> list[Observation]:
    """Parse a Yahoo Finance chart API response into Observation records.

    Each day produces up to 6 observations (one per kind):
      price_open, price_high, price_low, price_close, price_close_adj, volume

    Days with no trades (e.g. weekends/holidays in Yahoo's response) are
    skipped if all OHLCV values are None.

    Args:
        response: parsed JSON dict from Yahoo.
        subject_id: the Security ID these observations refer to. REQUIRED —
            the parser cannot infer it from the Yahoo ticker alone.
        retrieved_at: UTC timestamp for provenance. Defaults to now().
        source_url: optional source URL for provenance.
        yahoo_symbol: the Yahoo ticker (e.g. "RELIANCE.NS") used for the fetch.
            Stored in provenance notes for traceability.

    Returns:
        Sorted list of Observation records (sorted by subject_id, kind, as_of).
    """
    meta = extract_meta(response)
    series = extract_ohlcv_series(response)

    currency = (meta.get("currency") or "INR").upper()
    notes = f"Yahoo Finance symbol: {yahoo_symbol}" if yahoo_symbol else "Yahoo Finance chart API"

    prov_kwargs: dict = {
        "source": "yahoo",
        "extraction_method": ExtractionMethod.OFFICIAL_API,
        "confidence": Confidence.HIGH,
        "notes": notes,
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    if source_url:
        prov_kwargs["source_url"] = source_url
    base_prov = Provenance(**prov_kwargs)

    observations: list[Observation] = []
    seen: set[tuple[str, str, str]] = set()

    n = len(series["timestamps"])
    for i in range(n):
        d = series["timestamps"][i]
        if d is None:
            continue

        # Skip rows where ALL OHLCV are None (genuinely no data for that day).
        if all(
            series[k][i] is None
            for k in ("open", "high", "low", "close", "adjclose", "volume")
        ):
            continue

        specs = [
            (ObservationKind.PRICE_OPEN, series["open"][i], "INR/share"),
            (ObservationKind.PRICE_HIGH, series["high"][i], "INR/share"),
            (ObservationKind.PRICE_LOW, series["low"][i], "INR/share"),
            (ObservationKind.PRICE_CLOSE, series["close"][i], "INR/share"),
            (ObservationKind.PRICE_CLOSE_ADJ, series["adjclose"][i], "INR/share"),
            (ObservationKind.VOLUME, series["volume"][i], "shares"),
        ]
        for kind, value, unit in specs:
            # Skip adjclose entirely if not present (some instruments have no adjclose).
            if kind == ObservationKind.PRICE_CLOSE_ADJ and value is None:
                continue

            key = (subject_id, kind.value, d.isoformat())
            if key in seen:
                continue
            seen.add(key)

            data_status = DataStatus.OBSERVED
            # Treat None prices as unavailable (preserves the date but flags the gap).
            if value is None and kind != ObservationKind.VOLUME:
                data_status = DataStatus.UNAVAILABLE

            observations.append(
                Observation(
                    subject_id=subject_id,
                    kind=kind,
                    period=d.isoformat(),
                    as_of=d,
                    value=value,
                    unit=unit,
                    currency=currency if unit != "shares" else None,
                    data_status=data_status,
                    confidence=base_prov.confidence,
                    provenance=base_prov,
                )
            )

    # Deterministic sort.
    observations.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return observations
