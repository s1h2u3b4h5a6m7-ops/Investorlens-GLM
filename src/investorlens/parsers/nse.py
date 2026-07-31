"""
NSE (National Stock Exchange of India) parsers.

Sources:
  - EQUITY_L.csv: list of all currently listed equity symbols on NSE.
    URL: https://nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O
    or  https://archives.nseindia.com/content/equities/EQUITY_L.csv
    Columns: SYMBOL, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT,
             ISIN NUMBER, FACE VALUE

  - Bhavcopy (securities traded today): see Milestone 1.2 — not parsed here.

This module only contains PARSERS — pure functions that take raw text and
return Pydantic models. The actual fetching (HTTP, caching) is in
`investorlens.io.http` and the fetcher scripts.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

from ..models import ISINMaster, Provenance, SecurityType
from ..models.provenance import Confidence, ExtractionMethod

__all__ = [
    "parse_equity_l_csv",
    "iter_equity_l_rows",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(s: str, fmt: str = "%d-%b-%Y") -> date | None:
    """Parse NSE-style date strings like '10-Oct-2008'. Returns None if blank/unparseable."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, fmt).date()
    except ValueError:
        return None


def _parse_decimal(s: str) -> Decimal | None:
    """Parse a decimal string, returning None for blank/invalid."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _clean(s: str) -> str | None:
    """Strip whitespace; return None for empty strings (so they're dropped by canonicalize)."""
    s = (s or "").strip()
    return s or None


# ---------------------------------------------------------------------------
# Public parser API
# ---------------------------------------------------------------------------


def iter_equity_l_rows(csv_text: str) -> Iterator[dict[str, str]]:
    """Iterate raw NSE EQUITY_L.csv rows as dicts.

    Yields dicts keyed by the CSV header. This is the lowest-level parser,
    used for inspection and as the input to the higher-level parser.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # Strip whitespace from keys and values.
        yield {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}


def parse_equity_l_csv(
    csv_text: str,
    *,
    retrieved_at: datetime | None = None,
) -> list[ISINMaster]:
    """Parse NSE's EQUITY_L.csv into a list of `ISINMaster` records.

    Args:
        csv_text: raw CSV text from NSE.
        retrieved_at: UTC timestamp to attach to provenance. Defaults to now().

    Returns:
        List of ISINMaster records (one per row). Rows without a valid ISIN
        are skipped (with a warning logged).

    The provenance source is "nse"; extraction_method is "bulk_download";
    confidence is "high" (official bulk file).
    """
    prov_kwargs: dict = {
        "source": "nse",
        "source_url": "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
        "extraction_method": ExtractionMethod.BULK_DOWNLOAD,
        "confidence": Confidence.HIGH,
        "reporting_period": "current",
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    prov = Provenance(**prov_kwargs)

    records: list[ISINMaster] = []
    seen_isins: set[str] = set()

    for row in iter_equity_l_rows(csv_text):
        isin = (row.get("ISIN NUMBER") or "").strip().upper()
        symbol = (row.get("SYMBOL") or "").strip()
        if not isin or not symbol:
            # Skip rows missing the canonical key.
            continue
        if isin in seen_isins:
            # EQUITY_L.csv should have one row per symbol; ISIN can repeat
            # across series (e.g. EQ + BE). Keep the first.
            continue
        seen_isins.add(isin)

        records.append(
            ISINMaster(
                isin=isin,
                company_name=symbol,  # EQUITY_L.csv has only the symbol, not the full company name.
                nse_symbol=symbol,
                bse_code=None,
                security_type=SecurityType.EQUITY,
                exchange="NSE",
                sector=None,
                industry=None,
                active=True,
                face_value=_parse_decimal(row.get("FACE VALUE", "")),
                effective_from=_parse_date(row.get("DATE OF LISTING", "")),
                provenance=prov,
            )
        )

    return records
