"""Tests for the transparent scoring algorithm (investorlens.algorithms.scoring)."""

from __future__ import annotations

import pytest

from investorlens.algorithms.scoring import (
    DIRECTION_FACTORS,
    HEDGE_FACTORS,
    PRICING_POWER_FACTORS,
    VALIDATION_FACTORS,
    ScoreResult,
    score_all_exposures,
    score_exposure,
)


@pytest.fixture
def sample_exposure() -> dict:
    """Sun Pharma's USD/INR exposure: mixed, 0.3% magnitude, medium pricing, partially hedged, weakly_supported."""
    return {
        "company_id": "sec_sunpharma",
        "driver_id": "drv_fx_usd_inr",
        "direction": "negative",
        "magnitude_percent": 0.3,
        "pricing_power": "medium",
        "hedge_status": "partially_hedged",
        "validation_status": "weakly_supported",
        "financial_metric_impacted": "ebitda_margin",
        "transmission_mechanism": "raw_material_cost",
        "magnitude_estimate": "1% INR depreciation = ~0.3% margin impact",
        "notes": "Negative on KSM imports; positive on US exports.",
    }


class TestFactorTables:
    def test_direction_factors(self) -> None:
        assert DIRECTION_FACTORS["positive"] == 1.0
        assert DIRECTION_FACTORS["negative"] == -1.0
        assert DIRECTION_FACTORS["mixed"] == 0.0
        assert DIRECTION_FACTORS["neutral"] == 0.0

    def test_pricing_power_factors(self) -> None:
        assert PRICING_POWER_FACTORS["high"] == 0.3
        assert PRICING_POWER_FACTORS["medium"] == 0.6
        assert PRICING_POWER_FACTORS["low"] == 0.9
        assert PRICING_POWER_FACTORS["none"] == 1.0

    def test_hedge_factors(self) -> None:
        assert HEDGE_FACTORS["fully_hedged"] == 0.1
        assert HEDGE_FACTORS["partially_hedged"] == 0.5
        assert HEDGE_FACTORS["unhedged"] == 1.0

    def test_validation_factors(self) -> None:
        assert VALIDATION_FACTORS["validated"] == 1.0
        assert VALIDATION_FACTORS["weakly_supported"] == 0.7
        assert VALIDATION_FACTORS["hypothesized"] == 0.4

    def test_factors_decrease_with_mitigation(self) -> None:
        """Higher pricing power → lower factor (less impact)."""
        assert PRICING_POWER_FACTORS["high"] < PRICING_POWER_FACTORS["medium"]
        assert PRICING_POWER_FACTORS["medium"] < PRICING_POWER_FACTORS["low"]
        assert PRICING_POWER_FACTORS["low"] < PRICING_POWER_FACTORS["none"]
        """More hedging → lower factor."""
        assert HEDGE_FACTORS["fully_hedged"] < HEDGE_FACTORS["partially_hedged"]
        assert HEDGE_FACTORS["partially_hedged"] < HEDGE_FACTORS["unhedged"]
        """More validation → higher factor (more trusted)."""
        assert VALIDATION_FACTORS["validated"] > VALIDATION_FACTORS["weakly_supported"]
        assert VALIDATION_FACTORS["weakly_supported"] > VALIDATION_FACTORS["hypothesized"]


