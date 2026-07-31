"""
Knowledge graph data builder for the InvestorLens web graph.

Produces a JSON structure suitable for Cytoscape.js consumption:

  {
    "nodes": [
      {
        "data": {
          "id": "sec_...",           # stable node ID
          "label": "Reliance",        # display label
          "type": "company",          # company | sector | macro_driver
          "sector": "Refineries",     # for companies
          "isin": "INE002A01018",
          "nse_symbol": "RELIANCE",
          "exchange": "NSE+BSE",
          "observations_count": 41,
          "corporate_actions_count": 2
        }
      },
      ...
    ],
    "edges": [
      {
        "data": {
          "id": "edge_...",
          "source": "sec_...",        # company node ID
          "target": "sctr_...",       # sector node ID
          "label": "belongs_to",
          "type": "belongs_to"
        }
      },
      ...
    ],
    "metadata": {
      "generated_at": "2024-09-30T18:30:00Z",
      "node_count": 25,
      "edge_count": 20,
      "sectors": ["Pharmaceuticals", "Banks", ...],
      "data_status": "Phase 1 — data pipeline only"
    }
  }

Node types:
  - company: one per ISIN master record with observations or corp actions
  - sector: one per distinct sector (including "(Unclassified)")
  - macro_driver: one per distinct macro driver slug found in observations

Edge types (Phase 1):
  - belongs_to: company → sector
  - exposed_to: company → macro_driver (placeholder — Phase 3 will add evidence)

Edge types (Phase 3+, not yet populated):
  - supplies, customer_of, competes_with, depends_on, uses, produces

Pure function: takes ISIN master + observations + corp actions, returns dict.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..ids import make_id

__all__ = [
    "build_graph_data",
    "slugify_sector",
]

# Known macro driver slugs (from Milestone 1.5 parsers).
# These map drv_* subject_ids to human-readable labels + categories.
_MACRO_DRIVER_INFO: dict[str, dict[str, str]] = {
    "policy_repo_rate": {"label": "Policy Repo Rate", "category": "Interest Rate"},
    "sdf_rate": {"label": "SDF Rate", "category": "Interest Rate"},
    "msf_rate": {"label": "MSF Rate", "category": "Interest Rate"},
    "bank_rate": {"label": "Bank Rate", "category": "Interest Rate"},
    "crr": {"label": "CRR", "category": "Interest Rate"},
    "slr": {"label": "SLR", "category": "Interest Rate"},
    "fixed_reverse_repo_rate": {"label": "Reverse Repo Rate", "category": "Interest Rate"},
    "fx_usd_inr": {"label": "USD/INR", "category": "FX Rate"},
    "fx_eur_inr": {"label": "EUR/INR", "category": "FX Rate"},
    "fx_gbp_inr": {"label": "GBP/INR", "category": "FX Rate"},
    "fx_jpy_inr": {"label": "JPY/INR", "category": "FX Rate"},
    "cpi_combined_yoy": {"label": "CPI Combined YoY", "category": "Inflation"},
    "cpi_rural_yoy": {"label": "CPI Rural YoY", "category": "Inflation"},
    "cpi_urban_yoy": {"label": "CPI Urban YoY", "category": "Inflation"},
    "cpi_combined_index": {"label": "CPI Combined Index", "category": "Inflation"},
    "cpi_rural_index": {"label": "CPI Rural Index", "category": "Inflation"},
    "cpi_urban_index": {"label": "CPI Urban Index", "category": "Inflation"},
}


def slugify_sector(name: str) -> str:
    """Convert a sector name to a URL-safe slug."""
    s = name.lower().strip()
    s = s.replace(" ", "_").replace("/", "_").replace("&", "and")
    s = "".join(c for c in s if c.isalnum() or c == "_")
    return s or "unknown"


def _sector_node_id(sector_name: str) -> str:
    """Compute a stable sector node ID."""
    return make_id("sctr", {"name": slugify_sector(sector_name)})


def _make_edge_id(source: str, target: str, edge_type: str) -> str:
    """Deterministic edge ID."""
    import hashlib
    raw = f"{source}->{target}:{edge_type}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"edge_{h}"


def _extract_macro_driver_slug(subject_id: str) -> str | None:
    """If a subject_id is a macro driver (drv_*), extract its slug.

    The slug is the original key used to compute the drv_<hash> ID. Since we
    can't reverse the hash, we look it up in the known slugs table.
    """
    for slug, _info in _MACRO_DRIVER_INFO.items():
        if make_id("drv", {"slug": slug}) == subject_id:
            return slug
    return None


def build_graph_data(
    isin_master: list[dict],
    observations: list[dict],
    corp_actions: list[dict],
    *,
    value_chain_edges: list[dict] | None = None,
    raw_materials: list[dict] | None = None,
    products: list[dict] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the complete graph data structure for Cytoscape.js.

    Args:
        isin_master: list of ISIN master record dicts.
        observations: list of observation dicts (with subject_id, kind, etc.).
        corp_actions: list of corporate action dicts (with security_id, action_type, etc.).
        value_chain_edges: optional list of ValueChainEdge dicts (Phase 3). If provided,
            raw_material and product nodes are added and the edges are included.
        raw_materials: optional list of RawMaterial dicts (for node labels).
        products: optional list of Product dicts (for node labels).
        generated_at: UTC timestamp for metadata. Defaults to now().

    Returns:
        A dict with "nodes", "edges", and "metadata" keys, ready to serialize
        as JSON for the web graph.
    """
    if generated_at is None:
        generated_at = datetime.now()

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def _add_node(node_id: str, data: dict) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"data": {"id": node_id, **data}})

    def _add_edge(source: str, target: str, edge_type: str, label: str | None = None) -> None:
        edge_id = _make_edge_id(source, target, edge_type)
        edges.append({
            "data": {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": edge_type,
                "label": label or edge_type,
            }
        })

    # ─── Index observations + corp actions by subject/security ID ───────
    obs_count_by_subject: dict[str, int] = {}
    ca_count_by_security: dict[str, int] = {}
    macro_driver_subjects: set[str] = set()

    for obs in observations:
        sid = obs.get("subject_id")
        if sid:
            obs_count_by_subject[sid] = obs_count_by_subject.get(sid, 0) + 1
            # Check if this is a macro driver.
            if sid not in macro_driver_subjects and _extract_macro_driver_slug(sid):
                macro_driver_subjects.add(sid)

    for ca in corp_actions:
        sid = ca.get("security_id")
        if sid:
            ca_count_by_security[sid] = ca_count_by_security.get(sid, 0) + 1

    # ─── Sector nodes + company nodes + belongs_to edges ────────────────
    sectors_seen: set[str] = set()
    for company in isin_master:
        isin = company.get("isin")
        if not isin:
            continue
        security_id = make_id("sec", {"isin": isin})
        obs_count = obs_count_by_subject.get(security_id, 0)
        ca_count = ca_count_by_security.get(security_id, 0)

        # Skip companies with no data (no observations and no corp actions).
        if obs_count == 0 and ca_count == 0:
            continue

        # Sector node.
        sector_name = company.get("sector") or "(Unclassified)"
        if sector_name not in sectors_seen:
            sectors_seen.add(sector_name)
            sector_id = _sector_node_id(sector_name)
            _add_node(sector_id, {
                "label": sector_name,
                "type": "sector",
                "company_count": 0,  # will be incremented below
            })
        sector_id = _sector_node_id(sector_name)
        # Increment company_count on the sector node.
        for n in nodes:
            if n["data"]["id"] == sector_id:
                n["data"]["company_count"] = n["data"].get("company_count", 0) + 1
                break

        # Company node.
        company_label = company.get("nse_symbol") or company.get("company_name") or isin
        _add_node(security_id, {
            "label": company_label,
            "type": "company",
            "sector": sector_name,
            "isin": isin,
            "nse_symbol": company.get("nse_symbol"),
            "bse_code": company.get("bse_code"),
            "company_name": company.get("company_name"),
            "exchange": company.get("exchange"),
            "observations_count": obs_count,
            "corporate_actions_count": ca_count,
        })

        # belongs_to edge: company → sector.
        _add_edge(security_id, sector_id, "belongs_to", "belongs to")

    # ─── Macro driver nodes + exposed_to edges ──────────────────────────
    # For each company, create an "exposed_to" edge to every macro driver
    # that was tracked during the company's observation window. This is a
    # Phase 1 placeholder — Phase 3 will replace these with evidence-based
    # exposures.
    for macro_subject_id in sorted(macro_driver_subjects):
        slug = _extract_macro_driver_slug(macro_subject_id)
        if not slug:
            continue
        info = _MACRO_DRIVER_INFO.get(slug, {"label": slug, "category": "Macro"})
        _add_node(macro_subject_id, {
            "label": info["label"],
            "type": "macro_driver",
            "category": info["category"],
            "slug": slug,
        })

    # Create exposed_to edges from every company to every macro driver.
    # (Phase 1 placeholder — Phase 3 will filter these to evidence-based exposures.)
    company_node_ids = [n["data"]["id"] for n in nodes if n["data"].get("type") == "company"]
    macro_node_ids = [n["data"]["id"] for n in nodes if n["data"].get("type") == "macro_driver"]
    for company_id in company_node_ids:
        for macro_id in macro_node_ids:
            _add_edge(company_id, macro_id, "exposed_to", "exposed to")

    # ─── Value-chain edges (Phase 3) ────────────────────────────────────
    # If value_chain_edges are provided, add raw_material and product nodes
    # and include the value-chain edges (uses, depends_on, produces, etc.).
    vc_edge_count = 0
    if value_chain_edges:
        # Build lookup tables for raw materials and products.
        rm_by_id: dict[str, dict] = {rm.get("id", ""): rm for rm in (raw_materials or [])}
        prod_by_id: dict[str, dict] = {p.get("id", ""): p for p in (products or [])}

        for vc_edge in value_chain_edges:
            from_id = vc_edge.get("from_id")
            to_id = vc_edge.get("to_id")
            edge_type = vc_edge.get("edge_type")
            if not from_id or not to_id or not edge_type:
                continue

            # Ensure the from node exists (it should be a sector node already).
            # Ensure the to node exists — if it's a raw_material or product, add it.
            if to_id not in node_ids:
                if to_id in rm_by_id:
                    rm = rm_by_id[to_id]
                    _add_node(to_id, {
                        "label": rm.get("name", to_id),
                        "type": "raw_material",
                        "category": rm.get("category"),
                        "unit": rm.get("unit"),
                    })
                elif to_id in prod_by_id:
                    prod = prod_by_id[to_id]
                    _add_node(to_id, {
                        "label": prod.get("name", to_id),
                        "type": "product",
                        "category": prod.get("category"),
                    })
                else:
                    # Unknown target — add as a generic node.
                    _add_node(to_id, {
                        "label": to_id,
                        "type": "unknown",
                    })

            # Add the edge.
            magnitude = vc_edge.get("magnitude")
            magnitude_percent = vc_edge.get("magnitude_percent")
            validation = vc_edge.get("validation_status", "hypothesized")
            edge_label = edge_type.replace("_", " ")
            edges.append({
                "data": {
                    "id": vc_edge.get("id", _make_edge_id(from_id, to_id, edge_type)),
                    "source": from_id,
                    "target": to_id,
                    "type": edge_type,
                    "label": edge_label,
                    "magnitude": magnitude,
                    "magnitude_percent": magnitude_percent,
                    "validation_status": validation,
                }
            })
            vc_edge_count += 1

    # ─── Metadata ───────────────────────────────────────────────────────
    metadata = {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "company_count": len([n for n in nodes if n["data"].get("type") == "company"]),
        "sector_count": len([n for n in nodes if n["data"].get("type") == "sector"]),
        "macro_driver_count": len([n for n in nodes if n["data"].get("type") == "macro_driver"]),
        "raw_material_count": len([n for n in nodes if n["data"].get("type") == "raw_material"]),
        "product_count": len([n for n in nodes if n["data"].get("type") == "product"]),
        "value_chain_edge_count": vc_edge_count,
        "sectors": sorted(sectors_seen),
        "data_status": "Phase 3 — value-chain seed data (hypothesized). Milestone 3.2 will validate with document evidence.",
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": metadata,
    }
