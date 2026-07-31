"""
NSE Equity Bhavcopy parser.

NSE has published bhavcopy in two formats over the years:

1. **Legacy format** (pre-2024, still used for some historical archives):
   Columns: SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE,
            TOTTRDQTY, TOTTRDVAL, TIMESTAMP, TOTALTRADES, ISIN

2. **Modern (UDiFF) format** (late 2024 onwards):
   Columns: TradDt, Sym, SecTp, TckrSymb, Sgmt, Sr, Src, ConTrdRcpts,
            TtlTradgVol, TtlTrfVal, TtlNbOfTxsExctd, TtlTrfdVal,
            OpnPric, HghPric, LwPric, ClsPric, LastPric, PrvsClsgPric,
            Undrlyg, SqCmpt, CnsmrndXpryDt, OpnPricAdj, ClsPricAdj, ISIN, ...

This parser handles BOTH formats. Format is auto-detected from the header.
Each row produces 6 Observation records:
  price_open, price_high, price_low, price_close, volume, turnover

Pure function: takes CSV text, returns list[Observation]. No I/O, no network.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

from ..ids import make_id
from ..models import DataStatus, Observation, ObservationKind, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = [
    "parse_bhavcopy_csv",
    "detect_format",
    "BhavcopyFormat",
    "BhavcopyRow",
    "normalize_bhavcopy_rows",
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class BhavcopyFormat:
    LEGACY = "legacy"
    MODERN = "modern"
    UNKNOWN = "unknown"


# Headers that distinguish the two formats. We check the FIRST data row's keys
# (case-insensitive) for any of these telltale column names.
_LEGACY_TELLTALES = {
    "SYMBOL", "SERIES", "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP",
    "TOTALTRADES", "LAST",
}
_MODERN_TELLTALES = {
    "TRADDT", "TCKRSYMB", "TTLTRADGVOL", "TTLTRFVAL", "OPNPRIC", "CLSPRIC",
    "SGMT", "HGHPRIC", "LWPRIC", "PRVSCLSGPRIC",
}


def detect_format(header_keys: list[str]) -> str:
    """Detect whether a bhavcopy CSV is legacy or modern format.

    Args:
        header_keys: list of raw column names from the CSV header.

    Returns:
        One of BhavcopyFormat.LEGACY, .MODERN, or .UNKNOWN.
    """
    upper = {k.strip().upper() for k in header_keys if k}
    legacy_hits = len(upper & _LEGACY_TELLTALES)
    modern_hits = len(upper & _MODERN_TELLTALES)
    # Require at least 3 telltales to confirm a format — enough to disambiguate
    # while tolerating a few missing columns in test fixtures or abridged files.
    if modern_hits >= 3 and modern_hits > legacy_hits:
        return BhavcopyFormat.MODERN
    if legacy_hits >= 3 and legacy_hits > modern_hits:
        return BhavcopyFormat.LEGACY
    return BhavcopyFormat.UNKNOWN


# ---------------------------------------------------------------------------
# Normalized row — the unified shape both formats reduce to
# ---------------------------------------------------------------------------


class BhavcopyRow:
    """A normalized bhavcopy row. Independent of the source CSV format.

    Fields:
      trade_date:   the date this row refers to
      symbol:       NSE trading symbol
      isin:         ISIN of the security
      series:       NSE series (EQ, BE, etc.) — legacy only; "EQ" assumed for modern
      open/high/low/close: OHLC prices (may be None if no trades)
      last:         last traded price (may be None)
      prev_close:   previous close (for change calculations)
      volume:       total traded quantity (shares)
      turnover:     total traded value (INR)
      trades:       total number of trades
    """

    __slots__ = (
        "trade_date", "symbol", "isin", "series",
        "open", "high", "low", "close", "last", "prev_close",
        "volume", "turnover", "trades",
    )

    def __init__(
        self,
        *,
        trade_date: date,
        symbol: str,
        isin: str,
        series: str = "EQ",
        open: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float | None = None,
        last: float | None = None,
        prev_close: float | None = None,
        volume: float | None = None,
        turnover: float | None = None,
        trades: int | None = None,
    ) -> None:
        self.trade_date = trade_date
        self.symbol = symbol
        self.isin = isin
        self.series = series
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.last = last
        self.prev_close = prev_close
        self.volume = volume
        self.turnover = turnover
        self.trades = trades


# ---------------------------------------------------------------------------
# Format-specific normalizers
# ---------------------------------------------------------------------------


def _parse_decimal(s: str | None) -> float | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s in {"-", "NA", "N/A", "NaN"}:
        return None
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        return None


def _parse_int(s: str | None) -> int | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s in {"-", "NA", "N/A"}:
        return None
    try:
        return int(Decimal(s))
    except (InvalidOperation, ValueError):
        return None


def _parse_legacy_date(s: str | None) -> date | None:
    """Legacy TIMESTAMP is like '30-SEP-2024'."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.upper(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_modern_date(s: str | None) -> date | None:
    """Modern TradDt is ISO: '2024-09-30'."""
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return _parse_legacy_date(s)  # be tolerant


