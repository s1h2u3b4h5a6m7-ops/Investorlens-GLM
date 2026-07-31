"""
Exposure model for Phase 3.4 (Exposure Model).

An Exposure record captures HOW a company is affected by a macro driver or
raw material — not just THAT it's affected. This is the structured layer
between "Company X uses Crude Oil" (a value-chain edge) and "Company X's
gross margin drops 2% when crude oil rises 10%" (a Phase 4 quantitative impact).

Key design principle (from the roadmap):
  "Do NOT assume input↑ ⇒ negative; pass-through matters."

An input cost increase is NOT automatically negative for a company if:
  - The company has pricing power (can raise prices)
  - The company hedges the input
  - The company has inventory buffers
  - The company's product mix is diversified
  - The company operates in a geography that insulates it
  - Long-term contracts lock in prices
  - The timing of pass-through is short enough

Fields:
  - company_id: the Security ID (sec_*)
  - driver_id: the macro driver ID (drv_*) or raw material ID (rm_*)
  - driver_type: macro_driver | raw_material
  - direction: positive | negative | neutral | mixed
  - transmission_mechanism: raw_material_cost | revenue | financing_cost | demand | regulatory
  - pricing_power: high | medium | low | none
  - hedge_status: unhedged | partially_hedged | fully_hedged
  - pass_through_lag_days: how many days before cost increases are passed to customers
  - magnitude_estimate: qualitative description (e.g. "1% USD depreciation = ~0.5% margin impact")
  - financial_metric_impacted: gross_margin | ebitda_margin | revenue | net_income | operating_cost
  - notes: free-text caveats and context
  - validation_status: validated | weakly_supported | hypothesized

The Exposure ID is derived from (company_id, driver_id) so re-running
the pipeline upserts rather than duplicates.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..ids import make_id
from .provenance import Confidence, Provenance
from .valuechain import ValidationStatus

__all__ = [
    "Exposure",
    "ExposureDirection",
    "TransmissionMechanism",
    "PricingPower",
    "HedgeStatus",
    "FinancialMetric",
]


class ExposureDirection(str, Enum):
    """Direction of exposure — does the driver help or hurt the company?"""

    POSITIVE = "positive"      # driver increase → company benefits (e.g. exporter when INR depreciates)
    NEGATIVE = "negative"      # driver increase → company hurt (e.g. importer when INR depreciates)
    NEUTRAL = "neutral"        # driver change has no material impact
    MIXED = "mixed"            # driver has both positive and negative effects (e.g. USD/INR for pharma: hurts imports, helps exports)


class TransmissionMechanism(str, Enum):
    """How does the driver transmit to the company's financials?"""

    RAW_MATERIAL_COST = "raw_material_cost"       # input price → cost of goods sold
    REVENUE = "revenue"                           # demand/pricing → top line
    FINANCING_COST = "financing_cost"             # interest rates → interest expense
    DEMAND = "demand"                             # macro demand cycle → volumes
    REGULATORY = "regulatory"                     # policy/regulation → compliance cost or market access
    FX_TRANSLATION = "fx_translation"             # currency → overseas earnings translation
    OTHER = "other"


class PricingPower(str, Enum):
    """Can the company pass through cost increases to customers?"""

    HIGH = "high"             # dominant market position, brand premium, short contracts
    MEDIUM = "medium"         # some pricing power but constrained by competition
    LOW = "low"               # limited pricing power; price taker in commodity markets
    NONE = "none"             # no pricing power; fully exposed to input cost swings


class HedgeStatus(str, Enum):
    """Is the company hedged against this driver?"""

    UNHEDGED = "unhedged"               # no hedging; fully exposed
    PARTIALLY_HEDGED = "partially_hedged"  # some hedging (e.g. 3-6 months forward cover)
    FULLY_HEDGED = "fully_hedged"       # fully hedged for the relevant period


class FinancialMetric(str, Enum):
    """Which financial metric is most impacted by this exposure?"""

    GROSS_MARGIN = "gross_margin"
    EBITDA_MARGIN = "ebitda_margin"
    REVENUE = "revenue"
    NET_INCOME = "net_income"
    OPERATING_COST = "operating_cost"


class Exposure(BaseModel):
    """A structured exposure record connecting a company to a driver.

    This captures HOW the company is affected — not just THAT it's affected.
    The roadmap principle: "Do NOT assume input↑ ⇒ negative; pass-through matters."

    The ID is derived from (company_id, driver_id) so re-running the pipeline
    upserts rather than duplicates.
    """

    company_id: str = Field(..., description="Security ID (sec_*) of the exposed company")
    driver_id: str = Field(..., description="Macro driver ID (drv_*) or raw material ID (rm_*)")
    driver_type: Literal["macro_driver", "raw_material"]

    direction: ExposureDirection
    transmission_mechanism: TransmissionMechanism
    financial_metric_impacted: FinancialMetric = FinancialMetric.GROSS_MARGIN

    pricing_power: PricingPower = PricingPower.MEDIUM
    hedge_status: HedgeStatus = HedgeStatus.UNHEDGED
    pass_through_lag_days: int | None = Field(default=None, description="Days before cost increases are passed to customers (None = unknown)")

    magnitude_estimate: str | None = Field(default=None, description="Qualitative estimate, e.g. '1% USD depreciation = ~0.5% margin impact'")
    magnitude_percent: float | None = Field(default=None, description="Estimated sensitivity: 1% driver change = X% metric change")

    notes: str | None = None
    validation_status: ValidationStatus = ValidationStatus.HYPOTHESIZED

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Exposure":
        object.__setattr__(
            self,
            "id",
            make_id("exp", {"company_id": self.company_id, "driver_id": self.driver_id}),
        )
        return self

    id: str = Field(default="")
