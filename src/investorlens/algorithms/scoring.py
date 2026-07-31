"""
Transparent Driver → Company Scoring.

Takes Exposure records and produces decomposable impact scores. Every score
can be traced through the full chain:

  Driver change × Magnitude × Direction × Pricing power × Hedge × Validation = Score

Every factor is explicit. No black-box. A user asking "why did Company X get
a +0.15 impact score from Driver Y?" gets the full answer:

  "Driver Y +10% × magnitude 0.3% per 1% × direction -1 (negative) ×
   pricing_power 0.6 (medium) × hedge 0.5 (partially_hedged) ×
   validation 0.7 (weakly_supported) = -0.0063"

────────────────────────────────────────────────────────────────────────
SCORING FORMULA (documented per Operating Principle 11)
────────────────────────────────────────────────────────────────────────

Score = driver_change × magnitude_percent × direction_factor
        × pricing_power_factor × hedge_factor × validation_factor

Where:
  driver_change:       the hypothetical driver change (e.g. +0.10 for +10%)
  magnitude_percent:   from the Exposure record (e.g. 0.3 = 0.3% per 1% change)
  direction_factor:    positive = +1.0, negative = -1.0, mixed = 0.0 (net zero),
                       neutral = 0.0
  pricing_power_factor: high = 0.3 (70% of impact absorbed by pricing),
                        medium = 0.6 (40% absorbed), low = 0.9 (10% absorbed),
                        none = 1.0 (no absorption)
  hedge_factor:        fully_hedged = 0.1 (90% hedged), partially_hedged = 0.5,
                       unhedged = 1.0
  validation_factor:   validated = 1.0, weakly_supported = 0.7,
                       hypothesized = 0.4

The final score represents the estimated impact on the company's financial
metric from the given driver change. A score of -0.05 means the metric
(e.g. gross margin) is expected to decrease by 5 percentage points.

IMPORTANT: This is a STRUCTURED ESTIMATE, not a prediction. The factors are
heuristics, not empirically calibrated parameters. Phase 4.4 (empirical
validation) will test whether these factors match historical data and
recalibrate them if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ScoreResult",
    "score_exposure",
    "score_all_exposures",
    "DIRECTION_FACTORS",
    "PRICING_POWER_FACTORS",
    "HEDGE_FACTORS",
    "VALIDATION_FACTORS",
]


# ───────────────────────────────────────────────────────────────────────
# Factor lookup tables — these are the ONLY tuning parameters.
# Changing them changes every score. Document changes here.
# ───────────────────────────────────────────────────────────────────────

DIRECTION_FACTORS: dict[str, float] = {
    "positive": 1.0,     # driver increase → company benefits
    "negative": -1.0,    # driver increase → company hurt
    "mixed": 0.0,        # net effect is zero (positive and negative cancel)
    "neutral": 0.0,      # no material impact
}

PRICING_POWER_FACTORS: dict[str, float] = {
    "high": 0.3,         # 70% of cost increase absorbed by pricing power
    "medium": 0.6,       # 40% absorbed
    "low": 0.9,          # 10% absorbed
    "none": 1.0,         # no pricing power; fully exposed
}

HEDGE_FACTORS: dict[str, float] = {
    "fully_hedged": 0.1,      # 90% hedged; only 10% of impact flows through
    "partially_hedged": 0.5,  # 50% hedged
    "unhedged": 1.0,           # no hedge; fully exposed
}

VALIDATION_FACTORS: dict[str, float] = {
    "validated": 1.0,           # fully trusted
    "weakly_supported": 0.7,    # 70% confidence
    "hypothesized": 0.4,        # 40% confidence; heavily discounted
}


@dataclass
class ScoreResult:
    """The result of scoring a single driver-company exposure.

    Every field is explicit — no hidden computation. The decomposition
    string shows every factor and how they combine.
    """

    driver_id: str
    driver_label: str
    company_id: str
    company_label: str
    driver_change: float
    score: float

    # Individual factors (all explicit, all decomposable).
    magnitude_percent: float | None
    direction_factor: float
    pricing_power_factor: float
    hedge_factor: float
    validation_factor: float

    # Metadata.
    direction: str
    pricing_power: str
    hedge_status: str
    validation_status: str
    financial_metric: str
    transmission_mechanism: str
    magnitude_estimate: str | None
    notes: str | None

    def decomposition(self) -> str:
        """Human-readable decomposition of the score.

        Example:
          "USD/INR → Sun Pharma: +10% driver × 0.3% magnitude × -1.0 direction
           (negative) × 0.6 pricing_power (medium) × 0.5 hedge (partially_hedged)
           × 0.7 validation (weakly_supported) = -0.0063
           Impact: gross_margin decreases by ~0.63 percentage points."
        """
        parts = [
            f"{self.driver_label} → {self.company_label}:",
            f"  Driver change: {'+' if self.driver_change >= 0 else ''}{self.driver_change*100:.1f}%",
        ]

        if self.magnitude_percent is not None:
            parts.append(f"  Magnitude: {self.magnitude_percent}% per 1% driver change")
        else:
            parts.append("  Magnitude: — (not quantified)")

        parts.append(f"  Direction factor: {self.direction_factor:.1f} ({self.direction})")
        parts.append(f"  Pricing power factor: {self.pricing_power_factor:.1f} ({self.pricing_power})")
        parts.append(f"  Hedge factor: {self.hedge_factor:.1f} ({self.hedge_status})")
        parts.append(f"  Validation factor: {self.validation_factor:.1f} ({self.validation_status})")

        parts.append(f"  Score: {self.score:+.6f}")
        parts.append(f"  Financial metric: {self.financial_metric}")
        parts.append(f"  Transmission: {self.transmission_mechanism}")

        if self.magnitude_estimate:
            parts.append(f"  Magnitude estimate: {self.magnitude_estimate}")
        if self.notes:
            parts.append(f"  Notes: {self.notes}")

        # Interpretation.
        if abs(self.score) < 0.001:
            parts.append("  Interpretation: negligible impact")
        elif self.score > 0:
            parts.append(f"  Interpretation: {self.financial_metric} increases by ~{abs(self.score)*100:.2f} percentage points")
        else:
            parts.append(f"  Interpretation: {self.financial_metric} decreases by ~{abs(self.score)*100:.2f} percentage points")

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "driver_id": self.driver_id,
            "driver_label": self.driver_label,
            "company_id": self.company_id,
            "company_label": self.company_label,
            "driver_change": self.driver_change,
            "score": round(self.score, 6),
            "magnitude_percent": self.magnitude_percent,
            "direction_factor": self.direction_factor,
            "pricing_power_factor": self.pricing_power_factor,
            "hedge_factor": self.hedge_factor,
            "validation_factor": self.validation_factor,
            "direction": self.direction,
            "pricing_power": self.pricing_power,
            "hedge_status": self.hedge_status,
            "validation_status": self.validation_status,
            "financial_metric": self.financial_metric,
            "transmission_mechanism": self.transmission_mechanism,
            "magnitude_estimate": self.magnitude_estimate,
            "notes": self.notes,
            "decomposition": self.decomposition(),
        }


def score_exposure(
    exposure: dict,
    driver_change: float,
    *,
    driver_label: str | None = None,
    company_label: str | None = None,
) -> ScoreResult:
    """Score a single exposure for a given driver change.

    Args:
        exposure: an Exposure record dict with direction, magnitude_percent,
            pricing_power, hedge_status, validation_status, etc.
        driver_change: the hypothetical driver change (e.g. 0.10 for +10%).
        driver_label: optional human-readable driver name.
        company_label: optional human-readable company name.

    Returns:
        A ScoreResult with every factor explicit and a decomposition string.
    """
    driver_id = exposure.get("driver_id", "")
    company_id = exposure.get("company_id", "")

    magnitude_percent = exposure.get("magnitude_percent")
    direction = exposure.get("direction", "neutral")
    pricing_power = exposure.get("pricing_power", "none")
    hedge_status = exposure.get("hedge_status", "unhedged")
    validation_status = exposure.get("validation_status", "hypothesized")

    # Look up factors.
    direction_factor = DIRECTION_FACTORS.get(direction, 0.0)
    pricing_power_factor = PRICING_POWER_FACTORS.get(pricing_power, 1.0)
    hedge_factor = HEDGE_FACTORS.get(hedge_status, 1.0)
    validation_factor = VALIDATION_FACTORS.get(validation_status, 0.4)

    # Compute score.
    if magnitude_percent is not None:
        score = (
            driver_change
            * magnitude_percent
            * direction_factor
            * pricing_power_factor
            * hedge_factor
            * validation_factor
        )
    else:
        # No quantified magnitude → score is 0 (can't compute without magnitude).
        score = 0.0

    return ScoreResult(
        driver_id=driver_id,
        driver_label=driver_label or driver_id,
        company_id=company_id,
        company_label=company_label or company_id,
        driver_change=driver_change,
        score=score,
        magnitude_percent=magnitude_percent,
        direction_factor=direction_factor,
        pricing_power_factor=pricing_power_factor,
        hedge_factor=hedge_factor,
        validation_factor=validation_factor,
        direction=direction,
        pricing_power=pricing_power,
        hedge_status=hedge_status,
        validation_status=validation_status,
        financial_metric=exposure.get("financial_metric_impacted", "gross_margin"),
        transmission_mechanism=exposure.get("transmission_mechanism", "raw_material_cost"),
        magnitude_estimate=exposure.get("magnitude_estimate"),
        notes=exposure.get("notes"),
    )


def score_all_exposures(
    exposures: list[dict],
    driver_change: float,
    *,
    driver_labels: dict[str, str] | None = None,
    company_labels: dict[str, str] | None = None,
) -> list[ScoreResult]:
    """Score all exposures for a given driver change.

    Args:
        exposures: list of Exposure record dicts.
        driver_change: the hypothetical driver change (applied to all exposures).
        driver_labels: optional dict mapping driver_id → label.
        company_labels: optional dict mapping company_id → label.

    Returns:
        List of ScoreResult objects, sorted by absolute score descending.
    """
    d_labels = driver_labels or {}
    c_labels = company_labels or {}

    results = [
        score_exposure(
            exp,
            driver_change,
            driver_label=d_labels.get(exp.get("driver_id", ""), exp.get("driver_id", "")),
            company_label=c_labels.get(exp.get("company_id", ""), exp.get("company_id", "")),
        )
        for exp in exposures
    ]

    # Sort by absolute score descending (most impactful first).
    results.sort(key=lambda r: abs(r.score), reverse=True)
    return results
