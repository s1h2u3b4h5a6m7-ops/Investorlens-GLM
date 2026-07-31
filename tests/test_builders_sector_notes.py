"""Tests for the sector notes builder (investorlens.builders.sector_notes)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from investorlens.builders.sector_notes import (
    build_sector_note,
    format_value_chain_edges_table,
)
from investorlens.models import (
    Product,
    Provenance,
    RawMaterial,
    ValueChainEdge,
    ValueChainEdgeType,
)
from investorlens.models.provenance import Confidence, ExtractionMethod


@pytest.fixture
def prov() -> Provenance:
    return Provenance(
        source="investorlens",
        extraction_method=ExtractionMethod.DERIVED,
        confidence=Confidence.HYPOTHESIZED,
        notes="seed data",
    )


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def pharma_sector() -> dict:
    return {
        "sector_name": "Pharmaceuticals",
        "slug": "pharmaceuticals",
        "priority": 1,
        "rationale": "Clear cost drivers (APIs, KSMs), high import dependence on China.",
        "key_raw_materials": ["APIs", "KSMs", "Excipients", "Packaging"],
        "key_cost_drivers": ["API/KSM prices", "USD/INR", "Regulatory compliance"],
        "key_macro_exposures": ["USD/INR", "Crude oil", "Regulatory policy"],
    }


@pytest.fixture
def pharma_edges(prov: Provenance) -> list[ValueChainEdge]:
    # Use the actual computed IDs from the RawMaterial/Product models
    # so the builder's lookup tables find them.
    api_id = RawMaterial(name="Active Pharmaceutical Ingredient (API)", provenance=prov).id
    ksm_id = RawMaterial(name="Key Starting Material (KSM)", provenance=prov).id
    generics_id = Product(name="Generic Formulations", provenance=prov).id
    return [
        ValueChainEdge(
            from_id="sctr_pharma", to_id=api_id,
            edge_type=ValueChainEdgeType.USES,
            magnitude="Primary input", magnitude_percent=50.0,
            provenance=prov,
        ),
        ValueChainEdge(
            from_id="sctr_pharma", to_id=ksm_id,
            edge_type=ValueChainEdgeType.DEPENDS_ON,
            magnitude="Import dependent on China (~70%)",
            magnitude_percent=70.0,
            provenance=prov,
        ),
        ValueChainEdge(
            from_id="sctr_pharma", to_id=generics_id,
            edge_type=ValueChainEdgeType.PRODUCES,
            magnitude="Primary product",
            provenance=prov,
        ),
        ValueChainEdge(
            from_id="sctr_pharma", to_id="drv_fx_usd_inr",
            edge_type=ValueChainEdgeType.EXPOSED_TO,
            magnitude="Negative: imports",
            provenance=prov,
        ),
    ]


@pytest.fixture
def raw_materials(prov: Provenance) -> list[dict]:
    return [
        RawMaterial(name="Active Pharmaceutical Ingredient (API)", provenance=prov).model_dump(mode="json"),
        RawMaterial(name="Key Starting Material (KSM)", provenance=prov).model_dump(mode="json"),
    ]


@pytest.fixture
def products(prov: Provenance) -> list[dict]:
    return [
        Product(name="Generic Formulations", provenance=prov).model_dump(mode="json"),
    ]


class TestFormatValueChainEdgesTable:
    def test_empty_returns_placeholder(self) -> None:
        assert format_value_chain_edges_table([]) == "_(no value-chain edges on record)_"

    def test_renders_table_header(self, pharma_edges: list[ValueChainEdge]) -> None:
        table = format_value_chain_edges_table(pharma_edges)
        assert "| Type | From | To |" in table
        assert "|------|------|-----|" in table

    def test_includes_edge_type(self, pharma_edges: list[ValueChainEdge]) -> None:
        table = format_value_chain_edges_table(pharma_edges)
        assert "uses" in table
        assert "depends_on" in table
        assert "produces" in table
        assert "exposed_to" in table

    def test_includes_magnitude_and_percent(self, pharma_edges: list[ValueChainEdge]) -> None:
        table = format_value_chain_edges_table(pharma_edges)
        assert "Primary input" in table
        assert "50%" in table
        assert "70%" in table

    def test_includes_validation_status(self, pharma_edges: list[ValueChainEdge]) -> None:
        table = format_value_chain_edges_table(pharma_edges)
        assert "hypothesized" in table


class TestBuildSectorNote:
    def test_returns_markdown_string(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert isinstance(note, str)
        assert len(note) > 0

    def test_includes_yaml_frontmatter(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert note.startswith("---\n")
        fm = note.split("---\n")[1]
        assert "sector_name: Pharmaceuticals" in fm
        assert "slug: pharmaceuticals" in fm
        assert "priority: 1" in fm
        assert "edge_count: 4" in fm

    def test_title_uses_sector_name(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "# Pharmaceuticals" in note

    def test_includes_rationale(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Rationale" in note
        assert "Clear cost drivers" in note

    def test_includes_key_raw_materials(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Key raw materials" in note
        assert "APIs" in note
        assert "KSMs" in note

    def test_includes_cost_drivers(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Key cost drivers" in note
        assert "API/KSM prices" in note
        assert "USD/INR" in note

    def test_includes_macro_exposures(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Key macro exposures" in note
        assert "Crude oil" in note
        assert "Regulatory policy" in note

    def test_includes_products_section(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Products" in note
        assert "Generic Formulations" in note

    def test_includes_value_chain_edges_table(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Value-chain edges" in note
        assert "| Type | From | To |" in note

    def test_includes_data_quality(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert "## Data quality" in note
        assert "Total edges:** 4" in note
        assert "Hypothesized:** 4" in note
        assert "Validated:** 0" in note

    def test_deterministic_output(
        self,
        pharma_sector: dict,
        pharma_edges: list[ValueChainEdge],
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        a = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        b = build_sector_note(pharma_sector, pharma_edges, raw_materials, products, last_updated=fixed_ts)
        assert a == b

    def test_handles_empty_edges(
        self,
        pharma_sector: dict,
        raw_materials: list[dict],
        products: list[dict],
        fixed_ts: datetime,
    ) -> None:
        note = build_sector_note(pharma_sector, [], raw_materials, products, last_updated=fixed_ts)
        assert "_(no value-chain edges on record)_" in note
        assert "Total edges:** 0" in note
