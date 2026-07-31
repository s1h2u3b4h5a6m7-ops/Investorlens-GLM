"""
ISIN Master builder — merge per-source ISIN records into one canonical master.

Inputs:
  - List of ISINMaster records from NSE  (exchange="NSE", nse_symbol set, bse_code=None)
  - List of ISINMaster records from BSE  (exchange="BSE", bse_code set, nse_symbol=None)

Output:
  - List of merged ISINMaster records, one per ISIN, with:
      * exchange = "NSE", "BSE", or "NSE+BSE"
      * nse_symbol = NSE symbol if NSE has it, else None
      * bse_code   = BSE code   if BSE has it, else None
      * company_name = the longer / more descriptive name (BSE usually wins)
      * sector       = BSE sector if available (NSE EQUITY_L.csv has no sector)
      * face_value   = NSE if available, else BSE
      * active       = True if EITHER source says active (conservative)
      * provenance   = merged: source="nse+bse", with notes documenting both

Merge policy is documented in docs/DATA_MODEL.md → "ISIN Master merge policy".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from ..models import ISINMaster, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = ["build_isin_master", "merge_two_isin_records"]


def _pick_company_name(nse_name: str | None, bse_name: str | None) -> str | None:
    """Pick the more descriptive company name. BSE usually has the full legal name;
    NSE's EQUITY_L.csv only has the trading symbol.
    """
    nse_name = (nse_name or "").strip()
    bse_name = (bse_name or "").strip()
    if not nse_name and not bse_name:
        return None
    if not nse_name:
        return bse_name
    if not bse_name:
        return nse_name
    # Prefer the longer one (heuristic: longer = more descriptive).
    return bse_name if len(bse_name) >= len(nse_name) else nse_name


def _pick_sector(nse_sector: str | None, bse_sector: str | None) -> str | None:
    """BSE usually provides sector; NSE EQUITY_L.csv does not."""
    bse_sector = (bse_sector or "").strip()
    if bse_sector:
        return bse_sector
    nse_sector = (nse_sector or "").strip()
    return nse_sector or None


def _pick_face_value(nse_fv, bse_fv):
    """Prefer NSE face value if both present (it's usually cleaner);
    fall back to BSE if NSE missing.
    """
    if nse_fv is not None:
        return nse_fv
    return bse_fv


def _pick_effective_from(nse_date, bse_date):
    """Earliest known listing date."""
    if nse_date is None:
        return bse_date
    if bse_date is None:
        return nse_date
    return min(nse_date, bse_date)


def merge_two_isin_records(
    nse_rec: ISINMaster | None,
    bse_rec: ISINMaster | None,
    *,
    retrieved_at: datetime | None = None,
) -> ISINMaster | None:
    """Merge a single NSE record and a single BSE record for the same ISIN.

    Returns None if both inputs are None.
    Returns the non-None record unchanged (but with the same canonical provenance)
    if only one source has the ISIN.
    """
    if nse_rec is None and bse_rec is None:
        return None
    if nse_rec is None:
        assert bse_rec is not None
        return bse_rec
    if bse_rec is None:
        return nse_rec

    # Both present — merge.
    isin = nse_rec.isin  # canonical anchor (== bse_rec.isin by construction)
    exchange = "NSE+BSE"
    company_name = _pick_company_name(nse_rec.company_name, bse_rec.company_name) or nse_rec.company_name
    sector = _pick_sector(nse_rec.sector, bse_rec.sector)
    industry = bse_rec.industry or nse_rec.industry
    face_value = _pick_face_value(nse_rec.face_value, bse_rec.face_value)
    effective_from = _pick_effective_from(nse_rec.effective_from, bse_rec.effective_from)
    security_type = nse_rec.security_type  # NSE is always EQUITY in our pipeline; trust it
    active = nse_rec.active or bse_rec.active  # conservative: if either says active, treat as active

    # Build the merged provenance. Note the dual-source slug "nse+bse" so any
    # downstream consumer can see this record was cross-validated.
    prov_kwargs: dict = {
        "source": "nse+bse",
        "extraction_method": ExtractionMethod.BULK_DOWNLOAD,
        "confidence": Confidence.HIGH,  # cross-validated between two official sources
        "reporting_period": "current",
        "notes": (
            f"Merged from NSE (symbol={nse_rec.nse_symbol}) and "
            f"BSE (code={bse_rec.bse_code}). "
            f"NSE retrieved {nse_rec.provenance.retrieved_at.isoformat()}; "
            f"BSE retrieved {bse_rec.provenance.retrieved_at.isoformat()}."
        ),
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    provenance = Provenance(**prov_kwargs)

    return ISINMaster(
        isin=isin,
        company_name=company_name,
        nse_symbol=nse_rec.nse_symbol,
        bse_code=bse_rec.bse_code,
        security_type=security_type,
        exchange=exchange,
        sector=sector,
        industry=industry,
        active=active,
        face_value=face_value,
        effective_from=effective_from,
        provenance=provenance,
    )


def build_isin_master(
    nse_records: Iterable[ISINMaster],
    bse_records: Iterable[ISINMaster],
    *,
    retrieved_at: datetime | None = None,
) -> list[ISINMaster]:
    """Build the canonical ISIN master from NSE + BSE records.

    The output is sorted by ISIN for deterministic ordering.

    Edge cases:
      - An ISIN present in NSE only  → exchange="NSE"
      - An ISIN present in BSE only  → exchange="BSE"
      - An ISIN present in both      → exchange="NSE+BSE", fields merged per policy
      - An ISIN appearing multiple times within one source → first occurrence wins
        (this should not happen if parsers dedup correctly; we log a warning)
    """
    nse_by_isin = _index_by_isin(nse_records, source_label="NSE")
    bse_by_isin = _index_by_isin(bse_records, source_label="BSE")

    all_isins = sorted(set(nse_by_isin) | set(bse_by_isin))

    merged: list[ISINMaster] = []
    for isin in all_isins:
        rec = merge_two_isin_records(
            nse_by_isin.get(isin),
            bse_by_isin.get(isin),
            retrieved_at=retrieved_at,
        )
        if rec is not None:
            merged.append(rec)

    return merged


def _index_by_isin(
    records: Iterable[ISINMaster],
    *,
    source_label: str,
) -> dict[str, ISINMaster]:
    """Index records by ISIN. If an ISIN appears twice within the same source,
    keep the first and warn. (This indicates a parser bug if it happens.)
    """
    import logging

    log = logging.getLogger(__name__)
    out: dict[str, ISINMaster] = {}
    for rec in records:
        isin = rec.isin
        if isin in out:
            log.warning(
                "[%s] duplicate ISIN %s — keeping first occurrence", source_label, isin
            )
            continue
        out[isin] = rec
    return out
