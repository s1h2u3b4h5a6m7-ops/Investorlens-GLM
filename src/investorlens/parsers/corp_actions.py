"""
NSE Corporate Actions parser.

NSE publishes a bulk CSV at:
  https://archives.nseindia.com/corporates/CORPACT.csv

Columns (current NSE format):
  Symbol, Series, Industry, Face Value(Rs.), Symbol 2, Company Name,
  Subject, Ex-Date, Record-Date, Broadcast-Date, BC Start Date, BC End Date,
  ND Start Date, ND End Date, Actual Payment Date, Dividend Type,
  Dividend (%), Dividend Amount / Share, Purpose, Details

The "Subject" / "Purpose" field is free-text and contains the description of
the action (e.g. "Bonus - 1:1", "Stock Split from Rs.10/- to Rs.2/-", "Dividend - Rs.5/-").

This parser:
  1. Reads the CSV.
  2. Classifies each row into a CorporateActionType using regex on the Subject/Purpose.
  3. Extracts ratio (numerator:denominator) for splits/bonus/rights.
  4. Extracts dividend amount per share for dividends.
  5. Maps NSE symbol → ISIN → security_id using the ISIN master (passed in).
  6. Returns a list of CorporateAction records.

Pure function: takes CSV text + ISIN lookup, returns list[CorporateAction].
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from ..models import CorporateAction, CorporateActionType, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = [
    "parse_corpact_csv",
    "classify_subject",
    "extract_ratio",
    "extract_dividend_amount",
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subject / Purpose classification
# ---------------------------------------------------------------------------


# Regex patterns for the free-text Subject/Purpose field.
# Patterns are checked in order; first match wins.
# IMPORTANT: dividend must be checked AFTER bonus/split because some rows
# contain both (e.g. "Bonus + Dividend").
_PATTERNS: list[tuple[CorporateActionType, re.Pattern]] = [
    # Bonus issues — "Bonus 1:1", "Bonus Issue 2:1", etc.
    (CorporateActionType.BONUS, re.compile(r"\bbonus\b", re.IGNORECASE)),
    # Stock splits — "Stock Split from Rs.10 to Rs.2", "Sub-division", "Split 5:1"
    (CorporateActionType.SPLIT, re.compile(r"\b(stock\s*split|sub-?division|split)\b", re.IGNORECASE)),
    # Rights issues — "Rights 1:5 @ Rs.100", "Rights Issue"
    (CorporateActionType.RIGHTS, re.compile(r"\brights?\b", re.IGNORECASE)),
    # Mergers — "Merger", "Amalgamation", "Scheme of Arrangement"
    (CorporateActionType.MERGER, re.compile(r"\b(merger|amalgamat\w*|scheme\s+of\s+(?:arrangement|amalgamation))", re.IGNORECASE)),
    # Demergers — "Demerger", "Demerged", "Spin-off"
    (CorporateActionType.DEMERGER, re.compile(r"\b(demerger|spin-?off)", re.IGNORECASE)),
    # Symbol changes — "Change of Symbol", "Symbol Change"
    (CorporateActionType.SYMBOL_CHANGE, re.compile(r"\b(?:symbol\s+change|change\s+of\s+symbol)\b", re.IGNORECASE)),
    # Dividends — "Dividend - Rs.5", "Interim Dividend", "Final Dividend".
    # Checked BEFORE face_value_change because dividend rows often mention
    # "face value of Rs.X" as context (the dividend basis), not as a face value change.
    (CorporateActionType.DIVIDEND, re.compile(r"\bdividend\b", re.IGNORECASE)),
    # Face value changes (rare as a standalone action; usually co-occurs with a split,
    # which is checked first).
    (CorporateActionType.FACE_VALUE_CHANGE, re.compile(r"\bface\s+value\b", re.IGNORECASE)),
]


def classify_subject(subject: str | None) -> CorporateActionType:
    """Classify a free-text Subject/Purpose string into a CorporateActionType.

    Returns CorporateActionType.OTHER if no pattern matches.
    """
    if not subject:
        return CorporateActionType.OTHER
    for action_type, pattern in _PATTERNS:
        if pattern.search(subject):
            return action_type
    return CorporateActionType.OTHER


# ---------------------------------------------------------------------------
# Ratio / amount extraction
# ---------------------------------------------------------------------------


# Match ratios like "1:1", "2:5", "10:3", "1:1 (i.e. one share for every one share held)"
_RATIO_RE = re.compile(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)")


def extract_ratio(text: str | None) -> tuple[float | None, float | None]:
    """Extract a (numerator, denominator) ratio from a text like "Bonus 1:1".

    Returns (None, None) if no ratio is found. Returns (num, denom) on first match.
    """
    if not text:
        return None, None
    m = _RATIO_RE.search(text)
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None, None


# Match dividend amounts like "Rs. 5/-", "Rs.5", "INR 10", "Rs 5 per share"
_DIVIDEND_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*(\d+(?:\.\d+)?)\s*(?:/-|per\s+share)?",
    re.IGNORECASE,
)


def extract_dividend_amount(text: str | None) -> Decimal | None:
    """Extract the dividend amount per share from a text like "Dividend - Rs.5/-".

    Returns None if no amount is found.
    """
    if not text:
        return None
    m = _DIVIDEND_AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        return Decimal(m.group(1))
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def _parse_date(s: str | None) -> date | None:
    """Parse NSE date formats: DD-MMM-YYYY, DD-MMM-YY, YYYY-MM-DD."""
    if not s:
        return None
    s = s.strip()
    if not s or s in {"-", "NA", "N/A"}:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.upper(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(s: str | None) -> Decimal | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s in {"-", "NA", "N/A"}:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Symbol → ISIN lookup
# ---------------------------------------------------------------------------


def _build_symbol_to_isin_index(
    isin_master: Iterable[dict],
) -> dict[str, str]:
    """Build a {NSE_SYMBOL: ISIN} index from the ISIN master records."""
    out: dict[str, str] = {}
    for r in isin_master:
        sym = r.get("nse_symbol")
        isin = r.get("isin")
        if sym and isin:
            out[sym.upper()] = isin
    return out


def _make_security_id(isin: str) -> str:
    """Compute the Security ID from an ISIN."""
    from ..ids import make_id
    return make_id("sec", {"isin": isin})


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_corpact_csv(
    csv_text: str,
    *,
    isin_master: Iterable[dict] | None = None,
    retrieved_at: datetime | None = None,
    source_url: str | None = None,
) -> list[CorporateAction]:
    """Parse NSE's CORPACT.csv into a list of CorporateAction records.

    Args:
        csv_text: raw CSV text from NSE.
        isin_master: iterable of ISINMaster dicts (used to resolve NSE symbol → ISIN → security_id).
            If None or symbol not found, the action is skipped with a warning.
        retrieved_at: UTC timestamp for provenance. Defaults to now().
        source_url: source URL for provenance.

    Returns:
        List of CorporateAction records (deduplicated by ID). Sorted by
        (security_id, ex_date, action_type) for deterministic output.
    """
    # Build the symbol → ISIN index.
    sym_to_isin = _build_symbol_to_isin_index(isin_master or [])

    # Provenance template.
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

    reader = csv.DictReader(io.StringIO(csv_text))
    # NSE's CSV column names sometimes have trailing/leading whitespace.
    if reader.fieldnames:
        reader.fieldnames = [f.strip() if f else f for f in reader.fieldnames]

    records: list[CorporateAction] = []
    seen_ids: set[str] = set()
    skipped_no_isin = 0
    skipped_no_date = 0

    for row in reader:
        # Normalize keys to lowercase for tolerance.
        row = {k.lower().strip() if k else k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}

        symbol = (row.get("symbol") or "").strip().upper()
        if not symbol:
            continue

        isin = sym_to_isin.get(symbol)
        if not isin:
            skipped_no_isin += 1
            continue

        ex_date = _parse_date(row.get("ex-date") or row.get("ex date"))
        if ex_date is None:
            skipped_no_date += 1
            continue

        # Classify the action based on Subject + Purpose + Details.
        subject = row.get("subject") or ""
        purpose = row.get("purpose") or ""
        details = row.get("details") or ""
        text_for_classification = " | ".join(filter(None, [subject, purpose, details]))
        action_type = classify_subject(text_for_classification)

        # Extract numeric parameters based on action type.
        ratio_numerator: float | None = None
        ratio_denominator: float | None = None
        amount_per_share: Decimal | None = None

        if action_type in (CorporateActionType.SPLIT, CorporateActionType.BONUS, CorporateActionType.RIGHTS):
            # Try the "Dividend (%)" and other numeric columns first, then fall back to regex.
            ratio_numerator, ratio_denominator = extract_ratio(text_for_classification)
            # Some NSE rows have explicit "X:Y" in a separate column.
            if ratio_numerator is None:
                # Try parsing "Rs.10 to Rs.2" or "Rs.2 to Re.1" style from the Subject for splits.
                # NSE uses "Re.1" for 1 rupee (singular), "Rs.N" for N>=2.
                m = re.search(
                    r"r[es]\.?\s*(\d+(?:\.\d+)?)\s*(?:/-)?\s*to\s*r[es]\.?\s*(\d+(?:\.\d+)?)",
                    text_for_classification,
                    re.IGNORECASE,
                )
                if m:
                    try:
                        old_fv = float(m.group(1))
                        new_fv = float(m.group(2))
                        if new_fv > 0:
                            ratio_numerator = old_fv / new_fv
                            ratio_denominator = 1.0
                    except ValueError:
                        pass

        if action_type == CorporateActionType.DIVIDEND:
            # Prefer the explicit "Dividend Amount / Share" column, then fall back to regex.
            amount_per_share = _parse_decimal(row.get("dividend amount / share"))
            if amount_per_share is None:
                amount_per_share = extract_dividend_amount(text_for_classification)

        record_date = _parse_date(row.get("record-date") or row.get("record date"))
        announcement_date = _parse_date(row.get("broadcast-date") or row.get("broadcast date"))

        # New face value (for splits / face value changes).
        new_face_value: Decimal | None = None
        if action_type in (CorporateActionType.SPLIT, CorporateActionType.FACE_VALUE_CHANGE):
            # Try to extract the new face value from the Subject.
            # NSE uses "Re.1" for 1 rupee (singular), "Rs.N" for N>=2.
            m = re.search(r"to\s*r[es]\.?\s*(\d+(?:\.\d+)?)", text_for_classification, re.IGNORECASE)
            if m:
                try:
                    new_face_value = Decimal(m.group(1))
                except InvalidOperation:
                    pass

        try:
            ca = CorporateAction(
                security_id=_make_security_id(isin),
                action_type=action_type,
                ex_date=ex_date,
                record_date=record_date,
                announcement_date=announcement_date,
                ratio_numerator=ratio_numerator,
                ratio_denominator=ratio_denominator,
                amount_per_share=amount_per_share,
                new_face_value=new_face_value,
                notes=text_for_classification[:500] if text_for_classification else None,
                provenance=base_prov,
            )
        except Exception as e:
            log.warning("Failed to construct CorporateAction for %s on %s: %s", symbol, ex_date, e)
            continue

        if ca.id in seen_ids:
            continue
        seen_ids.add(ca.id)
        records.append(ca)

    if skipped_no_isin:
        log.info("Skipped %d corp-action rows because NSE symbol not in ISIN master.", skipped_no_isin)
    if skipped_no_date:
        log.info("Skipped %d corp-action rows because Ex-Date was missing/unparseable.", skipped_no_date)

    # Deterministic sort.
    records.sort(key=lambda c: (c.security_id, c.ex_date.isoformat(), c.action_type.value))
    return records
