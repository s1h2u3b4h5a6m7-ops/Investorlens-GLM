"""
BSE (Bombay Stock Exchange) parsers.

Sources:
  - List of Securities CSV from BSE's corporates section.
    URL: https://www.bseindia.com/corporates/List_Scrips.aspx
    (The page offers a downloadable CSV with all listed securities.)
    Typical columns: Scrip Code, Scrip Name, Status, Group, Face Value,
                     ISIN, Industry, Issuer Name, Security Type, ...

  - Bhavcopy from BSE (EquityBhavCopy.zip): see Milestone 1.2 — not parsed here.

BSE's CSV format has historically been inconsistent (column names vary between
versions, sometimes "Scrip Code", sometimes "SC_CODE", etc.). This parser is
deliberately tolerant of column-name variations and lowercases / strips everything.

This module contains only PARSERS — pure functions of their input.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator, Mapping

from ..models import ISINMaster, Provenance, SecurityType
from ..models.provenance import Confidence, ExtractionMethod

__all__ = [
    "parse_list_scrips_csv",
    "iter_list_scrips_rows",
    "normalize_row_keys",
]

log = logging.getLogger(__name__)


# BSE column names that map to each canonical field. The first match wins.
# This is the key tolerance mechanism: BSE's CSV column naming is inconsistent
# across years, so we accept many variants.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "scrip_code": ("scrip code", "sc_code", "code", "bse code"),
    "scrip_name": ("scrip name", "scrip", "security name", "sc_name", "symbol"),
    "status": ("status", "scrip status"),
    "group": ("group", "segment"),
    "face_value": ("face value", "facevalue", "fv"),
    "isin": ("isin", "isin number", "isin no"),
    "industry": ("industry", "sector"),
    "issuer_name": ("issuer name", "issuer", "company name", "company"),
    "security_type": ("security type", "instrument"),
    "listing_date": ("listing date", "date of listing", "listed"),
    "trading_status": ("trading status", "trade status"),
}


def normalize_row_keys(row: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of `row` with header aliases resolved to canonical keys.

    Example:
      {"Scrip Code": "524715", "ISIN": "INE044A01026"}
      → {"scrip_code": "524715", "isin": "INE044A01026"}
    """
    out: dict[str, str] = {}
    for k, v in row.items():
        if k is None:
            continue
        key = k.strip().lower()
        canonical = _canonical_key(key)
        if canonical:
            out[canonical] = (v.strip() if isinstance(v, str) else v)
        else:
            # Preserve unknown keys (lowercased) for debugging.
            out[key] = (v.strip() if isinstance(v, str) else v)
    return out


def _canonical_key(lower_key: str) -> str | None:
    for canonical, aliases in _COLUMN_ALIASES.items():
        if lower_key in aliases:
            return canonical
    return None


def iter_list_scrips_rows(csv_text: str) -> Iterator[dict[str, str]]:
    """Iterate raw BSE List_Scrips CSV rows, with keys normalized."""
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # Skip blank rows (BSE files sometimes have trailing blank lines).
        if not any((v or "").strip() for v in row.values()):
            continue
        yield normalize_row_keys(row)


def _parse_decimal(s: str) -> Decimal | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# BSE security type strings → canonical enum. Conservative: anything we don't
# recognize defaults to OTHER, not EQUITY (we'd rather mark unknown than guess).
_BSE_SECURITY_TYPE_MAP: dict[str, SecurityType] = {
    "equity": SecurityType.EQUITY,
    "eq": SecurityType.EQUITY,
    "share": SecurityType.EQUITY,
    "debt": SecurityType.DEBT,
    "bond": SecurityType.DEBT,
    "debenture": SecurityType.DEBT,
    "preference": SecurityType.PREFERENCE,
    "prefs": SecurityType.PREFERENCE,
    "etf": SecurityType.ETF,
    "invit": SecurityType.INVIT,
    "reit": SecurityType.REIT,
}


def _map_security_type(s: str | None) -> SecurityType:
    if not s:
        return SecurityType.OTHER
    s = s.strip().lower()
    return _BSE_SECURITY_TYPE_MAP.get(s, SecurityType.OTHER)


def parse_list_scrips_csv(
    csv_text: str,
    *,
    retrieved_at: datetime | None = None,
) -> list[ISINMaster]:
    """Parse BSE's List_Scrips CSV into a list of `ISINMaster` records.

    Only rows with a valid ISIN are emitted (ISIN is our canonical anchor;
    without it we can't deduplicate against NSE).

    Rows with security_type other than EQUITY are STILL included — we want
    debt ISINs in the master too (they matter for some companies' capital
    structure analysis in Phase 2).
    """
    prov_kwargs: dict = {
        "source": "bse",
        "source_url": "https://www.bseindia.com/corporates/List_Scrips.aspx",
        "extraction_method": ExtractionMethod.BULK_DOWNLOAD,
        "confidence": Confidence.HIGH,
        "reporting_period": "current",
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    prov = Provenance(**prov_kwargs)

    records: list[ISINMaster] = []
    seen_isins: set[str] = set()

    for row in iter_list_scrips_rows(csv_text):
        isin = (row.get("isin") or "").strip().upper()
        if not isin or len(isin) < 12:
            continue
        if isin in seen_isins:
            # BSE can list the same ISIN under multiple codes (different segments).
            # Keep the first; the merge step in build_isin_master will reconcile.
            continue
        seen_isins.add(isin)

        scrip_code = (row.get("scrip_code") or "").strip()
        issuer = (row.get("issuer_name") or row.get("scrip_name") or "").strip()
        if not issuer:
            # If no issuer name, fall back to scrip name; if still empty, skip.
            continue

        records.append(
            ISINMaster(
                isin=isin,
                company_name=issuer,
                nse_symbol=None,
                bse_code=scrip_code or None,
                security_type=_map_security_type(row.get("security_type")),
                exchange="BSE",
                sector=(row.get("industry") or "").strip() or None,
                industry=None,
                active=(row.get("status") or "").strip().lower() in ("active", "listed", "permitted"),
                face_value=_parse_decimal(row.get("face_value") or ""),
                effective_from=_parse_date(row.get("listing_date") or ""),
                provenance=prov,
            )
        )

    return records
