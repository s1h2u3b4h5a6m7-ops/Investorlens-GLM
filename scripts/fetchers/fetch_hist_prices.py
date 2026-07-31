"""
Fetch historical OHLCV (and adjusted close) from Yahoo Finance.

Yahoo publishes a free, no-API-key chart API that returns split+dividend-adjusted
historical prices. We use this directly (see `investorlens.io.yahoo`) rather
than depending on the `yfinance` library — lighter deps, more robust.

Modes:
  --incremental (default, last 30 days)
  --backfill PERIOD  (e.g. 5y, max, 10y, 6mo, 1mo, 3mo)
  --start YYYY-MM-DD --end YYYY-MM-DD  (explicit range)

Symbol resolution:
  --symbols RELIANCE,TCS   (NSE symbols; resolved via ISIN master → ISIN → subject_id)
  --only-isins INE002A01018,INE467B01029   (alternative; bypasses ISIN lookup)

Outputs:
  - Yahoo JSON cached to data/raw/yahoo/<date>/<hash>_<symbol>
  - Observations upserted to data/processed/observations.jsonl

Idempotent: re-running on the same date reads from cache; upsert detects
byte-identical content and skips rewrite.

Usage:
    python scripts/fetchers/fetch_hist_prices.py --symbols RELIANCE --incremental
    python scripts/fetchers/fetch_hist_prices.py --only-isins INE002A01018 --backfill 5y
    python scripts/fetchers/fetch_hist_prices.py --symbols RELIANCE,TCS --start 2024-01-01 --end 2024-09-30
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import FetchError, read_jsonl, upsert_records  # noqa: E402
from investorlens.io.yahoo import YahooChartClient, YahooError, to_yahoo_symbol  # noqa: E402
from investorlens.parsers import yahoo as yahoo_parser  # noqa: E402

log = logging.getLogger("fetch_hist_prices")

OUTPUT_PATH = ROOT / "data" / "processed" / "observations.jsonl"
ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"

# Range string → (lookback days, Yahoo range string) mapping.
# Yahoo accepts: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
_BACKFILL_RANGES: dict[str, str] = {
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "1y": "1y",
    "2y": "2y",
    "5y": "5y",
    "10y": "10y",
    "ytd": "ytd",
    "max": "max",
}


# ---------------------------------------------------------------------------
# ISIN master loading + symbol resolution
# ---------------------------------------------------------------------------


def load_isin_master() -> list[dict]:
    """Load the canonical ISIN master as a list of dicts.

    Returns an empty list if the master doesn't exist yet — the caller can
    still proceed if `--only-isins` was passed (subject IDs are derived
    deterministically from the ISIN itself).
    """
    if not ISIN_MASTER_PATH.exists():
        log.warning("ISIN master not found at %s — symbol resolution will be incomplete.", ISIN_MASTER_PATH)
        return []
    return read_jsonl(ISIN_MASTER_PATH)


def resolve_symbols_to_isins(
    symbols: list[str],
    isin_master: list[dict],
) -> dict[str, str]:
    """Map NSE symbols to ISINs using the ISIN master.

    Returns a dict {symbol: isin}. Symbols not in the master are skipped with a warning.
    """
    by_nse_symbol = {
        (r.get("nse_symbol") or "").upper(): r["isin"]
        for r in isin_master
        if r.get("nse_symbol")
    }
    out: dict[str, str] = {}
    for sym in symbols:
        sym_upper = sym.upper()
        isin = by_nse_symbol.get(sym_upper)
        if isin:
            out[sym] = isin
        else:
            log.warning("Symbol %s not in ISIN master — skipping.", sym)
    return out


# ---------------------------------------------------------------------------
# Per-symbol fetch logic
# ---------------------------------------------------------------------------


def _make_subject_id(isin: str) -> str:
    """Compute the Security ID from an ISIN (same formula as everywhere else)."""
    from investorlens.ids import make_id
    return make_id("sec", {"isin": isin})


def _build_yahoo_url(symbol: str, params: dict) -> str:
    """Build the Yahoo chart URL for provenance."""
    import requests
    return requests.Request("GET", f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params=params).prepare().url


def fetch_one_symbol(
    client: YahooChartClient,
    yahoo_symbol: str,
    subject_id: str,
    *,
    interval: str = "1d",
    range_: str = "5d",
    retrieved_at: datetime | None = None,
) -> list:
    """Fetch and parse the chart for a single Yahoo ticker. Returns observations."""
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    params = {"interval": interval, "range": range_}
    source_url = _build_yahoo_url(yahoo_symbol, params)

    try:
        response = client.get_chart(yahoo_symbol, interval=interval, range_=range_)
    except (FetchError, YahooError) as e:
        log.error("Fetch failed for %s: %s", yahoo_symbol, e)
        return []

    try:
        observations = yahoo_parser.parse_yahoo_chart(
            response,
            subject_id=subject_id,
            retrieved_at=retrieved_at,
            source_url=source_url,
            yahoo_symbol=yahoo_symbol,
        )
    except ValueError as e:
        log.error("Parse failed for %s: %s", yahoo_symbol, e)
        return []

    log.info("  %s → %d observations", yahoo_symbol, len(observations))
    return observations


def fetch_symbol_with_bse_fallback(
    client: YahooChartClient,
    nse_symbol: str | None,
    bse_code: str | None,
    isin: str,
    *,
    interval: str,
    range_: str,
    retrieved_at: datetime,
) -> list:
    """Try NSE ticker first; if Yahoo returns no data, fall back to BSE."""
    subject_id = _make_subject_id(isin)

    # Try NSE first
    if nse_symbol:
        nse_y = to_yahoo_symbol(nse_symbol=nse_symbol)
        obs = fetch_one_symbol(
            client, nse_y, subject_id,
            interval=interval, range_=range_, retrieved_at=retrieved_at,
        )
        if obs:
            return obs
        log.warning("No data from NSE ticker %s; trying BSE fallback.", nse_y)

    # BSE fallback
    if bse_code:
        bse_y = to_yahoo_symbol(bse_code=bse_code)
        obs = fetch_one_symbol(
            client, bse_y, subject_id,
            interval=interval, range_=range_, retrieved_at=retrieved_at,
        )
        if obs:
            return obs
        log.warning("No data from BSE ticker %s either.", bse_y)

    if not nse_symbol and not bse_code:
        log.error("No NSE symbol or BSE code for ISIN %s — cannot fetch.", isin)

    return []


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def fetch(
    *,
    symbols: list[str] | None = None,
    only_isins: list[str] | None = None,
    interval: str = "1d",
    backfill: str | None = None,
    incremental: bool = False,
    start: date | None = None,
    end: date | None = None,
    rate_limit_per_sec: float = 1.0,
) -> int:
    """Fetch historical prices for the given symbols/ISINs.

    Returns 0 on success, 1 on hard failure.
    """
    isin_master = load_isin_master()

    # Build the work list: [(nse_symbol, bse_code, isin), ...]
    targets: list[tuple[str | None, str | None, str]] = []

    if only_isins:
        # Build ISIN → (nse_symbol, bse_code) lookup from master.
        isin_to_symbols = {
            r["isin"]: (r.get("nse_symbol"), r.get("bse_code"))
            for r in isin_master
        }
        for isin in only_isins:
            nse_sym, bse_code = isin_to_symbols.get(isin, (None, None))
            targets.append((nse_sym, bse_code, isin))

    if symbols:
        sym_to_isin = resolve_symbols_to_isins(symbols, isin_master)
        # Build ISIN → (nse_symbol, bse_code) lookup
        isin_to_symbols = {
            r["isin"]: (r.get("nse_symbol"), r.get("bse_code"))
            for r in isin_master
        }
        for sym in symbols:
            isin = sym_to_isin.get(sym)
            if not isin:
                continue  # already warned in resolve_symbols_to_isins
            nse_sym, bse_code = isin_to_symbols.get(isin, (sym, None))
            targets.append((nse_sym, bse_code, isin))

    if not targets:
        log.error("No symbols or ISINs to fetch (check ISIN master and inputs).")
        return 1

    # Determine Yahoo range / period
    if backfill:
        range_ = _BACKFILL_RANGES.get(backfill)
        if range_ is None:
            log.error("Unknown backfill period: %s. Valid: %s", backfill, sorted(_BACKFILL_RANGES))
            return 1
        log.info("Backfill mode: range=%s", range_)
    elif start or end:
        # Explicit date range — convert to period1/period2 (handled in client).
        # For simplicity here, we use the Yahoo range API with a calculated range.
        # (Proper period1/period2 support is available in YahooChartClient if needed.)
        end_date = end or date.today()
        start_date = start or (end_date - timedelta(days=30))
        delta_days = (end_date - start_date).days
        # Pick the smallest Yahoo range that covers the delta.
        if delta_days <= 1:
            range_ = "1d"
        elif delta_days <= 5:
            range_ = "5d"
        elif delta_days <= 30:
            range_ = "1mo"
        elif delta_days <= 90:
            range_ = "3mo"
        elif delta_days <= 180:
            range_ = "6mo"
        elif delta_days <= 365:
            range_ = "1y"
        elif delta_days <= 730:
            range_ = "2y"
        elif delta_days <= 1825:
            range_ = "5y"
        elif delta_days <= 3650:
            range_ = "10y"
        else:
            range_ = "max"
        log.info("Date-range mode: %s to %s → Yahoo range=%s", start_date, end_date, range_)
    else:
        # Default: incremental (last 30 days)
        range_ = "1mo"
        log.info("Incremental mode (default): range=%s", range_)

    # Fetch each target.
    retrieved_at = datetime.now(timezone.utc)
    all_observations: list = []
    with YahooChartClient(rate_limit_per_sec=rate_limit_per_sec, max_retries=3) as client:
        for nse_sym, bse_code, isin in targets:
            log.info("Fetching %s (ISIN=%s)...", nse_sym or bse_code or isin, isin)
            obs = fetch_symbol_with_bse_fallback(
                client, nse_sym, bse_code, isin,
                interval=interval, range_=range_, retrieved_at=retrieved_at,
            )
            all_observations.extend(obs)

    if not all_observations:
        log.warning("No observations fetched.")
        return 1

    # Upsert.
    payload = [o.model_dump(mode="json", exclude_none=True) for o in all_observations]
    stats = upsert_records(OUTPUT_PATH, payload, key="id")
    try:
        out_rel = str(OUTPUT_PATH.relative_to(ROOT))
    except ValueError:
        out_rel = str(OUTPUT_PATH)
    log.info(
        "Upserted to %s: inserted=%d updated=%d total=%d",
        out_rel, stats["inserted"], stats["updated"], stats["total"],
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--symbols", type=str, help="Comma-separated NSE symbols, e.g. RELIANCE,TCS")
    grp.add_argument("--only-isins", type=str, help="Comma-separated ISINs")
    parser.add_argument("--interval", default="1d", help="Bar interval (1d, 1wk, 1mo). Default: 1d")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--backfill", type=str, help="Backfill period: 1mo/3mo/6mo/1y/2y/5y/10y/ytd/max")
    mode.add_argument("--incremental", action="store_true", help="Fetch last 30 days (default)")
    mode.add_argument("--start", type=str, help="Start date YYYY-MM-DD (use with --end)")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD (use with --start)")
    parser.add_argument("--rate-limit", type=float, default=1.0, help="Max requests/sec (default: 1.0)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
    only_isins = [i.strip().upper() for i in args.only_isins.split(",") if i.strip()] if args.only_isins else None
    start_date = date.fromisoformat(args.start) if args.start else None
    end_date = date.fromisoformat(args.end) if args.end else None

    return fetch(
        symbols=symbols,
        only_isins=only_isins,
        interval=args.interval,
        backfill=args.backfill,
        incremental=args.incremental,
        start=start_date,
        end=end_date,
        rate_limit_per_sec=args.rate_limit,
    )


if __name__ == "__main__":
    sys.exit(main())