def _normalize_legacy_row(row: dict[str, str]) -> BhavcopyRow | None:
    """Normalize a legacy-format CSV row to a BhavcopyRow. Returns None if invalid."""
    isin = (row.get("ISIN") or "").strip().upper()
    symbol = (row.get("SYMBOL") or "").strip()
    if not isin or not symbol:
        return None

    trade_date = _parse_legacy_date(row.get("TIMESTAMP"))
    if trade_date is None:
        return None

    # Filter to equity series (EQ) and a few related; skip debt/derivatives.
    series = (row.get("SERIES") or "EQ").strip().upper()
    if series not in {"EQ", "BE", "BZ", "SM", "ST"}:
        return None

    return BhavcopyRow(
        trade_date=trade_date,
        symbol=symbol,
        isin=isin,
        series=series,
        open=_parse_decimal(row.get("OPEN")),
        high=_parse_decimal(row.get("HIGH")),
        low=_parse_decimal(row.get("LOW")),
        close=_parse_decimal(row.get("CLOSE")),
        last=_parse_decimal(row.get("LAST")),
        prev_close=_parse_decimal(row.get("PREVCLOSE")),
        volume=_parse_decimal(row.get("TOTTRDQTY")),
        turnover=_parse_decimal(row.get("TOTTRDVAL")),
        trades=_parse_int(row.get("TOTALTRADES")),
    )


def _normalize_modern_row(row: dict[str, str]) -> BhavcopyRow | None:
    """Normalize a modern-format CSV row to a BhavcopyRow. Returns None if invalid."""
    isin = (row.get("ISIN") or "").strip().upper()
    symbol = (row.get("TckrSymb") or row.get("Sym") or "").strip()
    if not isin or not symbol:
        return None

    trade_date = _parse_modern_date(row.get("TradDt"))
    if trade_date is None:
        return None

    # Modern bhavcopy covers multiple segments. Only equity "CM" / "EQ" is relevant here.
    seg = (row.get("Sgmt") or row.get("SecTp") or "").strip().upper()
    if seg and seg not in {"CM", "EQ", "BE", "BZ", "SM", "ST", ""}:
        return None

    series = (row.get("Sr") or "EQ").strip().upper()

    return BhavcopyRow(
        trade_date=trade_date,
        symbol=symbol,
        isin=isin,
        series=series or "EQ",
        open=_parse_decimal(row.get("OpnPric")),
        high=_parse_decimal(row.get("HghPric")),
        low=_parse_decimal(row.get("LwPric")),
        close=_parse_decimal(row.get("ClsPric")),
        last=_parse_decimal(row.get("LastPric")),
        prev_close=_parse_decimal(row.get("PrvsClsgPric")),
        volume=_parse_decimal(row.get("TtlTradgVol")),
        turnover=_parse_decimal(row.get("TtlTrfVal")),
        trades=_parse_int(row.get("TtlNbOfTxsExctd")),
    )


