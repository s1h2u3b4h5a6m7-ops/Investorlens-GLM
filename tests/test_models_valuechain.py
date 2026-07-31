"""Tests for the value-chain models (investorlens.models.valuechain)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from investorlens.models import (
    Customer,
    Product,
    RawMaterial,
    Supplier,
    ValidationStatus,
    ValueChainEdge,
    ValueChainEdgeType,
)
from investorlens.models.provenance import Confidence, Provenance


@pytest.fixture
def prov() -> Provenance:
    return Provenance(source="investorlens", confidence=Confidence.HYPOTHESIZED)


class TestRawMaterial:
    def test_id_derived_from_name(self, prov: Provenance) -> None:
        rm1 = RawMaterial(name="Crude Oil", provenance=prov)
        rm2 = RawMaterial(name="Crude Oil", provenance=prov)
        assert rm1.id == rm2.id
        assert rm1.id.startswith("rm_")

    def test_id_changes_with_name(self, prov: Provenance) -> None:
        rm1 = RawMaterial(name="Crude Oil", provenance=prov)
        rm2 = RawMaterial(name="Limestone", provenance=prov)
        assert rm1.id != rm2.id

    def test_case_insensitive_id(self, prov: Provenance) -> None:
        rm1 = RawMaterial(name="Crude Oil", provenance=prov)
        rm2 = RawMaterial(name="crude oil", provenance=prov)
        assert rm1.id == rm2.id

    def test_optional_fields(self, prov: Provenance) -> None:
        rm = RawMaterial(name="API", category="chemical", unit="kg", description="Active Pharma Ingredient", provenance=prov)
        assert rm.category == "chemical"
        assert rm.unit == "kg"
        assert rm.description == "Active Pharma Ingredient"

    def test_name_required(self, prov: Provenance) -> None:
        with pytest.raises(ValidationError):
            RawMaterial(name="", provenance=prov)


class TestSupplier:
    def test_id_derived_from_name(self, prov: Provenance) -> None:
        s1 = Supplier(name="China KSM Suppliers", provenance=prov)
        s2 = Supplier(name="China KSM Suppliers", provenance=prov)
        assert s1.id == s2.id
        assert s1.id.startswith("sup_")

    def test_category_supplier(self, prov: Provenance) -> None:
        s = Supplier(name="China KSM Suppliers", category="international", is_company=False, country="China", provenance=prov)
        assert s.is_company is False
        assert s.country == "China"

    def test_named_company_supplier(self, prov: Provenance) -> None:
        s = Supplier(name="Reliance Industries", is_company=True, company_id="co_abc", provenance=prov)
        assert s.is_company is True
        assert s.company_id == "co_abc"


class TestCustomer:
    def test_id_derived_from_name(self, prov: Provenance) -> None:
        c1 = Customer(name="US Generic Distributors", provenance=prov)
        c2 = Customer(name="US Generic Distributors", provenance=prov)
        assert c1.id == c2.id
        assert c1.id.startswith("cust_")

    def test_government_customer(self, prov: Provenance) -> None:
        c = Customer(name="Government of India", category="government", is_company=False, country="India", provenance=prov)
        assert c.category == "government"
        assert c.is_company is False


class TestProduct:
    def test_id_derived_from_name(self, prov: Provenance) -> None:
        p1 = Product(name="Generic Formulations", provenance=prov)
        p2 = Product(name="Generic Formulations", provenance=prov)
        assert p1.id == p2.id
        assert p1.id.startswith("prod_")

    def test_category(self, prov: Provenance) -> None:
        p = Product(name="Portland Cement", category="commodity", provenance=prov)
        assert p.category == "commodity"


class TestValueChainEdge:
    def test_id_derived_from_endpoints_and_type(self, prov: Provenance) -> None:
        e1 = ValueChainEdge(
            from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.USES, provenance=prov,
        )
        e2 = ValueChainEdge(
            from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.USES, provenance=prov,
        )
        assert e1.id == e2.id
        assert e1.id.startswith("edge_")

    def test_id_changes_with_type(self, prov: Provenance) -> None:
        e1 = ValueChainEdge(from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.USES, provenance=prov)
        e2 = ValueChainEdge(from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.DEPENDS_ON, provenance=prov)
        assert e1.id != e2.id

    def test_default_validation_status_is_hypothesized(self, prov: Provenance) -> None:
        e = ValueChainEdge(from_id="a", to_id="b", edge_type=ValueChainEdgeType.USES, provenance=prov)
        assert e.validation_status == ValidationStatus.HYPOTHESIZED

    def test_magnitude_percent_optional(self, prov: Provenance) -> None:
        e = ValueChainEdge(
            from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.USES,
            magnitude="70% of raw material cost", magnitude_percent=70.0,
            provenance=prov,
        )
        assert e.magnitude == "70% of raw material cost"
        assert e.magnitude_percent == 70.0

    def test_evidence_field(self, prov: Provenance) -> None:
        e = ValueChainEdge(
            from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.USES,
            evidence="Annual report FY2024, page 42, raw material cost breakdown table",
            provenance=prov,
        )
        assert "page 42" in e.evidence

    def test_time_period(self, prov: Provenance) -> None:
        e = ValueChainEdge(
            from_id="sec_abc", to_id="rm_xyz", edge_type=ValueChainEdgeType.USES,
            time_period="FY2024", provenance=prov,
        )
        assert e.time_period == "FY2024"

    def test_all_edge_types_computable(self, prov: Provenance) -> None:
        """Every edge type should produce a valid ID."""
        for et in ValueChainEdgeType:
            e = ValueChainEdge(from_id="a", to_id="b", edge_type=et, provenance=prov)
            assert e.id.startswith("edge_")

    def test_direction_default_forward(self, prov: Provenance) -> None:
        e = ValueChainEdge(from_id="a", to_id="b", edge_type=ValueChainEdgeType.USES, provenance=prov)
        assert e.direction == "forward"
