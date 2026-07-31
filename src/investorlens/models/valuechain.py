"""
Value-chain domain models for Phase 3.

These entities represent the real-world components of a company's value chain:
  - RawMaterial   — inputs (crude oil, limestone, APIs, steel, etc.)
  - Supplier      — who supplies the raw material (can be a category, not always a named company)
  - Customer      — who buys the product (can be a category)
  - Product       — what the company produces (generic formulations, Portland cement, etc.)
  - ValueChainEdge — the relationship between any two entities
                     (supplies, customer_of, competes_with, depends_on, uses, produces,
                      benefits_from, hurt_by, exposed_to)

Every entity carries full Provenance. Every edge carries:
  - source (Provenance)
  - evidence (free text — what document/page supports this)
  - confidence (high/medium/low/estimated/hypothesized)
  - direction (forward/backward/bidirectional)
  - magnitude (optional — e.g. "70% of raw material cost")
  - time_period (when this relationship was true)
  - validation_status (validated/hypothesized/weakly_supported)

Design principle: never present a hypothesis as an established fact. Every
edge starts as HYPOTHESIZED until validated with empirical evidence (Phase 4).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..ids import make_id
from .provenance import Confidence, Provenance

__all__ = [
    "RawMaterial",
    "Supplier",
    "Customer",
    "Product",
    "ValueChainEdgeType",
    "ValidationStatus",
    "ValueChainEdge",
]


# ---------------------------------------------------------------------------
# Validation status (Phase 3+4)
# ---------------------------------------------------------------------------


class ValidationStatus(str, Enum):
    """Every value-chain edge must eventually have an explicit validation status."""

    VALIDATED = "validated"            # supported by empirical evidence (Phase 4)
    WEAKLY_SUPPORTED = "weakly_supported"  # some evidence but validation incomplete
    HYPOTHESIZED = "hypothesized"      # economically plausible but not validated


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------


class ValueChainEdgeType(str, Enum):
    """Types of relationships in the value-chain graph."""

    SUPPLIES = "supplies"              # supplier → company or supplier → raw_material
    CUSTOMER_OF = "customer_of"        # company → customer (company sells to customer)
    COMPETES_WITH = "competes_with"    # company → company
    DEPENDS_ON = "depends_on"          # company → raw_material / macro_driver
    USES = "uses"                      # company → raw_material (same as depends_on, more specific)
    PRODUCES = "produces"              # company → product
    BENEFITS_FROM = "benefits_from"    # company → macro_driver (positive exposure)
    HURT_BY = "hurt_by"                # company → macro_driver (negative exposure)
    EXPOSED_TO = "exposed_to"          # company → macro_driver (direction TBD)


# ---------------------------------------------------------------------------
# RawMaterial
# ---------------------------------------------------------------------------


class RawMaterial(BaseModel):
    """A raw material or input used in production.

    Examples: "Crude oil", "Active Pharmaceutical Ingredient (API)",
    "Limestone", "Natural rubber", "Titanium dioxide".
    """

    name: str = Field(..., min_length=1)
    category: str | None = Field(default=None, description="e.g. 'energy', 'chemical', 'mineral', 'agricultural'")
    unit: str | None = Field(default=None, description="e.g. 'barrel', 'tonne', 'kg'")
    description: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "RawMaterial":
        object.__setattr__(self, "id", make_id("rm", {"name": self.name.lower().strip()}))
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class Supplier(BaseModel):
    """A supplier of raw materials or services to a company.

    Can be a named company or a category (e.g. "China-based KSM suppliers").
    """

    name: str = Field(..., min_length=1)
    category: str | None = Field(default=None, description="e.g. 'domestic', 'international', 'captive'")
    is_company: bool = Field(default=False, description="True if this is a named company (has an ISIN); False if a category")
    company_id: str | None = Field(default=None, description="If is_company=True, the Company ID")
    country: str | None = None
    description: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Supplier":
        object.__setattr__(self, "id", make_id("sup", {"name": self.name.lower().strip()}))
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------


class Customer(BaseModel):
    """A customer of a company.

    Can be a named company, a government entity, or a category
    (e.g. "US generic pharma distributors").
    """

    name: str = Field(..., min_length=1)
    category: str | None = Field(default=None, description="e.g. 'domestic', 'export', 'B2B', 'B2C', 'government'")
    is_company: bool = Field(default=False)
    company_id: str | None = Field(default=None, description="If is_company=True, the Company ID")
    country: str | None = None
    description: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Customer":
        object.__setattr__(self, "id", make_id("cust", {"name": self.name.lower().strip()}))
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


class Product(BaseModel):
    """A product produced by a company.

    Examples: "Generic formulations", "Portland cement", "Passenger car tyres",
    "Decorative paints".
    """

    name: str = Field(..., min_length=1)
    category: str | None = Field(default=None, description="e.g. 'commodity', 'specialty', 'branded', 'generic'")
    description: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Product":
        object.__setattr__(self, "id", make_id("prod", {"name": self.name.lower().strip()}))
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# ValueChainEdge — the relationship entity
# ---------------------------------------------------------------------------


class ValueChainEdge(BaseModel):
    """A directed relationship between two entities in the value-chain graph.

    Every edge carries:
      - source entity ID (from_id)
      - target entity ID (to_id)
      - edge type (supplies, customer_of, depends_on, etc.)
      - evidence (free text: what document supports this?)
      - confidence (high/medium/low/estimated/hypothesized)
      - magnitude (optional: e.g. "70% of raw material cost")
      - time_period (when this relationship was true)
      - validation_status (validated/hypothesized/weakly_supported)

    The ID is derived from (from_id, to_id, edge_type) so re-running the
    research pipeline upserts rather than duplicates.
    """

    from_id: str = Field(..., description="ID of the source entity (company, supplier, etc.)")
    to_id: str = Field(..., description="ID of the target entity (raw_material, product, etc.)")
    edge_type: ValueChainEdgeType
    direction: Literal["forward", "backward", "bidirectional"] = "forward"

    magnitude: str | None = Field(default=None, description="e.g. '70% of raw material cost', 'top 3 customer'")
    magnitude_percent: float | None = Field(default=None, description="Numeric magnitude as % (0-100), if applicable")
    time_period: str | None = Field(default=None, description="e.g. 'FY2024', '2020-2024', 'current'")
    evidence: str | None = Field(default=None, description="Free text: what document/page supports this?")
    validation_status: ValidationStatus = ValidationStatus.HYPOTHESIZED

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "ValueChainEdge":
        object.__setattr__(
            self,
            "id",
            make_id(
                "edge",
                {
                    "from_id": self.from_id,
                    "to_id": self.to_id,
                    "edge_type": self.edge_type.value,
                },
            ),
        )
        return self

    id: str = Field(default="")