def normalize_bhavcopy_rows(csv_text: str) -> Iterator[BhavcopyRow]:
    """Iterate normalized BhavcopyRows from a CSV (legacy or modern).

    Format is detected from the header row. Unknown formats raise ValueError.
    Rows missing required fields (ISIN, symbol, valid date) are silently skipped.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return  # empty CSV

    fmt = detect_format(list(reader.fieldnames))
    if fmt == BhavcopyFormat.UNKNOWN:
        raise ValueError(
            f"Could not detect bhavcopy format from header: {reader.fieldnames}. "
            f"Expected legacy (SYMBOL,SERIES,...) or modern (TradDt,TckrSymb,...) format."
        )

    normalizer = _normalize_legacy_row if fmt == BhavcopyFormat.LEGACY else _normalize_modern_row
    for row in reader:
        # Strip whitespace from keys/values for tolerance.
        cleaned = {k.strip() if k else k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        normalized = normalizer(cleaned)
        if normalized is not None:
            yield normalized


# ---------------------------------------------------------------------------
# BhavcopyRow → Observation records
# ---------------------------------------------------------------------------


def _subject_id_for_isin(isin: str) -> str:
    """Compute the Security ID for an ISIN.

    The Security model derives its ID from {isin}, so the same formula
    works whether or not the security has been formally registered in the
    ISIN master yet. This is intentional: we don't lose price data just
    because the ISIN master is stale.
    """
    return make_id("sec", {"isin": isin})


def _make_observation(
    *,
    subject_id: str,
    kind: ObservationKind,
    trade_date: date,
    value: float | None,
    unit: str,
    prov: Provenance,
    data_status: DataStatus = DataStatus.OBSERVED,
) -> Observation:
    """Construct a single Observation. Returns None if value is None and the
    kind is a price (no-trade days for illiquid securities).
    """
    # For volume / turnover, a value of 0 is meaningful (no trades happened).
    # For prices, a None or 0 on a no-trade day should be marked unavailable.
    if kind in (ObservationKind.PRICE_OPEN, ObservationKind.PRICE_HIGH, ObservationKind.PRICE_LOW, ObservationKind.PRICE_CLOSE):
        if value is None or value == 0:
            data_status = DataStatus.UNAVAILABLE

    return Observation(
        subject_id=subject_id,
        kind=kind,
        period=trade_date.isoformat(),
        as_of=trade_date,
        value=value,
        unit=unit,
        currency="INR" if unit in {"INR", "INR/share"} else None,
        data_status=data_status,
        confidence=prov.confidence,
        provenance=prov,
    )


def parse_bhavcopy_csv(
    csv_text: str,
    *,
    retrieved_at: datetime | None = None,
    source_url: str | None = None,
    only_isins: set[str] | None = None,
) -> list[Observation]:
    """Parse an NSE Equity bhavcopy CSV into a list of Observation records.

    Each bhavcopy row produces 6 observations:
      price_open, price_high, price_low, price_close, volume, turnover

    Args:
        csv_text: raw CSV text (already decompressed from the zip).
        retrieved_at: UTC timestamp for provenance. Defaults to now().
        source_url: URL of the source zip (for provenance).
        only_isins: optional filter — only emit observations for these ISINs.
            Useful for backfill testing on a small subset.

    Returns:
        List of Observation records. Sorted by (subject_id, kind, as_of)
        for deterministic output.
    """
    prov_kwargs: dict = {
        "source": "nse",
        "extraction_method": ExtractionMethod.BULK_DOWNLOAD,
        "confidence": Confidence.HIGH,
        "reporting_period": "current",
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    if source_url:
        prov_kwargs["source_url"] = source_url
    base_prov = Provenance(**prov_kwargs)

    observations: list[Observation] = []
    seen_keys: set[tuple[str, str, str]] = set()  # (subject_id, kind, period)

    for row in normalize_bhavcopy_rows(csv_text):
        if only_isins is not None and row.isin not in only_isins:
            continue

        subject_id = _subject_id_for_isin(row.isin)
        # Each row gives us 6 distinct observations on the same trade date.
        # Note: the Observation model's ID is derived from
        # (subject_id, kind, period, as_of, source_id) so duplicates are
        # automatically deduplicated by the model itself — but we also
        # skip explicitly to avoid wasting memory on duplicates within a single file
        # (e.g. if NSE lists the same ISIN under multiple series in the modern format).
        specs: list[tuple[ObservationKind, float | None, str]] = [
            (ObservationKind.PRICE_OPEN, row.open, "INR/share"),
            (ObservationKind.PRICE_HIGH, row.high, "INR/share"),
            (ObservationKind.PRICE_LOW, row.low, "INR/share"),
            (ObservationKind.PRICE_CLOSE, row.close, "INR/share"),
            (ObservationKind.VOLUME, row.volume, "shares"),
            (ObservationKind.TURNOVER, row.turnover, "INR"),
        ]
        for kind, value, unit in specs:
            key = (subject_id, kind.value, row.trade_date.isoformat())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            observations.append(
                _make_observation(
                    subject_id=subject_id,
                    kind=kind,
                    trade_date=row.trade_date,
                    value=value,
                    unit=unit,
                    prov=base_prov,
                )
            )

    # Deterministic ordering for idempotent output.
    observations.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return observations
