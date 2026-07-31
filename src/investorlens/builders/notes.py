"""
Company knowledge note builder.

Takes a company's structured data (ISIN master record + observations +
corporate actions) and produces a human-readable Markdown note with
YAML frontmatter.

The note structure follows the InvestorLens roadmap:
  - YAML frontmatter (machine-readable, Dataview-compatible)
  - Business
  - Products
  - Customers
  - Suppliers
  - Raw materials
  - Cost drivers
  - Financials (prices, volume, turnover — populated from observations)
  - Capital structure
  - Management / promoters
  - Risks
  - Value chain
  - Macro exposures (populated from drv_* observations on the same dates)
  - Evidence
  - Hypotheses
  - Validated relationships
  - Corporate actions (populated from corporate_actions.jsonl)
  - Data quality

Sections without underlying data are emitted as empty placeholders with a
clear note that the data hasn't been researched yet. This makes the gap
explicit rather than hiding it.

Pure function: takes records, returns a Markdown string. No I/O.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from ..models import CorporateAction, Observation, ObservationKind
from ..models.provenance import Provenance

__all__ = [
    "build_company_note",
    "slugify_company",
    "format_decimal",
    "format_date",
    "format_observations_table",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify_company(name: str, nse_symbol: str | None = None, isin: str | None = None) -> str:
    """Generate a URL-safe slug for a company.

    Prefer the NSE symbol (lowercase); fall back to the company name; finally
    fall back to the ISIN if neither is available.

    Examples:
      ("Reliance Industries Ltd", "RELIANCE", "INE002A01018") → "reliance"
      ("Some Co Ltd", None, "INE123A01045")                   → "some_co_ltd"
      ("", None, "INE999A99999")                              → "ine999a99999"
    """
    if nse_symbol:
        return nse_symbol.strip().lower().replace(" ", "_").replace("/", "_")
    if name:
        s = name.strip().lower()
        # Replace common company suffixes and punctuation.
        for suffix in (" ltd", " limited", " pvt", " private"):
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
        s = s.replace(" ", "_").replace("/", "_").replace(".", "").replace(",", "").replace("&", "and")
        return s or (isin.lower() if isin else "unknown")
    return (isin or "unknown").lower()


def format_decimal(v: float | int | Decimal | str | None) -> str:
    """Format a numeric value for Markdown display.

    Returns "—" (em dash) for None, otherwise a string with up to 4 decimal places.
    """
    if v is None:
        return "—"
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float):
        # Trim trailing zeros: 100.5000 → 100.5; 100.0000 → 100
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s
    return str(v)


def format_date(d: date | datetime | str | None) -> str:
    """Format a date for Markdown display. Returns "—" for None."""
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        d = d.date()
    return d.isoformat()


# ---------------------------------------------------------------------------
# Observations table formatter
# ---------------------------------------------------------------------------


def format_observations_table(observations: list[Observation]) -> str:
    """Render a list of price/volume observations as a Markdown table.

    Sorts by as_of descending (most recent first). Limits to the most recent 30
    rows to keep the note readable.
    """
    if not observations:
        return "_(no observations)_"

    # Sort by as_of descending.
    sorted_obs = sorted(observations, key=lambda o: o.as_of, reverse=True)
    # Limit to 30 most recent.
    sorted_obs = sorted_obs[:30]

    lines = [
        "| Date | Kind | Value | Unit | Currency | Source |",
        "|------|------|------:|------|----------|--------|",
    ]
    for o in sorted_obs:
        prov_source = o.provenance.source if o.provenance else "—"
        lines.append(
            f"| {o.as_of.isoformat()} | `{o.kind.value}` | {format_decimal(o.value)} | {o.unit or '—'} | {o.currency or '—'} | {prov_source} |"
        )
    if len(observations) > 30:
        lines.append(f"| _(showing 30 most recent of {len(observations)} total)_ ||||||")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Corporate actions table formatter
# ---------------------------------------------------------------------------


def format_corporate_actions_table(cas: list[CorporateAction]) -> str:
    """Render corporate actions as a Markdown table, sorted by ex_date descending."""
    if not cas:
        return "_(no corporate actions on record)_"

    sorted_cas = sorted(cas, key=lambda c: c.ex_date, reverse=True)
    lines = [
        "| Ex-Date | Type | Ratio | Amount/Share | New FV | Notes | Source |",
        "|---------|------|-------|-------------|--------|-------|--------|",
    ]
    for c in sorted_cas:
        ratio = "—"
        if c.ratio_numerator is not None and c.ratio_denominator is not None:
            ratio = f"{c.ratio_numerator:g} : {c.ratio_denominator:g}"
        amount = format_decimal(c.amount_per_share) if c.amount_per_share is not None else "—"
        new_fv = format_decimal(c.new_face_value) if c.new_face_value is not None else "—"
        # Truncate notes to 80 chars for the table.
        notes = (c.notes or "")[:80]
        if c.notes and len(c.notes) > 80:
            notes += "…"
        prov_source = c.provenance.source if c.provenance else "—"
        lines.append(
            f"| {c.ex_date.isoformat()} | `{c.action_type.value}` | {ratio} | {amount} | {new_fv} | {notes} | {prov_source} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# YAML frontmatter
# ---------------------------------------------------------------------------


def _yaml_escape(s: str) -> str:
    """Escape a string for safe YAML scalar value."""
    if s is None:
        return '""'
    s = str(s)
    # If it contains special YAML chars, wrap in double quotes and escape.
    if any(c in s for c in [":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "<", ">", "=", "!", "%", "@", "`"]):
        return '"' + s.replace('"', '\\"') + '"'
    if s.strip() != s or not s:
        return '"' + s + '"'
    return s


def _yaml_frontmatter(company: dict, observations_count: int, corp_actions_count: int, last_updated: str) -> str:
    """Build the YAML frontmatter block for a company note.

    Fields are kept simple (strings, numbers, dates, booleans) for Dataview
    compatibility.
    """
    isin = company.get("isin") or ""
    nse_symbol = company.get("nse_symbol") or ""
    bse_code = company.get("bse_code") or ""

    lines = ["---"]
    lines.append(f"id: {_yaml_escape(company.get('id', ''))}")
    lines.append(f"isin: {_yaml_escape(isin)}")
    if nse_symbol:
        lines.append(f"nse_symbol: {_yaml_escape(nse_symbol)}")
    if bse_code:
        lines.append(f"bse_code: {_yaml_escape(bse_code)}")
    lines.append(f"company_name: {_yaml_escape(company.get('company_name', ''))}")
    if company.get("sector"):
        lines.append(f"sector: {_yaml_escape(company['sector'])}")
    if company.get("industry"):
        lines.append(f"industry: {_yaml_escape(company['industry'])}")
    lines.append(f"exchange: {_yaml_escape(company.get('exchange', ''))}")
    lines.append(f"security_type: {_yaml_escape(company.get('security_type', ''))}")
    if company.get("face_value"):
        lines.append(f"face_value: {_yaml_escape(company['face_value'])}")
    lines.append(f"active: {str(company.get('active', True)).lower()}")
    if company.get("effective_from"):
        lines.append(f"listing_date: {_yaml_escape(company['effective_from'])}")
    # Provenance / data status
    lines.append(f"observations_count: {observations_count}")
    lines.append(f"corporate_actions_count: {corp_actions_count}")
    lines.append(f"last_updated: {_yaml_escape(last_updated)}")
    lines.append(f"data_status: researched_partial  # Phase 1 data only; Phase 3+ will fill research sections")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main note builder
# ---------------------------------------------------------------------------


_PLACEHOLDER_SECTIONS = [
    ("Business", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Products", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Customers", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Suppliers", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Raw materials", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Cost drivers", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Capital structure", "_(Not yet researched — to be filled in Phase 3 from annual reports and credit rating rationales.)_"),
    ("Management / promoters", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
    ("Risks", "_(Not yet researched — to be filled in Phase 3 from DRHPs and credit rating rationales.)_"),
    ("Value chain", "_(Not yet researched — to be filled in Phase 3 from DRHPs and supply-chain analysis.)_"),
    ("Evidence", "_(No evidence records yet — Phase 3 will populate from source documents.)_"),
    ("Hypotheses", "_(No hypotheses yet — Phase 3 will record inferred relationships.)_"),
    ("Validated relationships", "_(No validated relationships yet — Phase 4 will validate via rolling betas, event studies, and shock analysis.)_"),
]


def build_company_note(
    company: dict,
    observations: list[Observation],
    corp_actions: list[CorporateAction],
    *,
    value_chain_edges: list[dict] | None = None,
    raw_materials: list[dict] | None = None,
    products: list[dict] | None = None,
    suppliers: list[dict] | None = None,
    customers: list[dict] | None = None,
    exposures: list[dict] | None = None,
    macro_drivers: list[dict] | None = None,
    last_updated: datetime | None = None,
) -> str:
    """Build a Markdown knowledge note for a single company.

    Args:
        company: the ISIN master record as a dict.
        observations: this company's observations (subject_id == security_id).
        corp_actions: this company's corporate actions (security_id == security_id).
        value_chain_edges: optional list of ValueChainEdge dicts where from_id
            == this company's security_id. If provided, the Products, Raw
            materials, Customers, Suppliers, and Value chain sections are
            populated from the edges.
        raw_materials: lookup list for raw material node labels.
        products: lookup list for product node labels.
        suppliers: lookup list for supplier node labels.
        customers: lookup list for customer node labels.
        exposures: optional list of Exposure dicts where company_id == this
            company's security_id. If provided, the Macro exposures section
            is populated with structured exposure data.
        macro_drivers: lookup list for macro driver node labels.
        last_updated: UTC timestamp. Defaults to now().

    Returns:
        A complete Markdown string with YAML frontmatter and all sections.
    """
    if last_updated is None:
        last_updated = datetime.now()

    # Separate observations by kind.
    price_obs = [o for o in observations if o.kind in (
        ObservationKind.PRICE_OPEN,
        ObservationKind.PRICE_HIGH,
        ObservationKind.PRICE_LOW,
        ObservationKind.PRICE_CLOSE,
        ObservationKind.PRICE_CLOSE_ADJ,
    )]
    volume_obs = [o for o in observations if o.kind == ObservationKind.VOLUME]
    turnover_obs = [o for o in observations if o.kind == ObservationKind.TURNOVER]

    # Latest close (raw + adjusted).
    latest_close: Observation | None = None
    latest_adj_close: Observation | None = None
    for o in observations:
        if o.kind == ObservationKind.PRICE_CLOSE:
            if latest_close is None or o.as_of > latest_close.as_of:
                latest_close = o
        elif o.kind == ObservationKind.PRICE_CLOSE_ADJ:
            if latest_adj_close is None or o.as_of > latest_adj_close.as_of:
                latest_adj_close = o

    # YAML frontmatter
    fm = _yaml_frontmatter(
        company,
        observations_count=len(observations),
        corp_actions_count=len(corp_actions),
        last_updated=last_updated.isoformat(timespec="seconds"),
    )

    # Title
    company_name = company.get("company_name") or "(unknown company)"
    title = f"# {company_name}"

    # Header block (under title)
    header_lines = [
        f"**ISIN:** `{company.get('isin', '—')}`  ",
        f"**Exchange:** {company.get('exchange', '—')}  ",
        f"**Active:** {'yes' if company.get('active', True) else 'no'}  ",
    ]
    if company.get("nse_symbol"):
        header_lines.append(f"**NSE symbol:** `{company['nse_symbol']}`  ")
    if company.get("bse_code"):
        header_lines.append(f"**BSE code:** `{company['bse_code']}`  ")
    if company.get("sector"):
        header_lines.append(f"**Sector:** {company['sector']}  ")
    if company.get("industry"):
        header_lines.append(f"**Industry:** {company['industry']}  ")
    if company.get("face_value"):
        header_lines.append(f"**Face value:** ₹{company['face_value']}  ")
    if company.get("effective_from"):
        header_lines.append(f"**Listing date:** {company['effective_from']}  ")
    header = "\n".join(header_lines)

    # Latest snapshot (quick-glance metrics at the top)
    snapshot_lines = ["## Latest snapshot", ""]
    if latest_close:
        snapshot_lines.append(f"- **Last close (raw):** ₹{format_decimal(latest_close.value)} on {latest_close.as_of.isoformat()} (source: {latest_close.provenance.source})")
    if latest_adj_close:
        snapshot_lines.append(f"- **Last close (adjusted):** ₹{format_decimal(latest_adj_close.value)} on {latest_adj_close.as_of.isoformat()} (source: {latest_adj_close.provenance.source})")
    if not latest_close and not latest_adj_close:
        snapshot_lines.append("_(No price observations on record.)_")
    snapshot = "\n".join(snapshot_lines)

    # Build all sections in order.
    sections: list[str] = [fm, "", title, "", header, "", snapshot, ""]

    # Business section (always placeholder for now — requires DRHP/AR research)
    sections.append("## Business")
    sections.append("")
    sections.append("_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_")
    sections.append("")

    # ─── Value-chain-populated sections ─────────────────────────────────
    # When value_chain_edges are provided, populate Products, Raw materials,
    # Customers, Suppliers, and Value chain sections from the edges.
    # Sections without data remain as Phase 3 placeholders.
    vc_by_type: dict[str, list[dict]] = {}
    if value_chain_edges:
        for e in value_chain_edges:
            et = e.get("edge_type", "")
            vc_by_type.setdefault(et, []).append(e)

    # Build lookup tables for node labels.
    rm_by_id = {r.get("id", ""): r for r in (raw_materials or [])}
    prod_by_id = {p.get("id", ""): p for p in (products or [])}
    sup_by_id = {s.get("id", ""): s for s in (suppliers or [])}
    cust_by_id = {c.get("id", ""): c for c in (customers or [])}

    def _node_label(node_id: str) -> str:
        """Look up a human-readable label for a node ID."""
        if node_id in rm_by_id:
            return rm_by_id[node_id].get("name", node_id)
        if node_id in prod_by_id:
            return prod_by_id[node_id].get("name", node_id)
        if node_id in sup_by_id:
            return sup_by_id[node_id].get("name", node_id)
        if node_id in cust_by_id:
            return cust_by_id[node_id].get("name", node_id)
        return node_id

    def _format_vc_table(edges: list[dict]) -> str:
        """Render value-chain edges as a Markdown table."""
        if not edges:
            return "_(no data)_"
        lines = ["| Target | Type | Magnitude | % | Validation |", "|--------|------|-----------|---|------------|"]
        for e in sorted(edges, key=lambda x: x.get("edge_type", "")):
            target = _node_label(e.get("to_id", ""))
            etype = e.get("edge_type", "—")
            mag = e.get("magnitude") or "—"
            pct = f"{e['magnitude_percent']:.0f}%" if e.get("magnitude_percent") is not None else "—"
            val = e.get("validation_status", "hypothesized")
            lines.append(f"| {target} | `{etype}` | {mag} | {pct} | {val} |")
        return "\n".join(lines)

    # Products section
    produces_edges = vc_by_type.get("produces", [])
    if produces_edges:
        sections.append("## Products")
        sections.append("")
        sections.append(_format_vc_table(produces_edges))
        sections.append("")
    else:
        sections.append("## Products")
        sections.append("")
        sections.append("_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_")
        sections.append("")

    # Customers section
    customer_edges = vc_by_type.get("customer_of", [])
    if customer_edges:
        sections.append("## Customers")
        sections.append("")
        sections.append(_format_vc_table(customer_edges))
        sections.append("")
    else:
        sections.append("## Customers")
        sections.append("")
        sections.append("_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_")
        sections.append("")

    # Suppliers section
    supplier_edges = [e for e in vc_by_type.get("depends_on", []) if e.get("to_id", "") in sup_by_id]
    if supplier_edges:
        sections.append("## Suppliers")
        sections.append("")
        sections.append(_format_vc_table(supplier_edges))
        sections.append("")
    else:
        sections.append("## Suppliers")
        sections.append("")
        sections.append("_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_")
        sections.append("")

    # Raw materials section
    rm_edges = [e for e in (vc_by_type.get("uses", []) + vc_by_type.get("depends_on", []))
                if e.get("to_id", "") in rm_by_id]
    if rm_edges:
        sections.append("## Raw materials")
        sections.append("")
        sections.append(_format_vc_table(rm_edges))
        sections.append("")
    else:
        sections.append("## Raw materials")
        sections.append("")
        sections.append("_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_")
        sections.append("")

    # Remaining placeholder sections (Cost drivers, Capital structure, etc.)
    remaining_placeholders = [
        ("Cost drivers", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
        ("Capital structure", "_(Not yet researched — to be filled in Phase 3 from annual reports and credit rating rationales.)_"),
        ("Management / promoters", "_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_"),
        ("Risks", "_(Not yet researched — to be filled in Phase 3 from DRHPs and credit rating rationales.)_"),
    ]
    for section_title, body in remaining_placeholders:
        sections.append(f"## {section_title}")
        sections.append("")
        sections.append(body)
        sections.append("")

    # Value chain section (full edge table if edges exist)
    if value_chain_edges:
        sections.append("## Value chain")
        sections.append("")
        sections.append(f"_{len(value_chain_edges)} value-chain edges on record._")
        sections.append("")
        sections.append(_format_vc_table(value_chain_edges))
        sections.append("")
    else:
        sections.append("## Value chain")
        sections.append("")
        sections.append("_(Not yet researched — to be filled in Phase 3 from DRHPs and supply-chain analysis.)_")
        sections.append("")

    # Evidence / Hypotheses / Validated relationships placeholders
    for section_title, body in [
        ("Evidence", "_(No evidence records yet — Phase 3 will populate from source documents.)_"),
        ("Hypotheses", "_(No hypotheses yet — Phase 3 will record inferred relationships.)_"),
        ("Validated relationships", "_(No validated relationships yet — Phase 4 will validate via rolling betas, event studies, and shock analysis.)_"),
    ]:
        sections.append(f"## {section_title}")
        sections.append("")
        sections.append(body)
        sections.append("")

    # Financials (populated from observations)
    sections.append("## Financials")
    sections.append("")
    sections.append(f"_{len(observations)} observations on record._")
    sections.append("")
    if price_obs:
        sections.append("### Price observations")
        sections.append("")
        sections.append(format_observations_table(price_obs))
        sections.append("")
    if volume_obs:
        sections.append("### Volume observations")
        sections.append("")
        sections.append(format_observations_table(volume_obs))
        sections.append("")
    if turnover_obs:
        sections.append("### Turnover observations")
        sections.append("")
        sections.append(format_observations_table(turnover_obs))
        sections.append("")
    if not observations:
        sections.append("_(No financial observations on record.)_")
        sections.append("")

    # Macro exposures — populated from structured Exposure records if available,
    # otherwise falls back to the Phase 1 placeholder summary.
    sections.append("## Macro exposures")
    sections.append("")
    if exposures:
        sections.append(_format_exposures_table(exposures, rm_by_id, {d.get("id", ""): d for d in (macro_drivers or [])}))
        sections.append("")
    else:
        macro_exposure_summary = _build_macro_exposures_summary(observations)
        sections.append(macro_exposure_summary)
        sections.append("")

    # Corporate actions (populated)
    sections.append("## Corporate actions")
    sections.append("")
    sections.append(format_corporate_actions_table(corp_actions))
    sections.append("")

    # Data quality
    sections.append("## Data quality")
    sections.append("")
    dq_lines = [
        f"- **Observations count:** {len(observations)}",
        f"- **Corporate actions count:** {len(corp_actions)}",
        f"- **Price observations count:** {len(price_obs)}",
        f"- **Earliest observation:** {_earliest_date(observations)}",
        f"- **Latest observation:** {_latest_date(observations)}",
        f"- **Note last updated:** {last_updated.isoformat(timespec='seconds')}",
        f"- **Data status:** Phase 1 (data pipeline) only — research sections are placeholders.",
    ]
    sections.extend(dq_lines)
    sections.append("")

    return "\n".join(sections)


def _earliest_date(observations: list[Observation]) -> str:
    if not observations:
        return "—"
    return min(o.as_of for o in observations).isoformat()


def _latest_date(observations: list[Observation]) -> str:
    if not observations:
        return "—"
    return max(o.as_of for o in observations).isoformat()


def _build_macro_exposures_summary(observations: list[Observation]) -> str:
    """Build a summary of macro exposures.

    Phase 1 limitation: we don't yet have explicit exposure records (those
    come in Phase 3). What we CAN do is note which macro drivers existed
    during the same time window as the company's price observations.

    This is a placeholder that flags the relevant drivers for Phase 3 research.
    """
    if not observations:
        return "_(No observations — cannot determine macro exposure window.)_"

    company_dates = [o.as_of for o in observations]
    earliest = min(company_dates)
    latest = max(company_dates)

    return (
        f"_(Phase 1 limitation: explicit exposure records are a Phase 3 task. "
        f"This company has price observations from **{earliest.isoformat()}** to "
        f"**{latest.isoformat()}**. During this window, the following macro drivers "
        f"were tracked by InvestorLens:)_\n\n"
        f"- **Interest rates (RBI):** policy_repo_rate, sdf_rate, msf_rate, bank_rate, crr, slr, fixed_reverse_repo_rate\n"
        f"- **FX rates:** USD/INR, EUR/INR, GBP/INR, JPY/INR\n"
        f"- **Inflation:** CPI Combined YoY, CPI Rural YoY, CPI Urban YoY\n\n"
        f"_(Phase 3 will research which of these drivers materially affect this company, "
        f"with evidence from annual reports and DRHPs.)_"
    )


def _format_exposures_table(
    exposures: list[dict],
    rm_by_id: dict[str, dict],
    drv_by_id: dict[str, dict],
) -> str:
    """Render exposure records as a Markdown table.

    Columns: Driver | Direction | Transmission | Pricing Power | Hedge | Lag | Magnitude | Metric | Validation
    """
    if not exposures:
        return "_(no exposure records)_"

    def _label(driver_id: str) -> str:
        if driver_id in rm_by_id:
            return rm_by_id[driver_id].get("name", driver_id)
        if driver_id in drv_by_id:
            return drv_by_id[driver_id].get("label", driver_id)
        return driver_id

    lines = [
        "| Driver | Direction | Transmission | Pricing Power | Hedge | Lag (days) | Magnitude | Metric | Validation |",
        "|--------|-----------|-------------|---------------|-------|-----------|-----------|--------|------------|",
    ]
    for e in sorted(exposures, key=lambda x: x.get("direction", "")):
        driver = _label(e.get("driver_id", ""))
        direction = e.get("direction", "—")
        transmission = e.get("transmission_mechanism", "—")
        pricing = e.get("pricing_power", "—")
        hedge = e.get("hedge_status", "—")
        lag = str(e.get("pass_through_lag_days") or "—")
        magnitude = e.get("magnitude_estimate") or "—"
        if len(magnitude) > 60:
            magnitude = magnitude[:57] + "…"
        metric = e.get("financial_metric_impacted", "—")
        validation = e.get("validation_status", "hypothesized")
        lines.append(
            f"| {driver} | {direction} | {transmission} | {pricing} | {hedge} | {lag} | {magnitude} | {metric} | {validation} |"
        )
    return "\n".join(lines)
