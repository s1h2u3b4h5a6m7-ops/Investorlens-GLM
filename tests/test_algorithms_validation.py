"""Tests for the empirical validation algorithms (investorlens.algorithms.validation)."""

from __future__ import annotations

import pytest

from investorlens.algorithms.validation import (
    EventStudyResult,
    RollingBetaResult,
    ShockAnalysisResult,
    align_time_series,
    compute_event_study,
    compute_rolling_beta,
    compute_shock_analysis,
)


# ---------------------------------------------------------------------------
# align_time_series
# ---------------------------------------------------------------------------


class TestAlignTimeSeries:
    def test_aligns_by_date(self) -> None:
        company = [
            {"as_of": "2024-01-01", "value": 100},
            {"as_of": "2024-01-02", "value": 101},
            {"as_of": "2024-01-03", "value": 102},
        ]
        driver = [
            {"as_of": "2024-01-01", "value": 80},
            {"as_of": "2024-01-03", "value": 82},
        ]
        aligned = align_time_series(company, driver)
        assert len(aligned) == 2  # only 2024-01-01 and 2024-01-03 overlap
        assert aligned[0] == ("2024-01-01", 100.0, 80.0)
        assert aligned[1] == ("2024-01-03", 102.0, 82.0)

    def test_empty_inputs(self) -> None:
        assert align_time_series([], []) == []

    def test_no_overlap(self) -> None:
        company = [{"as_of": "2024-01-01", "value": 100}]
        driver = [{"as_of": "2024-01-02", "value": 80}]
        assert align_time_series(company, driver) == []

    def test_skips_none_values(self) -> None:
        company = [{"as_of": "2024-01-01", "value": None}]
        driver = [{"as_of": "2024-01-01", "value": 80}]
        assert align_time_series(company, driver) == []


# ---------------------------------------------------------------------------
# compute_rolling_beta
# ---------------------------------------------------------------------------


class TestComputeRollingBeta:
    def test_insufficient_data_returns_none(self) -> None:
        result = compute_rolling_beta(
            [{"as_of": "2024-01-01", "value": 100}],
            [{"as_of": "2024-01-01", "value": 80}],
            company_id="co", driver_id="drv",
            min_observations=5,
        )
        assert result.beta is None
        assert "Insufficient" in result.interpretation

    def test_perfect_positive_correlation(self) -> None:
        """If company and driver both increase but at varying rates, beta should be positive."""
        # Use varying growth rates so there's variance in the returns
        rates = [0.01, 0.02, 0.015, 0.025, 0.01, 0.03, 0.02, 0.015, 0.02, 0.025]
        company_val = 100
        driver_val = 80
        company = []
        driver = []
        for i, r in enumerate(rates, 1):
            company_val *= (1 + r)
            driver_val *= (1 + r * 0.8)  # driver moves in same direction but different magnitude
            company.append({"as_of": f"2024-01-{i:02d}", "value": company_val})
            driver.append({"as_of": f"2024-01-{i:02d}", "value": driver_val})
        result = compute_rolling_beta(company, driver, company_id="co", driver_id="drv", min_observations=3)
        assert result.beta is not None
        assert result.beta > 0  # positive correlation

    def test_perfect_negative_correlation(self) -> None:
        """If company decreases when driver increases, beta should be negative."""
        company = [{"as_of": f"2024-01-{i:02d}", "value": 100 * (0.99 ** i)} for i in range(1, 11)]
        driver = [{"as_of": f"2024-01-{i:02d}", "value": 80 * (1.01 ** i)} for i in range(1, 11)]
        result = compute_rolling_beta(company, driver, company_id="co", driver_id="drv", min_observations=3)
        assert result.beta is not None
        assert result.beta < 0  # negative

    def test_r_squared_between_0_and_1(self) -> None:
        company = [{"as_of": f"2024-01-{i:02d}", "value": 100 + i + (i % 3)} for i in range(1, 11)]
        driver = [{"as_of": f"2024-01-{i:02d}", "value": 80 + i} for i in range(1, 11)]
        result = compute_rolling_beta(company, driver, company_id="co", driver_id="drv", min_observations=3)
        if result.r_squared is not None:
            assert 0 <= result.r_squared <= 1

    def test_interpretation_contains_key_info(self) -> None:
        company = [{"as_of": f"2024-01-{i:02d}", "value": 100 * (1.01 ** i)} for i in range(1, 11)]
        driver = [{"as_of": f"2024-01-{i:02d}", "value": 80 * (1.01 ** i)} for i in range(1, 11)]
        result = compute_rolling_beta(company, driver, company_id="co", driver_id="drv", min_observations=3)
        assert "Beta" in result.interpretation
        assert "R²" in result.interpretation or "R²" in result.interpretation
        assert "P-value" in result.interpretation

    def test_to_dict(self) -> None:
        company = [{"as_of": f"2024-01-{i:02d}", "value": 100 + i} for i in range(1, 11)]
        driver = [{"as_of": f"2024-01-{i:02d}", "value": 80 + i} for i in range(1, 11)]
        result = compute_rolling_beta(company, driver, company_id="co", driver_id="drv", min_observations=3)
        d = result.to_dict()
        assert "beta" in d
        assert "r_squared" in d
        assert "n_observations" in d
        assert "interpretation" in d


