"""
Seed value-chain data for the 4 priority sectors (Phase 3, Milestone 3.1).

This script creates:
  1. data/master/priority_sectors.jsonl — registry of the 4 priority sectors
  2. data/master/raw_materials.jsonl — raw material records
  3. data/master/products.jsonl — product records
  4. data/processed/value_chain_edges.jsonl — value-chain edges

All data is based on publicly known industry structure (general knowledge,
not yet from specific DRHPs/annual reports — that's Milestone 3.2).
Every edge starts as HYPOTHESIZED with confidence=hypothesized, until
Milestone 3.2 research validates it with evidence from specific documents.

The 4 priority sectors (per ROADMAP):
  1. Pharma / API
  2. Cement
  3. Tyres
  4. Paints

Usage:
    python scripts/seed_value_chain.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import upsert_records, write_jsonl  # noqa: E402
from investorlens.models import (  # noqa: E402
    Product,
    Provenance,
    RawMaterial,
    ValueChainEdge,
    ValueChainEdgeType,
)
from investorlens.models.provenance import Confidence, ExtractionMethod  # noqa: E402

log = logging.getLogger("seed_value_chain")

PRIORITY_SECTORS_PATH = ROOT / "data" / "master" / "priority_sectors.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
PRODUCTS_PATH = ROOT / "data" / "master" / "products.jsonl"
VALUE_CHAIN_EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"


def _prov(notes: str) -> Provenance:
    """Create a hypothesized provenance for seed data."""
    return Provenance(
        source="investorlens",
        extraction_method=ExtractionMethod.DERIVED,
        confidence=Confidence.HYPOTHESIZED,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Priority sectors registry
# ---------------------------------------------------------------------------


PRIORITY_SECTORS = [
    {
        "sector_name": "Pharmaceuticals",
        "slug": "pharmaceuticals",
        "priority": 1,
        "rationale": "Clear cost drivers (APIs, KSMs), high import dependence on China, well-disclosed in DRHPs and annual reports.",
        "key_raw_materials": ["APIs", "KSMs (Key Starting Materials)", "Excipients", "Packaging"],
        "key_cost_drivers": ["API/KSM prices", "USD/INR (import dependence)", "Regulatory compliance (FDA/CDSCO)"],
        "key_macro_exposures": ["USD/INR", "Crude oil (packaging)", "Regulatory policy"],
    },
    {
        "sector_name": "Cement",
        "slug": "cement",
        "priority": 2,
        "rationale": "Commodity product with clear input structure (limestone, coal/power, gypsum). High energy cost (~40% of cost). Well-covered by rating agencies.",
        "key_raw_materials": ["Limestone", "Coal", "Fly ash", "Gypsum", "Clinker"],
        "key_cost_drivers": ["Coal/power (energy ~40%)", "Limestone (raw material)", "Freight/logistics", "Pet coke"],
        "key_macro_exposures": ["Coal prices", "USD/INR (coal/pet coke imports)", "Diesel (freight)", "Demand (construction cycle)"],
    },
    {
        "sector_name": "Tyres",
        "slug": "tyres",
        "priority": 3,
        "rationale": "Raw material cost is ~65% of revenue. Clear drivers: natural rubber, crude oil (synthetic rubber, carbon black). Well-disclosed in annual reports.",
        "key_raw_materials": ["Natural rubber", "Synthetic rubber", "Carbon black", "Steel (tyre cord)", "Nylon"],
        "key_cost_drivers": ["Natural rubber (30-35% of RM)", "Crude oil (synthetic rubber, carbon black)", "Steel"],
        "key_macro_exposures": ["Natural rubber prices", "Crude oil", "USD/INR (rubber imports)", "Automotive demand cycle"],
    },
    {
        "sector_name": "Paints",
        "slug": "paints",
        "priority": 4,
        "rationale": "Raw material cost is ~55% of revenue. Highly dependent on crude oil derivatives (titanium dioxide, resins, solvents). Concentrated market (Asian Paints ~50% share).",
        "key_raw_materials": ["Titanium dioxide", "Resins", "Solvents", "Pigments", "Additives"],
        "key_cost_drivers": ["Crude oil derivatives (TiO2, resins, solvents ~50% of RM)", "Packaging", "Freight"],
        "key_macro_exposures": ["Crude oil", "USD/INR (TiO2 imports)", "Demand (construction/real estate)"],
    },
]


# ---------------------------------------------------------------------------
# Raw materials
# ---------------------------------------------------------------------------


RAW_MATERIALS = [
    # Pharma
    {"name": "Active Pharmaceutical Ingredient (API)", "category": "chemical", "unit": "kg", "description": "The biologically active component in a drug"},
    {"name": "Key Starting Material (KSM)", "category": "chemical", "unit": "kg", "description": "The basic chemical input used to synthesize APIs"},
    {"name": "Excipients", "category": "chemical", "unit": "kg", "description": "Inactive substances used as carriers for APIs"},
    {"name": "Pharma Packaging", "category": "material", "unit": "unit", "description": "Blister packs, bottles, vials"},
    # Cement
    {"name": "Limestone", "category": "mineral", "unit": "tonne", "description": "Primary raw material for cement (~1.5 tonnes per tonne of cement)"},
    {"name": "Coal", "category": "energy", "unit": "tonne", "description": "Primary fuel for clinkerization; ~40% of cement cost"},
    {"name": "Fly Ash", "category": "mineral", "unit": "tonne", "description": "By-product of thermal power plants; used as a supplementary cementitious material"},
    {"name": "Gypsum", "category": "mineral", "unit": "tonne", "description": "Added to clinker to control setting time (~3-5%)"},
    {"name": "Clinker", "category": "mineral", "unit": "tonne", "description": "Intermediate product; ground with gypsum to make cement"},
    {"name": "Pet Coke", "category": "energy", "unit": "tonne", "description": "Alternative fuel for cement kilns; cheaper than coal"},
    # Tyres
    {"name": "Natural Rubber", "category": "agricultural", "unit": "kg", "description": "30-35% of tyre raw material cost; primarily imported from SE Asia"},
    {"name": "Synthetic Rubber", "category": "chemical", "unit": "kg", "description": "Derived from crude oil; used for performance tyres"},
    {"name": "Carbon Black", "category": "chemical", "unit": "kg", "description": "Reinforcing filler; derived from crude oil"},
    {"name": "Steel Tyre Cord", "category": "metal", "unit": "kg", "description": "Steel wire used for reinforcement in radial tyres"},
    {"name": "Nylon Tyre Cord", "category": "chemical", "unit": "kg", "description": "Fabric reinforcement for bias tyres"},
    # Paints
    {"name": "Titanium Dioxide", "category": "chemical", "unit": "kg", "description": "White pigment; ~20-25% of paint raw material cost; largely imported"},
    {"name": "Resins", "category": "chemical", "unit": "kg", "description": "Binder; acrylic, alkyd, epoxy; derived from crude oil"},
    {"name": "Solvents", "category": "chemical", "unit": "litre", "description": "Derived from crude oil; used to dissolve resins"},
    {"name": "Pigments", "category": "chemical", "unit": "kg", "description": "Colorants; organic and inorganic"},
    {"name": "Paint Additives", "category": "chemical", "unit": "kg", "description": "Defoamers, thickeners, biocides, etc."},
    # Cross-sector: macro inputs
    {"name": "Crude Oil", "category": "energy", "unit": "barrel", "description": "Base input for many chemical raw materials (synthetic rubber, resins, solvents, carbon black, TiO2)"},
]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


PRODUCTS = [
    # Pharma
    {"name": "Generic Formulations", "category": "generic", "description": "Off-patent drugs in finished dosage forms (tablets, capsules, injectables)"},
    {"name": "APIs (Active Pharmaceutical Ingredients)", "category": "generic", "description": "Bulk drugs sold to other formulators"},
    {"name": "Branded Formulations", "category": "branded", "description": "Patented or branded drugs"},
    # Cement
    {"name": "Portland Cement", "category": "commodity", "description": "Standard cement type (OPC, PPC, PSC)"},
    {"name": "Ready-Mix Concrete", "category": "commodity", "description": "Pre-mixed concrete delivered to construction sites"},
    # Tyres
    {"name": "Passenger Car Tyres", "category": "branded", "description": "Radial tyres for cars and SUVs"},
    {"name": "Commercial Vehicle Tyres", "category": "branded", "description": "Truck and bus tyres; bias and radial"},
    {"name": "Two-Wheeler Tyres", "category": "branded", "description": "Motorcycle and scooter tyres"},
    {"name": "Off-Highway Tyres", "category": "branded", "description": "Tractor, OTR, industrial tyres"},
    # Paints
    {"name": "Decorative Paints", "category": "branded", "description": "Architectural paints for homes and buildings (~70% of paint industry revenue)"},
    {"name": "Industrial Paints", "category": "specialty", "description": "Powder coatings, automotive coatings, protective coatings"},
]


# ---------------------------------------------------------------------------
# Value-chain edges
# ---------------------------------------------------------------------------


def _make_edges() -> list[ValueChainEdge]:
    """Create value-chain edges for the 4 priority sectors.

    These connect sectors → raw materials (depends_on/uses) and
    sectors → products (produces), plus sectors → macro drivers (exposed_to).

    All edges are HYPOTHESIZED — Milestone 3.2 will validate with evidence.
    """
    from investorlens.ids import make_id

    edges: list[ValueChainEdge] = []
    prov = _prov("Seed data from publicly known industry structure; not yet validated with specific document evidence (Milestone 3.2).")

    # Map sector names to their "sector node IDs" for the from_id.
    # We use the sector's sctr_ ID as the from_id.
    def _sctr(sector_name: str) -> str:
        from investorlens.builders.graph import slugify_sector
        return make_id("sctr", {"name": slugify_sector(sector_name)})

    def _rm(name: str) -> str:
        return make_id("rm", {"name": name.lower().strip()})

    def _prod(name: str) -> str:
        return make_id("prod", {"name": name.lower().strip()})

    def _drv(slug: str) -> str:
        return make_id("drv", {"slug": slug})

    # ─── Pharma / API ────────────────────────────────────────────────
    pharma = _sctr("Pharmaceuticals")
    edges.extend([
        ValueChainEdge(from_id=pharma, to_id=_rm("Active Pharmaceutical Ingredient (API)"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Primary input", magnitude_percent=50.0,
                       time_period="current", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_rm("Key Starting Material (KSM)"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Import dependent on China (~70%)",
                       magnitude_percent=70.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_rm("Excipients"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Minor input", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_rm("Pharma Packaging"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Minor input", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_prod("Generic Formulations"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="Primary product", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_prod("APIs (Active Pharmaceutical Ingredients)"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="Some companies are API-focused", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.EXPOSED_TO, magnitude="Negative: API/KSM imports",
                       time_period="current", provenance=prov),
        ValueChainEdge(from_id=pharma, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.BENEFITS_FROM, magnitude="Positive: export revenue (US generics)",
                       time_period="current", provenance=prov),
    ])

    # ─── Cement ──────────────────────────────────────────────────────
    cement = _sctr("Cement")
    edges.extend([
        ValueChainEdge(from_id=cement, to_id=_rm("Limestone"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Primary raw material (~1.5t per t cement)",
                       provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_rm("Coal"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Energy ~40% of cost",
                       magnitude_percent=40.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_rm("Pet Coke"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Alternative fuel; cheaper than coal",
                       provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_rm("Fly Ash"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Supplementary cementitious material",
                       provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_rm("Gypsum"),
                       edge_type=ValueChainEdgeType.USES, magnitude="3-5% of input", provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_prod("Portland Cement"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="Primary product", provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_prod("Ready-Mix Concrete"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="Value-added product", provenance=prov),
        ValueChainEdge(from_id=cement, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: coal/pet coke imports",
                       time_period="current", provenance=prov),
    ])

    # ─── Tyres ───────────────────────────────────────────────────────
    tyres = _sctr("Tyres")
    edges.extend([
        ValueChainEdge(from_id=tyres, to_id=_rm("Natural Rubber"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="30-35% of raw material cost",
                       magnitude_percent=32.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_rm("Synthetic Rubber"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Derived from crude oil",
                       provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_rm("Carbon Black"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Reinforcing filler; crude oil derivative",
                       provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_rm("Steel Tyre Cord"),
                       edge_type=ValueChainEdgeType.USES, magnitude="For radial tyres", provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_rm("Nylon Tyre Cord"),
                       edge_type=ValueChainEdgeType.USES, magnitude="For bias tyres", provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_prod("Passenger Car Tyres"),
                       edge_type=ValueChainEdgeType.PRODUCES, provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_prod("Commercial Vehicle Tyres"),
                       edge_type=ValueChainEdgeType.PRODUCES, provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_prod("Two-Wheeler Tyres"),
                       edge_type=ValueChainEdgeType.PRODUCES, provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_rm("Crude Oil"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON,
                       magnitude="Indirect: synthetic rubber + carbon black are crude derivatives",
                       provenance=prov),
        ValueChainEdge(from_id=tyres, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: natural rubber imports",
                       time_period="current", provenance=prov),
    ])

    # ─── Paints ──────────────────────────────────────────────────────
    paints = _sctr("Paints")
    edges.extend([
        ValueChainEdge(from_id=paints, to_id=_rm("Titanium Dioxide"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="~20-25% of RM cost; largely imported",
                       magnitude_percent=22.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_rm("Resins"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Binder; crude oil derivative",
                       provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_rm("Solvents"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Crude oil derivative", provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_rm("Pigments"),
                       edge_type=ValueChainEdgeType.USES, provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_rm("Paint Additives"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Minor but specialty", provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_prod("Decorative Paints"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="~70% of industry revenue",
                       magnitude_percent=70.0, provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_prod("Industrial Paints"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="~30% of industry revenue",
                       magnitude_percent=30.0, provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_rm("Crude Oil"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON,
                       magnitude="Indirect: TiO2, resins, solvents are crude derivatives (~50% of RM)",
                       magnitude_percent=50.0, provenance=prov),
        ValueChainEdge(from_id=paints, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: TiO2 imports",
                       time_period="current", provenance=prov),
    ])

    return edges


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log.info("Seeding priority sectors + value-chain data (Phase 3, Milestone 3.1)...")

    # 1. Priority sectors registry
    PRIORITY_SECTORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(PRIORITY_SECTORS_PATH, PRIORITY_SECTORS)
    log.info("Wrote %d priority sectors to %s", len(PRIORITY_SECTORS), PRIORITY_SECTORS_PATH)

    # 2. Raw materials
    prov_rm = _prov("Seed raw material definitions from publicly known industry structure.")
    rm_records = [RawMaterial(**rm, provenance=prov_rm) for rm in RAW_MATERIALS]
    rm_payload = [r.model_dump(mode="json", exclude_none=True) for r in rm_records]
    write_jsonl(RAW_MATERIALS_PATH, rm_payload)
    log.info("Wrote %d raw materials to %s", len(rm_records), RAW_MATERIALS_PATH)

    # 3. Products
    prov_prod = _prov("Seed product definitions from publicly known industry structure.")
    prod_records = [Product(**p, provenance=prov_prod) for p in PRODUCTS]
    prod_payload = [p.model_dump(mode="json", exclude_none=True) for p in prod_records]
    write_jsonl(PRODUCTS_PATH, prod_payload)
    log.info("Wrote %d products to %s", len(prod_records), PRODUCTS_PATH)

    # 4. Value-chain edges
    edges = _make_edges()
    edge_payload = [e.model_dump(mode="json", exclude_none=True) for e in edges]
    upsert_records(VALUE_CHAIN_EDGES_PATH, edge_payload, key="id")
    log.info("Wrote %d value-chain edges to %s", len(edges), VALUE_CHAIN_EDGES_PATH)

    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