class TestScoreExposure:
    def test_negative_direction_produces_negative_score(self, sample_exposure: dict) -> None:
        result = score_exposure(sample_exposure, 0.10)  # +10% driver change
        assert result.score < 0  # negative direction → negative score

    def test_positive_direction_produces_positive_score(self, sample_exposure: dict) -> None:
        exp = {**sample_exposure, "direction": "positive"}
        result = score_exposure(exp, 0.10)
        assert result.score > 0

    def test_mixed_direction_produces_zero_score(self, sample_exposure: dict) -> None:
        exp = {**sample_exposure, "direction": "mixed"}
        result = score_exposure(exp, 0.10)
        assert result.score == 0.0  # mixed → net zero

    def test_score_formula_correct(self, sample_exposure: dict) -> None:
        """Verify the exact formula: driver_change × magnitude × direction × pricing × hedge × validation."""
        result = score_exposure(sample_exposure, 0.10)
        expected = 0.10 * 0.3 * (-1.0) * 0.6 * 0.5 * 0.7
        assert result.score == pytest.approx(expected, rel=1e-10)

    def test_no_magnitude_produces_zero_score(self, sample_exposure: dict) -> None:
        exp = {**sample_exposure, "magnitude_percent": None}
        result = score_exposure(exp, 0.10)
        assert result.score == 0.0

    def test_higher_pricing_power_reduces_impact(self, sample_exposure: dict) -> None:
        """A company with HIGH pricing power should have a smaller |score| than one with LOW."""
        exp_low = {**sample_exposure, "pricing_power": "low"}
        exp_high = {**sample_exposure, "pricing_power": "high"}
        result_low = score_exposure(exp_low, 0.10)
        result_high = score_exposure(exp_high, 0.10)
        assert abs(result_high.score) < abs(result_low.score)

    def test_more_hedging_reduces_impact(self, sample_exposure: dict) -> None:
        exp_unhedged = {**sample_exposure, "hedge_status": "unhedged"}
        exp_hedged = {**sample_exposure, "hedge_status": "fully_hedged"}
        result_unhedged = score_exposure(exp_unhedged, 0.10)
        result_hedged = score_exposure(exp_hedged, 0.10)
        assert abs(result_hedged.score) < abs(result_unhedged.score)

    def test_more_validation_increases_score(self, sample_exposure: dict) -> None:
        exp_hyp = {**sample_exposure, "validation_status": "hypothesized"}
        exp_val = {**sample_exposure, "validation_status": "validated"}
        result_hyp = score_exposure(exp_hyp, 0.10)
        result_val = score_exposure(exp_val, 0.10)
        assert abs(result_val.score) > abs(result_hyp.score)

    def test_decomposition_contains_all_factors(self, sample_exposure: dict) -> None:
        result = score_exposure(sample_exposure, 0.10, driver_label="USD/INR", company_label="Sun Pharma")
        d = result.decomposition()
        assert "USD/INR" in d
        assert "Sun Pharma" in d
        assert "Driver change:" in d
        assert "Magnitude:" in d
        assert "Direction factor:" in d
        assert "Pricing power factor:" in d
        assert "Hedge factor:" in d
        assert "Validation factor:" in d
        assert "Score:" in d
        assert "Interpretation:" in d

    def test_decomposition_interpretation_positive(self, sample_exposure: dict) -> None:
        exp = {**sample_exposure, "direction": "positive"}
        result = score_exposure(exp, 0.10)
        d = result.decomposition()
        assert "increases" in d

    def test_decomposition_interpretation_negative(self, sample_exposure: dict) -> None:
        result = score_exposure(sample_exposure, 0.10)
        d = result.decomposition()
        assert "decreases" in d

    def test_decomposition_interpretation_negligible(self, sample_exposure: dict) -> None:
        """A mixed direction should produce a negligible (zero) score."""
        exp = {**sample_exposure, "direction": "mixed"}
        result = score_exposure(exp, 0.10)
        d = result.decomposition()
        assert "negligible" in d

    def test_to_dict_serialization(self, sample_exposure: dict) -> None:
        result = score_exposure(sample_exposure, 0.10, driver_label="USD/INR", company_label="Sun Pharma")
        d = result.to_dict()
        assert d["driver_label"] == "USD/INR"
        assert d["company_label"] == "Sun Pharma"
        assert d["driver_change"] == 0.10
        assert "score" in d
        assert "decomposition" in d
        assert d["decomposition"] is not None

    def test_driver_change_scales_score_linearly(self, sample_exposure: dict) -> None:
        """Doubling the driver change should double the score (linearity assumption)."""
        r1 = score_exposure(sample_exposure, 0.10)
        r2 = score_exposure(sample_exposure, 0.20)
        assert r2.score == pytest.approx(r1.score * 2, rel=1e-10)


class TestScoreAllExposures:
    def test_scores_all_exposures(self) -> None:
        exposures = [
            {"company_id": "a", "driver_id": "x", "direction": "negative", "magnitude_percent": 0.5,
             "pricing_power": "low", "hedge_status": "unhedged", "validation_status": "hypothesized"},
            {"company_id": "b", "driver_id": "y", "direction": "positive", "magnitude_percent": 0.3,
             "pricing_power": "high", "hedge_status": "partially_hedged", "validation_status": "validated"},
        ]
        results = score_all_exposures(exposures, 0.10)
        assert len(results) == 2

    def test_sorted_by_absolute_score_descending(self) -> None:
        exposures = [
            {"company_id": "a", "driver_id": "x", "direction": "negative", "magnitude_percent": 0.1,
             "pricing_power": "high", "hedge_status": "fully_hedged", "validation_status": "hypothesized"},
            {"company_id": "b", "driver_id": "y", "direction": "negative", "magnitude_percent": 0.5,
             "pricing_power": "low", "hedge_status": "unhedged", "validation_status": "validated"},
        ]
        results = score_all_exposures(exposures, 0.10)
        assert abs(results[0].score) >= abs(results[1].score)

    def test_uses_labels(self) -> None:
        exposures = [
            {"company_id": "sec_a", "driver_id": "drv_x", "direction": "negative", "magnitude_percent": 0.5,
             "pricing_power": "low", "hedge_status": "unhedged", "validation_status": "hypothesized"},
        ]
        results = score_all_exposures(
            exposures, 0.10,
            driver_labels={"drv_x": "USD/INR"},
            company_labels={"sec_a": "Sun Pharma"},
        )
        assert results[0].driver_label == "USD/INR"
        assert results[0].company_label == "Sun Pharma"

    def test_empty_exposures_returns_empty(self) -> None:
        results = score_all_exposures([], 0.10)
        assert results == []
