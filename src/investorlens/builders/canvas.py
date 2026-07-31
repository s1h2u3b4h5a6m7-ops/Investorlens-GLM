"""
Obsidian Canvas generator for InvestorLens.

Produces two kinds of canvas files in the OpenJSONCanvas format (which is
just a JSON file with `{"nodes": [...], "edges": [...]}`):

1. **Sector canvases** — one `.canvas` per sector, containing:
   - A text node for the sector title
   - File nodes for each company in the sector (linking to the Markdown note)
   - Edges from the sector node to each company node (label: "contains")

2. **Index canvas** — a top-level `index.canvas` linking to all sector canvases:
   - A text node for the InvestorLens title
   - File nodes for each sector canvas
   - Edges from the index to each sector

Layout: deterministic grid. No Graphviz dependency — keeps the build simple
and reproducible. For ≤80 nodes per sector canvas, a simple 8-column grid
works well.

Node IDs: use the ISIN master record ID (`isin_<hash>`) for company nodes,
and `make_id("sctr", {"name": sector_slug})` for sector nodes. These are
stable and traceable to the knowledge graph.

The OpenJSONCanvas format:
  {
    "nodes": [
      {"id": "...", "type": "text", "x": 0, "y": 0, "width": 250, "height": 250, "text": "..."},
      {"id": "...", "type": "file", "x": 300, "y": 0, "width": 250, "height": 250, "file": "path/to/note.md"}
    ],
    "edges": [
      {"id": "...", "fromNode": "...", "toNode": "...", "label": "contains"}
    ]
  }

Pure functions: take data, return dict. No I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..ids import make_id
from .notes import slugify_company

__all__ = [
    "build_sector_canvas",
    "build_index_canvas",
    "MAX_NODES_PER_CANVAS",
    "GRID_COLUMNS",
    "NODE_WIDTH",
    "NODE_HEIGHT",
    "X_SPACING",
    "Y_SPACING",
]

# Layout constants — deterministic, no randomness.
MAX_NODES_PER_CANVAS = 80
GRID_COLUMNS = 8
NODE_WIDTH = 250
NODE_HEIGHT = 250
X_SPACING = 300  # distance between left edges of adjacent columns
Y_SPACING = 300  # distance between top edges of adjacent rows

# Title node dimensions (slightly wider/taller for prominence).
TITLE_WIDTH = 500
TITLE_HEIGHT = 120


def _grid_position(index: int, *, start_x: int = 0, start_y: int = 0) -> tuple[int, int]:
    """Compute (x, y) for the node at grid position `index`.

    Grid is left-to-right, top-to-bottom, GRID_COLUMNS wide.
    """
    col = index % GRID_COLUMNS
    row = index // GRID_COLUMNS
    x = start_x + col * X_SPACING
    y = start_y + row * Y_SPACING
    return x, y


def _sector_node_id(sector_name: str) -> str:
    """Compute a stable sector node ID from the sector name.

    Uses the `sctr` prefix (introduced in Milestone 2.2 to resolve the
    `sec_` prefix collision between Sector and Security models).
    """
    slug = sector_name.lower().strip().replace(" ", "_").replace("/", "_")
    return make_id("sctr", {"name": slug})


def _edge_id(from_id: str, to_id: str) -> str:
    """Compute a deterministic edge ID from its endpoints."""
    raw = f"{from_id}->{to_id}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"edge_{h}"


def _company_note_path(company: dict) -> str:
    """Return the vault-relative path to the company's Markdown note."""
    slug = slugify_company(
        company.get("company_name", ""),
        nse_symbol=company.get("nse_symbol"),
        isin=company.get("isin"),
    )
    return f"notes/companies/{slug}.md"


# ---------------------------------------------------------------------------
# Sector canvas
# ---------------------------------------------------------------------------


