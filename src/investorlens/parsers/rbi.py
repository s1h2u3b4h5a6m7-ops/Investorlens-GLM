"""
RBI (Reserve Bank of India) parsers.

Two pages are scraped:

1. **Policy Rates page**: https://rbi.org.in/Scripts/BS_ViewPolicyRates.aspx
   Contains the current policy rates (Repo, SDF, MSF, Bank Rate, CRR, SLR).

2. **FX Reference Rate page**: https://rbi.org.in/Scripts/ReferenceRate.aspx
   Contains the daily USD/INR, EUR/INR, GBP/INR, JPY/INR reference rates.

Both pages render simple HTML tables. We use the standard library
`html.parser.HTMLParser` — no external dependencies (BeautifulSoup etc.).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Iterable

from ..ids import make_id
from ..models import Observation, ObservationKind, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = [
    "parse_policy_rates_html",
    "parse_fx_reference_html",
    "extract_tables",
    "Table",
    "POLICY_RATE_SLUGS",
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tiny HTML table extractor (stdlib only)
# ---------------------------------------------------------------------------


class Table:
    """A simple HTML table representation: list of rows, each row is a list of cell strings."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def add_row(self) -> None:
        self.rows.append([])

    def add_cell(self, text: str) -> None:
        if not self.rows:
            self.add_row()
        self.rows[-1].append(text)

    @property
    def shape(self) -> tuple[int, int]:
        n_rows = len(self.rows)
        n_cols = max((len(r) for r in self.rows), default=0)
        return n_rows, n_cols

    def as_dicts(self) -> list[dict[str, str]]:
        """Return rows as dicts, using the first row as headers."""
        if not self.rows:
            return []
        headers = [h.strip() for h in self.rows[0]]
        out: list[dict[str, str]] = []
        for row in self.rows[1:]:
            d: dict[str, str] = {}
            for i, cell in enumerate(row):
                if i < len(headers):
                    d[headers[i]] = cell.strip()
                else:
                    d[f"col_{i}"] = cell.strip()
            out.append(d)
        return out


