"""
Sector knowledge note builder for Phase 3.

Takes a priority sector record + its value-chain edges + raw materials +
products and produces a human-readable Markdown note with YAML frontmatter.

The note structure:
  - YAML frontmatter (machine-readable, Dataview-compatible)
  - Title + overview
  - Rationale (why this sector was chosen)
  - Raw materials (table with cost % where known)
  - Products (table)
  - Macro exposures (from value-chain edges)
  - Cost drivers (from the priority sector registry)
  - Value-chain edges (full table with evidence + validation status)
  - Data quality

Pure function: takes records, returns a Markdown string. No I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import ValidationStatus, ValueChainEdge, ValueChainEdgeType
from ..models.provenance import Provenance

__all__ = [
    "build_sector_note",
    "format_value_chain_edges_table",
]


def _yaml_escape(s: str) -> str:
    """Escape a string for safe YAML scalar value."""
    if s is None:
        return '""'
    s = str(s)
    if any(c in s for c in [":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "<", ">", "=", "!", "%", "@", "`"]):
        return '"' + s.replace('"', '\\"') + '"'
    if s.strip() != s or not s:
        return '"' + s + '"'
    return s


def format_value_chain_edges_table(edges: list[ValueChainEdge]) -> str:
    """Render value-chain edges as a Markdown table."""
    if not edges:
        return "_(no value-chain edges on record)_"

    # Sort by edge type, then by from_id, then by to_id.
    sorted_edges = sorted(edges, key=lambda e: (e.edge_type.value, e.from_id, e.to_id))

    lines = [
        "| Type | From | To | Magnitude | % | Validation | Evidence |",
        "|------|------|-----|-----------|---|------------|----------|",
    ]
    for e in sorted_edges:
        magnitude = e.magnitude or "—"
        pct = f"{e.magnitude_percent:.0f}%" if e.magnitude_percent is not None else "—"
        validation = e.validation_status.value
        evidence = (evidence[:60] + "…") if (evidence := (e.evidence or "")) and len(evidence) > 60 else (e.evidence or "—")
        lines.append(
            f"| `{e.edge_type.value}` | `{e.from_id}` | `{e.to_id}` | {magnitude} | {pct} | {validation} | {evidence} |"
        )
    return "\n".join(lines)


def build_sector_note(
    sector: dict,
    edges: list[ValueChainEdge],
    raw_materials: list[dict],
    products: list[dict],
    *,
    last_updated: datetime | None = None,
) -> str:
    """Build a Markdown knowledge note for a single priority sector.

    Args:
        sector: the priority sector record (from priority_sectors.jsonl).
            Must have: sector_name, slug, priority, rationale,
            key_raw_materials, key_cost_drivers, key_macro_exposures.
        edges: value-chain edges where from_id is this sector's sctr_ ID.
        raw_materials: all raw material records (list of dicts with id, name, etc.).
        products: all product records (list of dicts with id, name, etc.).
        last_updated: UTC timestamp. Defaults to now().

    Returns:
        A complete Markdown string with YAML frontmatter and all sections.
    """
    if last_updated is None:
        last_updated = datetime.now()

    sector_name = sector.get("sector_name", "(unknown)")
    slug = sector.get("slug", sector_name.lower().replace(" ", "_"))

    # Build lookup tables for raw materials and products.
    rm_by_id: dict[str, dict] = {rm.get("id", ""): rm for rm in raw_materials}
    prod_by_id: dict[str, dict] = {p.get("id", ""): p for p in products}

    # Separate edges by type.
    uses_edges = [e for e in edges if e.edge_type in (ValueChainEdgeType.USES, ValueChainEdgeType.DEPENDS_ON)]
    produces_edges = [e for e in edges if e.edge_type == ValueChainEdgeType.PRODUCES]
    exposure_edges = [e for e in edges if e.edge_type in (ValueChainEdgeType.EXPOSED_TO, ValueChainEdgeType.BENEFITS_FROM, ValueChainEdgeType.HURT_BY)]

    # YAML frontmatter
    fm_lines = ["---"]
    fm_lines.append(f"sector_name: {_yaml_escape(sector_name)}")
    fm_lines.append(f"slug: {_yaml_escape(slug)}")
    fm_lines.append(f"priority: {sector.get('priority', 0)}")
    fm_lines.append(f"edge_count: {len(edges)}")
    fm_lines.append(f"last_updated: {_yaml_escape(last_updated.isoformat(timespec='seconds'))}")
    fm_lines.append(f"data_status: researched_partial  # Phase 3 seed data; Milestone 3.2 will validate with document evidence")
    fm_lines.append("---")
    fm = "\n".join(fm_lines)

    # Title
    title = f"# {sector_name}"

    # Overview
    overview_lines = [
        f"**Priority:** {sector.get('priority', '—')}  ",
        f"**Slug:** `{slug}`  ",
        f"**Value-chain edges:** {len(edges)} ({len(uses_edges)} uses/depends, {len(produces_edges)} produces, {len(exposure_edges)} exposures)  ",
    ]
    overview = "\n".join(overview_lines)

    # Rationale
    rationale = f"## Rationale\n\n{sector.get('rationale', '_(not specified)_')}"

    # Key raw materials (from the sector registry, not from edges)
    rm_list = sector.get("key_raw_materials", [])
    rm_section = "## Key raw materials\n\n"
    if rm_list:
        rm_section += "| Raw material | Notes |\n|--------------|-------|\n"
        for rm in rm_list:
            rm_section += f"| {rm} | _(details to be researched in Milestone 3.2)_ |\n"
    else:
        rm_section += "_(not specified)_\n"

    # Key cost drivers
    cd_list = sector.get("key_cost_drivers", [])
    cd_section = "## Key cost drivers\n\n"
    if cd_list:
        cd_section += "| Cost driver | Notes |\n|-------------|-------|\n"
        for cd in cd_list:
            cd_section += f"| {cd} | _(magnitude to be quantified in Milestone 3.2)_ |\n"
    else:
        cd_section += "_(not specified)_\n"

    # Key macro exposures
    me_list = sector.get("key_macro_exposures", [])
    me_section = "## Key macro exposures\n\n"
    if me_list:
        me_section += "| Macro driver | Direction | Notes |\n|---------------|-----------|-------|\n"
        for me in me_list:
            me_section += f"| {me} | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |\n"
    else:
        me_section += "_(not specified)_\n"

    # Products (from edges)
    prod_section = "## Products\n\n"
    if produces_edges:
        prod_section += "| Product | Magnitude | % | Validation |\n|---------|-----------|---|------------|\n"
        for e in produces_edges:
            prod_name = prod_by_id.get(e.to_id, {}).get("name", e.to_id)
            magnitude = e.magnitude or "—"
            pct = f"{e.magnitude_percent:.0f}%" if e.magnitude_percent is not None else "—"
            prod_section += f"| {prod_name} | {magnitude} | {pct} | {e.validation_status.value} |\n"
    else:
        prod_section += "_(no products on record)_\n"

    # Value-chain edges (full table)
    vce_section = f"## Value-chain edges\n\n{format_value_chain_edges_table(edges)}\n"

    # Data quality
    validated_count = sum(1 for e in edges if e.validation_status == ValidationStatus.VALIDATED)
    hypothesized_count = sum(1 for e in edges if e.validation_status == ValidationStatus.HYPOTHESIZED)
    weakly_count = sum(1 for e in edges if e.validation_status == ValidationStatus.WEAKLY_SUPPORTED)

    dq_section = "## Data quality\n\n"
    dq_section += f"- **Total edges:** {len(edges)}\n"
    dq_section += f"- **Validated:** {validated_count}\n"
    dq_section += f"- **Weakly supported:** {weakly_count}\n"
    dq_section += f"- **Hypothesized:** {hypothesized_count}\n"
    dq_section += f"- **Note last updated:** {last_updated.isoformat(timespec='seconds')}\n"
    dq_section += f"- **Data status:** Phase 3 seed data (publicly known industry structure). Milestone 3.2 will validate with evidence from DRHPs, annual reports, and credit rating rationales.\n"

    # Assemble
    sections = [
        fm, "", title, "", overview, "",
        rationale, "",
        rm_section,
        cd_section,
        me_section,
        prod_section,
        vce_section,
        dq_section,
    ]
    return "\n".join(sections)