# ---------------------------------------------------------------------------
# compute_event_study
# ---------------------------------------------------------------------------


class TestComputeEventStudy:
    def test_event_date_not_found(self) -> None:
        obs = [{"as_of": "2024-01-01", "value": 100}]
        result = compute_event_study(obs, "2024-06-01", company_id="co")
        assert result.abnormal_return is None
        assert "not found" in result.interpretation

    def test_computes_return(self) -> None:
        obs = [
            {"as_of": "2024-01-01", "value": 100},
            {"as_of": "2024-01-02", "value": 105},
            {"as_of": "2024-01-03", "value": 110},
        ]
        result = compute_event_study(obs, "2024-01-02", company_id="co", window_days=1)
        assert result.abnormal_return is not None
        # Return from day 1 (100) to day 3 (110) = 10%
        assert result.abnormal_return == pytest.approx(0.10, rel=1e-4)

    def test_interpretation_contains_direction(self) -> None:
        obs = [
            {"as_of": "2024-01-01", "value": 100},
            {"as_of": "2024-01-02", "value": 95},
        ]
        result = compute_event_study(obs, "2024-01-01", company_id="co", window_days=1)
        assert "negative" in result.interpretation or "lost" in result.interpretation

    def test_to_dict(self) -> None:
        obs = [{"as_of": "2024-01-01", "value": 100}, {"as_of": "2024-01-02", "value": 105}]
        result = compute_event_study(obs, "2024-01-01", company_id="co", window_days=1)
        d = result.to_dict()
        assert "abnormal_return" in d
        assert "event_date" in d


# ---------------------------------------------------------------------------
# compute_shock_analysis
# ---------------------------------------------------------------------------


class TestComputeShockAnalysis:
    def test_no_shocks_returns_empty(self) -> None:
        """If no driver change exceeds the threshold, return empty list."""
        company = [{"as_of": f"2024-01-{i:02d}", "value": 100 + i * 0.01} for i in range(1, 6)]
        driver = [{"as_of": f"2024-01-{i:02d}", "value": 80 + i * 0.01} for i in range(1, 6)]
        results = compute_shock_analysis(company, driver, shock_threshold=0.5)  # 50% threshold
        assert results == []

    def test_identifies_shock(self) -> None:
        """A large driver change should be identified as a shock."""
        company = [
            {"as_of": "2024-01-01", "value": 100},
            {"as_of": "2024-01-02", "value": 95},  # -5%
        ]
        driver = [
            {"as_of": "2024-01-01", "value": 80},
            {"as_of": "2024-01-02", "value": 84},  # +5%
        ]
        results = compute_shock_analysis(company, driver, shock_threshold=0.02, company_id="co", driver_id="drv")
        assert len(results) == 1
        assert results[0].driver_change > 0  # positive shock
        assert results[0].company_return < 0  # company lost value

    def test_predicted_impact_comparison(self) -> None:
        """When predicted_impact is given, actual_vs_predicted should be computed."""
        company = [
            {"as_of": "2024-01-01", "value": 100},
            {"as_of": "2024-01-02", "value": 98},  # -2%
        ]
        driver = [
            {"as_of": "2024-01-01", "value": 80},
            {"as_of": "2024-01-02", "value": 84},  # +5%
        ]
        results = compute_shock_analysis(
            company, driver, shock_threshold=0.02,
            company_id="co", driver_id="drv",
            predicted_impact=-0.004,  # model predicts -0.4% per 1% driver change
        )
        assert len(results) == 1
        assert results[0].actual_vs_predicted is not None

    def test_interpretation_contains_shock_info(self) -> None:
        company = [
            {"as_of": "2024-01-01", "value": 100},
            {"as_of": "2024-01-02", "value": 95},
        ]
        driver = [
            {"as_of": "2024-01-01", "value": 80},
            {"as_of": "2024-01-02", "value": 84},
        ]
        results = compute_shock_analysis(company, driver, shock_threshold=0.02, company_id="co", driver_id="drv")
        assert "shock" in results[0].interpretation.lower()
        assert "2024-01-02" in results[0].interpretation

    def test_to_dict(self) -> None:
        company = [{"as_of": "2024-01-01", "value": 100}, {"as_of": "2024-01-02", "value": 95}]
        driver = [{"as_of": "2024-01-01", "value": 80}, {"as_of": "2024-01-02", "value": 84}]
        results = compute_shock_analysis(company, driver, shock_threshold=0.02, company_id="co", driver_id="drv")
        d = results[0].to_dict()
        assert "driver_change" in d
        assert "company_return" in d
        assert "shock_date" in d
