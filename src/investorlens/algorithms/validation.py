"""
Empirical validation algorithms for Phase 4.4.

Three validation methods:

1. **Rolling betas**: measure how a company's stock returns correlate with
   a macro driver's changes over a rolling window. If the model predicts a
   negative exposure, the empirical beta should be negative.

2. **Event studies**: measure a company's abnormal return around identifiable
   events (e.g. RBI rate hike, crude oil spike). If the model predicts a
   negative exposure to crude oil, the company should underperform on days
   when crude oil spikes.

3. **Historical shock analysis**: compare known driver shocks (e.g. USD/INR
   +5% in a month) against company outcomes (stock return in the same period).
   If the model predicts a -0.5% margin impact per 1% USD/INR change, and
   USD/INR moved +5%, the company's stock should have underperformed.

All three methods produce a `ValidationResult` that can be compared against
the model's predicted scores from Milestone 4.3.

IMPORTANT: With the current seed data (5 overlapping dates), the results are
illustrative, not statistically significant. The framework is designed to
produce meaningful results when live data provides hundreds of trading days.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "RollingBetaResult",
    "EventStudyResult",
    "ShockAnalysisResult",
    "ValidationResult",
    "compute_rolling_beta",
    "compute_event_study",
    "compute_shock_analysis",
    "align_time_series",
]


@dataclass
class RollingBetaResult:
    """Result of a rolling beta computation.

    The beta measures the sensitivity of company returns to driver changes.
    A beta of -0.5 means: for every 1% increase in the driver, the company's
    stock decreases by 0.5%.

    Fields:
      - company_id, driver_id: the pair being validated
      - beta: the rolling beta (slope of OLS regression)
      - r_squared: how well the driver explains the company's returns (0-1)
      - p_value: statistical significance of the beta (lower = more significant)
      - n_observations: number of data points used
      - window_size: the rolling window used
      - interpretation: human-readable summary
    """

    company_id: str
    driver_id: str
    beta: float | None
    r_squared: float | None
    p_value: float | None
    n_observations: int
    window_size: int
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "driver_id": self.driver_id,
            "beta": round(self.beta, 6) if self.beta is not None else None,
            "r_squared": round(self.r_squared, 6) if self.r_squared is not None else None,
            "p_value": round(self.p_value, 6) if self.p_value is not None else None,
            "n_observations": self.n_observations,
            "window_size": self.window_size,
            "interpretation": self.interpretation,
        }


@dataclass
class EventStudyResult:
    """Result of an event study.

    Measures the company's abnormal return around an event date.
    Abnormal return = actual return - expected return (benchmarked to 0 or
    a market index).

    Fields:
      - company_id: the company being studied
      - event_date: the date of the event
      - event_description: what happened
      - window_days: number of days before/after the event
      - abnormal_return: cumulative abnormal return over the window
      - interpretation: human-readable summary
    """

    company_id: str
    event_date: str
    event_description: str
    window_days: int
    abnormal_return: float | None
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "event_date": self.event_date,
            "event_description": self.event_description,
            "window_days": self.window_days,
            "abnormal_return": round(self.abnormal_return, 6) if self.abnormal_return is not None else None,
            "interpretation": self.interpretation,
        }


@dataclass
class ShockAnalysisResult:
    """Result of a historical shock analysis.

    Compares a known driver shock against the company's stock performance
    in the same period.

    Fields:
      - company_id, driver_id: the pair being analyzed
      - shock_date: when the shock occurred
      - driver_change: the magnitude of the driver change (e.g. +0.05 for +5%)
      - company_return: the company's stock return in the same period
      - predicted_impact: the model's predicted impact (from scoring)
      - actual_vs_predicted: ratio of actual to predicted (1.0 = perfect match)
      - interpretation: human-readable summary
    """

    company_id: str
    driver_id: str
    shock_date: str
    driver_change: float
    company_return: float | None
    predicted_impact: float | None
    actual_vs_predicted: float | None
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "driver_id": self.driver_id,
            "shock_date": self.shock_date,
            "driver_change": round(self.driver_change, 6),
            "company_return": round(self.company_return, 6) if self.company_return is not None else None,
            "predicted_impact": round(self.predicted_impact, 6) if self.predicted_impact is not None else None,
            "actual_vs_predicted": round(self.actual_vs_predicted, 6) if self.actual_vs_predicted is not None else None,
            "interpretation": self.interpretation,
        }


@dataclass
class ValidationResult:
    """Aggregate validation result for a company-driver pair.

    Combines rolling beta, event study, and shock analysis into a single
    validation status.
    """

    company_id: str
    driver_id: str
    rolling_beta: RollingBetaResult | None = None
    event_studies: list[EventStudyResult] = field(default_factory=list)
    shock_analyses: list[ShockAnalysisResult] = field(default_factory=list)
    overall_status: str = "hypothesized"  # validated / weakly_supported / hypothesized
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "driver_id": self.driver_id,
            "rolling_beta": self.rolling_beta.to_dict() if self.rolling_beta else None,
            "event_studies": [e.to_dict() for e in self.event_studies],
            "shock_analyses": [s.to_dict() for s in self.shock_analyses],
            "overall_status": self.overall_status,
            "interpretation": self.interpretation,
        }


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------


def align_time_series(
    company_obs: list[dict],
    driver_obs: list[dict],
) -> list[tuple[str, float, float]]:
    """Align company and driver observations by date.

    Args:
        company_obs: list of observation dicts with 'as_of' (date string)
            and 'value' (numeric). Typically price_close observations.
        driver_obs: list of observation dicts with 'as_of' and 'value'.

    Returns:
        List of (date, company_value, driver_value) tuples, sorted by date.
        Only dates where BOTH series have observations are included.
    """
    company_by_date: dict[str, float] = {}
    for obs in company_obs:
        d = obs.get("as_of", "")
        v = obs.get("value")
        if d and v is not None:
            try:
                company_by_date[d] = float(v)
            except (TypeError, ValueError):
                pass

    driver_by_date: dict[str, float] = {}
    for obs in driver_obs:
        d = obs.get("as_of", "")
        v = obs.get("value")
        if d and v is not None:
            try:
                driver_by_date[d] = float(v)
            except (TypeError, ValueError):
                pass

    # Find overlapping dates.
    common_dates = sorted(set(company_by_date.keys()) & set(driver_by_date.keys()))

    return [(d, company_by_date[d], driver_by_date[d]) for d in common_dates]


# ---------------------------------------------------------------------------
# 1. Rolling beta
# ---------------------------------------------------------------------------


def compute_rolling_beta(
    company_obs: list[dict],
    driver_obs: list[dict],
    *,
    company_id: str = "",
    driver_id: str = "",
    window_size: int = 30,
    min_observations: int = 3,
) -> RollingBetaResult:
    """Compute the rolling beta of company returns vs driver changes.

    The beta is the slope of an OLS regression of company returns on driver
    changes. A negative beta means the company moves opposite to the driver.

    Args:
        company_obs: company price observations (e.g. price_close).
        driver_obs: driver observations (e.g. fx_rate, policy_rate).
        company_id, driver_id: IDs for the result record.
        window_size: rolling window in days (default 30).
        min_observations: minimum data points needed (default 3).

    Returns:
        A RollingBetaResult with beta, r_squared, p_value, n_observations.
    """
    aligned = align_time_series(company_obs, driver_obs)

    if len(aligned) < min_observations:
        return RollingBetaResult(
            company_id=company_id,
            driver_id=driver_id,
            beta=None,
            r_squared=None,
            p_value=None,
            n_observations=len(aligned),
            window_size=window_size,
            interpretation=f"Insufficient data: {len(aligned)} observations (need {min_observations}).",
        )

    # Compute returns/changes.
    dates = [a[0] for a in aligned]
    company_values = np.array([a[1] for a in aligned])
    driver_values = np.array([a[2] for a in aligned])

    # Returns: percentage change between consecutive observations.
    company_returns = np.diff(company_values) / company_values[:-1]
    driver_changes = np.diff(driver_values) / driver_values[:-1]

    n = len(company_returns)
    if n < min_observations:
        return RollingBetaResult(
            company_id=company_id,
            driver_id=driver_id,
            beta=None,
            r_squared=None,
            p_value=None,
            n_observations=n,
            window_size=window_size,
            interpretation=f"Insufficient return data: {n} observations (need {min_observations}).",
        )

    # OLS regression: company_returns = alpha + beta * driver_changes + epsilon
    X = np.column_stack([np.ones(n), driver_changes])
    y = company_returns

    try:
        # beta = (X'X)^(-1) X'y
        coeffs = np.linalg.lstsq(X, y, rcond=None)
        beta = coeffs[0][1]
        residuals = y - X @ coeffs[0]

        # R-squared
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # P-value (simplified: t-statistic with n-2 degrees of freedom)
        if n > 2 and ss_res > 0:
            se_beta = np.sqrt(ss_res / (n - 2) / np.sum((driver_changes - np.mean(driver_changes)) ** 2))
            t_stat = beta / se_beta if se_beta > 0 else 0.0
            # Approximate p-value using normal distribution (good for n > 30)
            from math import erfc, sqrt
            p_value = erfc(abs(t_stat) / sqrt(2))
        else:
            p_value = None

    except (np.linalg.LinAlgError, ValueError):
        return RollingBetaResult(
            company_id=company_id,
            driver_id=driver_id,
            beta=None,
            r_squared=None,
            p_value=None,
            n_observations=n,
            window_size=window_size,
            interpretation="Regression failed (singular matrix).",
        )

    # Interpretation.
    direction = "positive" if beta > 0 else "negative" if beta < 0 else "neutral"
    significance = "significant" if p_value and p_value < 0.05 else "not significant"
    interpretation = (
        f"Beta = {beta:.4f} ({direction}). "
        f"R² = {r_squared:.4f} ({r_squared*100:.1f}% of variance explained). "
        f"P-value = {p_value:.4f} ({significance}). "
        f"Based on {n} observations. "
        f"A beta of {beta:.4f} means: for every 1% increase in the driver, "
        f"the company's stock {'increases' if beta > 0 else 'decreases'} by {abs(beta):.4f}%."
    )

    return RollingBetaResult(
        company_id=company_id,
        driver_id=driver_id,
        beta=beta,
        r_squared=r_squared,
        p_value=p_value,
        n_observations=n,
        window_size=window_size,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# 2. Event study
# ---------------------------------------------------------------------------


def compute_event_study(
    company_obs: list[dict],
    event_date: str,
    *,
    company_id: str = "",
    event_description: str = "",
    window_days: int = 5,
) -> EventStudyResult:
    """Compute the abnormal return around an event date.

    The abnormal return is the company's return over the event window,
    benchmarked against zero (no market index available in seed data).

    Args:
        company_obs: company price observations (sorted by date).
        event_date: the date of the event (ISO string).
        company_id: company ID for the result.
        event_description: what happened.
        window_days: number of days before/after the event.

    Returns:
        An EventStudyResult with the cumulative abnormal return.
    """
    # Sort observations by date.
    sorted_obs = sorted(company_obs, key=lambda o: o.get("as_of", ""))
    dates = [o.get("as_of", "") for o in sorted_obs]
    values = [o.get("value") for o in sorted_obs]

    # Find the event date in the series (or closest).
    event_idx = None
    for i, d in enumerate(dates):
        if d == event_date:
            event_idx = i
            break

    if event_idx is None:
        return EventStudyResult(
            company_id=company_id,
            event_date=event_date,
            event_description=event_description,
            window_days=window_days,
            abnormal_return=None,
            interpretation=f"Event date {event_date} not found in company observations.",
        )

    # Find the start and end of the window.
    start_idx = max(0, event_idx - window_days)
    end_idx = min(len(values) - 1, event_idx + window_days)

    if start_idx == end_idx or values[start_idx] is None or values[end_idx] is None:
        return EventStudyResult(
            company_id=company_id,
            event_date=event_date,
            event_description=event_description,
            window_days=window_days,
            abnormal_return=None,
            interpretation="Insufficient data around event date.",
        )

    try:
        start_val = float(values[start_idx])
        end_val = float(values[end_idx])
        abnormal_return = (end_val - start_val) / start_val
    except (TypeError, ValueError, ZeroDivisionError):
        return EventStudyResult(
            company_id=company_id,
            event_date=event_date,
            event_description=event_description,
            window_days=window_days,
            abnormal_return=None,
            interpretation="Could not compute return (invalid values).",
        )

    direction = "positive" if abnormal_return > 0 else "negative"
    interpretation = (
        f"Abnormal return = {abnormal_return:+.4f} ({direction}). "
        f"Over a {window_days}-day window around {event_date}, "
        f"the company's stock {'gained' if abnormal_return > 0 else 'lost'} "
        f"{abs(abnormal_return)*100:.2f}%. "
        f"Event: {event_description}."
    )

    return EventStudyResult(
        company_id=company_id,
        event_date=event_date,
        event_description=event_description,
        window_days=window_days,
        abnormal_return=abnormal_return,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# 3. Historical shock analysis
# ---------------------------------------------------------------------------


def compute_shock_analysis(
    company_obs: list[dict],
    driver_obs: list[dict],
    *,
    company_id: str = "",
    driver_id: str = "",
    shock_threshold: float = 0.02,
    predicted_impact: float | None = None,
) -> list[ShockAnalysisResult]:
    """Identify historical driver shocks and compare against company returns.

    A "shock" is any period where the driver changed by more than
    `shock_threshold` (default 2%) between consecutive observations.

    Args:
        company_obs: company price observations.
        driver_obs: driver observations.
        company_id, driver_id: IDs for the result.
        shock_threshold: minimum driver change to qualify as a shock.
        predicted_impact: the model's predicted impact per 1% driver change
            (from the scoring algorithm). Used to compute actual_vs_predicted.

    Returns:
        List of ShockAnalysisResult, one per identified shock.
    """
    aligned = align_time_series(company_obs, driver_obs)

    if len(aligned) < 2:
        return []

    results: list[ShockAnalysisResult] = []

    for i in range(1, len(aligned)):
        prev_date, prev_company, prev_driver = aligned[i - 1]
        curr_date, curr_company, curr_driver = aligned[i]

        # Driver change.
        if prev_driver == 0:
            continue
        driver_change = (curr_driver - prev_driver) / prev_driver

        # Check if it's a shock.
        if abs(driver_change) < shock_threshold:
            continue

        # Company return.
        if prev_company == 0:
            continue
        company_return = (curr_company - prev_company) / prev_company

        # Actual vs predicted.
        actual_vs_predicted = None
        if predicted_impact is not None and driver_change != 0:
            predicted_total = predicted_impact * driver_change * 100  # predicted_impact is per 1%
            if abs(predicted_total) > 1e-10:
                actual_vs_predicted = company_return / predicted_total

        direction = "positive" if driver_change > 0 else "negative"
        company_dir = "gained" if company_return > 0 else "lost"

        interpretation = (
            f"Driver {direction} shock of {abs(driver_change)*100:.2f}% on {curr_date}. "
            f"Company {company_dir} {abs(company_return)*100:.2f}%. "
        )
        if actual_vs_predicted is not None:
            if abs(actual_vs_predicted) < 0.5:
                interpretation += f"Model prediction was in the right direction (ratio: {actual_vs_predicted:.2f})."
            elif actual_vs_predicted > 0:
                interpretation += f"Model prediction was in the right direction but magnitude differed (ratio: {actual_vs_predicted:.2f})."
            else:
                interpretation += f"Model prediction was in the WRONG direction (ratio: {actual_vs_predicted:.2f})."

        results.append(ShockAnalysisResult(
            company_id=company_id,
            driver_id=driver_id,
            shock_date=curr_date,
            driver_change=driver_change,
            company_return=company_return,
            predicted_impact=predicted_impact,
            actual_vs_predicted=actual_vs_predicted,
            interpretation=interpretation,
        ))

    return results