def build_sector_canvas(
    sector_name: str,
    companies: list[dict],
    *,
    canvas_path: str | None = None,
) -> dict[str, Any]:
    """Build a sector canvas containing all companies in that sector.

    Args:
        sector_name: the display name of the sector (e.g. "Pharmaceuticals").
        companies: list of ISIN master record dicts belonging to this sector.
            Each should have at least: id, isin, company_name, nse_symbol.
        canvas_path: optional vault-relative path to this canvas file (used
            in the index canvas to link back). Not stored in the canvas itself.

    Returns:
        An OpenJSONCanvas dict with:
          - 1 text node for the sector title
          - Up to MAX_NODES_PER_CANVAS file nodes for companies
          - Edges from the title node to each company node (label: "contains")
          - If truncated, a text node noting the truncation

    Companies are sorted alphabetically by company_name for deterministic
    ordering. If the sector has >MAX_NODES_PER_CANVAS companies, only the
    first MAX_NODES_PER_CANVAS are included (with a truncation note).
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    # Sort companies alphabetically for deterministic output.
    sorted_companies = sorted(companies, key=lambda c: (c.get("company_name") or "").lower())

    # Truncate if necessary.
    truncated = len(sorted_companies) > MAX_NODES_PER_CANVAS
    if truncated:
        visible_companies = sorted_companies[:MAX_NODES_PER_CANVAS]
    else:
        visible_companies = sorted_companies

    # Title node — centered above the grid.
    title_x = max(0, (GRID_COLUMNS * X_SPACING - TITLE_WIDTH) // 2)
    title_text = f"# {sector_name}\n\n{len(visible_companies)} companies"
    if truncated:
        title_text += f" (showing {MAX_NODES_PER_CANVAS} of {len(sorted_companies)})"
    sector_node_id = _sector_node_id(sector_name)
    nodes.append({
        "id": sector_node_id,
        "type": "text",
        "x": title_x,
        "y": 0,
        "width": TITLE_WIDTH,
        "height": TITLE_HEIGHT,
        "text": title_text,
    })

    # Company file nodes in a grid below the title.
    grid_start_y = TITLE_HEIGHT + 50  # 50px gap below title
    for i, company in enumerate(visible_companies):
        x, y = _grid_position(i, start_x=0, start_y=grid_start_y)
        note_path = _company_note_path(company)
        company_node_id = company.get("id", f"unknown_{i}")
        nodes.append({
            "id": company_node_id,
            "type": "file",
            "x": x,
            "y": y,
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
            "file": note_path,
        })
        edges.append({
            "id": _edge_id(sector_node_id, company_node_id),
            "fromNode": sector_node_id,
            "toNode": company_node_id,
            "label": "contains",
        })

    # Truncation note (if applicable).
    if truncated:
        trunc_y = grid_start_y + ((MAX_NODES_PER_CANVAS // GRID_COLUMNS) + 1) * Y_SPACING
        nodes.append({
            "id": f"{sector_node_id}_truncation_note",
            "type": "text",
            "x": 0,
            "y": trunc_y,
            "width": TITLE_WIDTH,
            "height": 60,
            "text": (
                f"Truncated: showing {MAX_NODES_PER_CANVAS} of {len(sorted_companies)} companies. "
                f"Use the web graph (Phase 2.3) for full sector exploration."
            ),
        })

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Index canvas
# ---------------------------------------------------------------------------


def build_index_canvas(
    sectors: list[tuple[str, list[dict]]],
    *,
    sector_canvas_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the top-level index canvas linking to all sector canvases.

    Args:
        sectors: list of (sector_name, companies) tuples, one per sector.
            Only sectors with at least 1 company should be included.
        sector_canvas_paths: optional dict mapping sector_name → vault-relative
            path to the sector's .canvas file. If provided, sector nodes link
            to the canvas files; otherwise they're text nodes.

    Returns:
        An OpenJSONCanvas dict with:
          - 1 text node for the InvestorLens title
          - File nodes for each sector canvas (or text nodes if paths not given)
          - Edges from the title to each sector node
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    # Title node.
    total_companies = sum(len(c) for _, c in sectors)
    title_text = (
        f"# InvestorLens\n\n"
        f"{len(sectors)} sectors | {total_companies} companies\n\n"
        "Click a sector node to open its canvas."
    )
    title_x = max(0, (GRID_COLUMNS * X_SPACING - TITLE_WIDTH) // 2)
    nodes.append({
        "id": "investorlens_index",
        "type": "text",
        "x": title_x,
        "y": 0,
        "width": TITLE_WIDTH,
        "height": TITLE_HEIGHT,
        "text": title_text,
    })

    # Sort sectors alphabetically for deterministic output.
    sorted_sectors = sorted(sectors, key=lambda s: s[0].lower())

    # Sector nodes in a grid below the title.
    grid_start_y = TITLE_HEIGHT + 50
    for i, (sector_name, companies) in enumerate(sorted_sectors):
        x, y = _grid_position(i, start_x=0, start_y=grid_start_y)
        sector_id = _sector_node_id(sector_name)
        company_count = len(companies)

        if sector_canvas_paths and sector_name in sector_canvas_paths:
            # File node linking to the sector canvas.
            nodes.append({
                "id": sector_id,
                "type": "file",
                "x": x,
                "y": y,
                "width": NODE_WIDTH,
                "height": NODE_HEIGHT,
                "file": sector_canvas_paths[sector_name],
            })
        else:
            # Text node (fallback when canvas path not yet known).
            nodes.append({
                "id": sector_id,
                "type": "text",
                "x": x,
                "y": y,
                "width": NODE_WIDTH,
                "height": NODE_HEIGHT,
                "text": f"## {sector_name}\n\n{company_count} companies",
            })

        edges.append({
            "id": _edge_id("investorlens_index", sector_id),
            "fromNode": "investorlens_index",
            "toNode": sector_id,
            "label": "sector",
        })

    return {"nodes": nodes, "edges": edges}
