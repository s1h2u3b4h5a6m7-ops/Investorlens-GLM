"""
MOSPI (Ministry of Statistics and Programme Implementation) parsers.

Currently supports:
  - CPI (Consumer Price Index) CSV: monthly index values + YoY %.

MOSPI publishes CPI as Excel files at https://mospi.gov.in/web/mospi/cpi-publications.
We model the CSV shape we'd extract from the .xlsx. The most-watched number
is the Combined (Rural + Urban) YoY %, which is the headline inflation rate.

Future datasets (not yet implemented):
  - IIP (Index of Industrial Production)
  - SUT (Supply and Use Tables) — Phase 4 Leontief model

Pure function: takes CSV text + args, returns list[Observation]. No I/O.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from typing import Iterable

from ..ids import make_id
from ..models import Observation, ObservationKind, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = ["parse_cpi_csv", "normalize_cpi_row_keys"]

log = logging.getLogger(__name__)


# MOSPI CPI column names vary across releases. Map known variants to canonical keys.
_CPI_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "year": ("year", "yr"),
    "month": ("month", "mon", "month_name"),
    "combined_index": ("combined rural+urban index", "combined index", "combined", "rural+urban index"),
    "combined_yoy": ("combined yoy %", "combined yoy", "combined yoy(%)", "combined inflation %", "inflation %"),
    "rural_index": ("rural index", "rural"),
    "rural_yoy": ("rural yoy %", "rural yoy"),
    "urban_index": ("urban index", "urban"),
    "urban_yoy": ("urban yoy %", "urban yoy"),
}


def normalize_cpi_row_keys(row: dict[str, str]) -> dict[str, str]:
    """Return a copy of `row` with header aliases resolved to canonical keys."""
    out: dict[str, str] = {}
    for k, v in row.items():
        if k is None:
            continue
        key = k.strip().lower()
        canonical = _canonical_key(key)
        if canonical:
            out[canonical] = (v.strip() if isinstance(v, str) else v)
        else:
            out[key] = (v.strip() if isinstance(v, str) else v)
    return out


def _canonical_key(lower_key: str) -> str | None:
    for canonical, aliases in _CPI_COLUMN_ALIASES.items():
        if lower_key in aliases:
            return canonical
    return None


_MONTH_NAME_TO_NUM: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_year(s: str | None) -> int | None:
    if not s:
        return None
    s = str(s).strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def _parse_month(s: str | None) -> int | None:
    if not s:
        return None
    s = str(s).strip().lower()
    if s.isdigit():
        m = int(s)
        return m if 1 <= m <= 12 else None
    return _MONTH_NAME_TO_NUM.get(s)


def _parse_float(s: str | None) -> float | None:
    if s is None:
        return None
    s = str(s).strip().rstrip("%").strip()
    if not s or s in {"-", "NA", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _make_driver_id(slug: str) -> str:
    """Compute the macro-driver ID from a slug."""
    return make_id("drv", {"slug": slug.lower().strip()})


# Canonical slugs for CPI indicators.
_CPI_SLUGS: dict[str, str] = {
    "combined_yoy": "cpi_combined_yoy",
    "rural_yoy": "cpi_rural_yoy",
    "urban_yoy": "cpi_urban_yoy",
    "combined_index": "cpi_combined_index",
    "rural_index": "cpi_rural_index",
    "urban_index": "cpi_urban_index",
}


def parse_cpi_csv(
    csv_text: str,
    *,
    retrieved_at: datetime | None = None,
    source_url: str | None = None,
) -> list[Observation]:
    """Parse MOSPI CPI CSV into Observation records.

    Each row produces up to 6 observations (one per indicator):
      - cpi_combined_yoy, cpi_rural_yoy, cpi_urban_yoy (kind=CPI_YOY, unit=%)
      - cpi_combined_index, cpi_rural_index, cpi_urban_index (kind=OTHER, unit=index)

    Rows missing year or month are skipped.

    Args:
        csv_text: raw CSV text.
        retrieved_at: UTC timestamp for provenance. Defaults to now().
        source_url: source URL for provenance.

    Returns:
        Sorted list of Observation records.
    """
    prov_kwargs: dict = {
        "source": "mospi",
        "extraction_method": ExtractionMethod.BULK_DOWNLOAD,
        "confidence": Confidence.HIGH,
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    if source_url:
        prov_kwargs["source_url"] = source_url
    base_prov = Provenance(**prov_kwargs)

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames:
        reader.fieldnames = [f.strip() if f else f for f in reader.fieldnames]

    observations: list[Observation] = []
    seen: set[tuple[str, str, str]] = set()

    for raw_row in reader:
        row = normalize_cpi_row_keys({k.lower().strip() if k else k: (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k})

        year = _parse_year(row.get("year"))
        month = _parse_month(row.get("month"))
        if year is None or month is None:
            continue

        # Use the first day of the month as the as_of date.
        as_of = date(year, month, 1)
        period = f"{year}-{month:02d}"

        # Extract each indicator.
        for canonical_field, slug in _CPI_SLUGS.items():
            value_str = row.get(canonical_field)
            value = _parse_float(value_str)
            if value is None:
                continue
            # YoY fields use the CPI_YOY kind; index fields use OTHER.
            kind = ObservationKind.CPI_YOY if canonical_field.endswith("_yoy") else ObservationKind.OTHER
            unit = "%" if canonical_field.endswith("_yoy") else "index"
            key = (slug, kind.value, period)
            if key in seen:
                continue
            seen.add(key)
            observations.append(
                Observation(
                    subject_id=_make_driver_id(slug),
                    kind=kind,
                    period=period,
                    as_of=as_of,
                    value=value,
                    unit=unit,
                    currency=None,
                    data_status="observed",
                    confidence=base_prov.confidence,
                    provenance=base_prov,
                )
            )

    observations.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return observations