class _TableExtractor(HTMLParser):
    """Extract all <table> elements from HTML as Table objects.

    Stacks tables (handles nesting). Cell text is concatenated across
    nested tags with a single space separator.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[Table] = []
        self._table_stack: list[Table] = []
        self._in_cell: bool = False
        self._cell_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            t = Table()
            self.tables.append(t)
            self._table_stack.append(t)
        elif tag in ("tr",) and self._table_stack:
            self._table_stack[-1].add_row()
        elif tag in ("td", "th") and self._table_stack:
            self._in_cell = True
            self._cell_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._table_stack:
                self._table_stack.pop()
        elif tag in ("td", "th") and self._table_stack:
            text = " ".join(" ".join(self._cell_buf).split())
            self._table_stack[-1].add_cell(text)
            self._in_cell = False
            self._cell_buf = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_buf.append(data)


def extract_tables(html: str) -> list[Table]:
    """Extract all <table> elements from an HTML string."""
    parser = _TableExtractor()
    parser.feed(html)
    return parser.tables


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_percent(s: str | None) -> float | None:
    """Parse a percentage string like '6.50' or '6.50%' → 6.50 (as float)."""
    if s is None:
        return None
    s = s.strip().rstrip("%").strip()
    if not s or s in {"-", "NA", "N/A"}:
        return None
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        return None


def _parse_decimal(s: str | None) -> float | None:
    return _parse_percent(s)  # same logic


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s.upper(), fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Policy rates
# ---------------------------------------------------------------------------


# Canonical slugs for each policy rate. These are stable identifiers used
# as the basis for the macro driver ID (drv_<hash of slug>).
POLICY_RATE_SLUGS: dict[str, str] = {
    "policy repo rate": "policy_repo_rate",
    "repo rate": "policy_repo_rate",
    "repo": "policy_repo_rate",
    "sdf rate": "sdf_rate",
    "standing deposit facility": "sdf_rate",
    "sdf": "sdf_rate",
    "msf rate": "msf_rate",
    "marginal standing facility": "msf_rate",
    "msf": "msf_rate",
    "bank rate": "bank_rate",
    "crr": "crr",
    "cash reserve ratio": "crr",
    "slr": "slr",
    "statutory liquidity ratio": "slr",
    "fixed reverse repo rate": "fixed_reverse_repo_rate",
    "reverse repo rate": "fixed_reverse_repo_rate",
    "reverse repo": "fixed_reverse_repo_rate",
}


def _canonical_policy_slug(label: str) -> str | None:
    """Map a free-text policy rate label to a canonical slug."""
    if not label:
        return None
    key = label.strip().lower()
    # Try exact match first, then progressively shorter prefixes.
    if key in POLICY_RATE_SLUGS:
        return POLICY_RATE_SLUGS[key]
    for k, v in POLICY_RATE_SLUGS.items():
        if key.startswith(k):
            return v
    return None


def _make_driver_id(slug: str) -> str:
    """Compute the macro-driver ID from a slug. Uses the existing `drv` prefix.

    This ID becomes the subject_id of policy-rate / CPI / FX observations,
    and will become the MacroDriver.id in Phase 3.
    """
    return make_id("drv", {"slug": slug.lower().strip()})


def parse_policy_rates_html(
    html: str,
    *,
    retrieved_at: datetime | None = None,
    source_url: str | None = None,
    as_of: date | None = None,
) -> list[Observation]:
    """Parse the RBI policy rates HTML page into Observation records.

    Args:
        html: raw HTML text.
        retrieved_at: UTC timestamp for provenance. Defaults to now().
        source_url: source URL for provenance.
        as_of: the date the rates apply to. Defaults to today (UTC). Useful
            for parsing historical snapshots.

    Returns:
        List of Observation records (one per recognized rate). Each has
        kind=POLICY_RATE, subject_id=drv_<slug>, unit="%".
    """
    prov_kwargs: dict = {
        "source": "rbi",
        "extraction_method": ExtractionMethod.HTML_SCRAPE,
        "confidence": Confidence.HIGH,
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    if source_url:
        prov_kwargs["source_url"] = source_url
    base_prov = Provenance(**prov_kwargs)

    if as_of is None:
        as_of = datetime.now().date()

    tables = extract_tables(html)
    if not tables:
        log.warning("No <table> elements found in RBI policy rates HTML.")
        return []

    observations: list[Observation] = []
    seen: set[tuple[str, str, str]] = set()

    # Look at all tables — RBI's page has multiple tables; we scan all rows
    # and pick out any (label, value) pair where the label matches a known slug.
    for table in tables:
        for row in table.rows:
            if len(row) < 2:
                continue
            label = row[0]
            # Try each cell as the value (some tables have label | value | notes).
            for value_cell in row[1:]:
                slug = _canonical_policy_slug(label)
                if slug is None:
                    break
                value = _parse_percent(value_cell)
                if value is None:
                    continue
                key = (slug, "policy_rate", as_of.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                observations.append(
                    Observation(
                        subject_id=_make_driver_id(slug),
                        kind=ObservationKind.POLICY_RATE,
                        period=as_of.isoformat(),
                        as_of=as_of,
                        value=value,
                        unit="%",
                        currency=None,
                        data_status="observed",
                        confidence=base_prov.confidence,
                        provenance=base_prov,
                    )
                )
                break  # don't try other cells once we've matched

    observations.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return observations


# ---------------------------------------------------------------------------
# FX reference rate
# ---------------------------------------------------------------------------


# Map of column header → currency code. We only care about a small set.
_FX_HEADER_MAP: dict[str, str] = {
    "1 usd": "USD",
    "usd": "USD",
    "1 eur": "EUR",
    "eur": "EUR",
    "1 gbp": "GBP",
    "gbp": "GBP",
    "100 jpy": "JPY",
    "jpy": "JPY",
    "100 jpy (inr)": "JPY",
}


def _canonical_fx_currency(header: str) -> str | None:
    if not header:
        return None
    key = header.strip().lower()
    return _FX_HEADER_MAP.get(key)


def parse_fx_reference_html(
    html: str,
    *,
    retrieved_at: datetime | None = None,
    source_url: str | None = None,
) -> list[Observation]:
    """Parse the RBI FX reference rate HTML page into Observation records.

    Each row produces one Observation per currency column (USD, EUR, GBP, JPY).
    Each observation has kind=FX_RATE, subject_id=drv_fx_<ccy>_inr.

    Returns:
        Sorted list of FX observations.
    """
    prov_kwargs: dict = {
        "source": "rbi",
        "extraction_method": ExtractionMethod.HTML_SCRAPE,
        "confidence": Confidence.HIGH,
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    if source_url:
        prov_kwargs["source_url"] = source_url
    base_prov = Provenance(**prov_kwargs)

    tables = extract_tables(html)
    if not tables:
        log.warning("No <table> elements found in RBI FX reference rate HTML.")
        return []

    observations: list[Observation] = []
    seen: set[tuple[str, str, str]] = set()

    for table in tables:
        rows = table.rows
        if len(rows) < 2:
            continue
        # First row is headers; find date column and currency columns.
        headers = [h.strip() for h in rows[0]]
        date_col_idx: int | None = None
        ccy_cols: dict[int, str] = {}  # col_idx → currency code
        for i, h in enumerate(headers):
            if not h:
                continue
            lower = h.lower()
            if "date" in lower or "as on" in lower:
                date_col_idx = i
            else:
                ccy = _canonical_fx_currency(h)
                if ccy:
                    ccy_cols[i] = ccy
        if date_col_idx is None or not ccy_cols:
            continue

        for row in rows[1:]:
            if len(row) <= date_col_idx:
                continue
            d = _parse_date(row[date_col_idx])
            if d is None:
                continue
            for col_idx, ccy in ccy_cols.items():
                if col_idx >= len(row):
                    continue
                value = _parse_decimal(row[col_idx])
                if value is None or value <= 0:
                    continue
                slug = f"fx_{ccy.lower()}_inr"
                key = (slug, "fx_rate", d.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                observations.append(
                    Observation(
                        subject_id=_make_driver_id(slug),
                        kind=ObservationKind.FX_RATE,
                        period=d.isoformat(),
                        as_of=d,
                        value=value,
                        unit=f"INR/{ccy}",
                        currency="INR",
                        data_status="observed",
                        confidence=base_prov.confidence,
                        provenance=base_prov,
                    )
                )

    observations.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return observations
