"""
Relationship Status Upgrader — assigns VALIDATED/HYPOTHESIZED/WEAKLY_SUPPORTED
status to every relationship based on empirical evidence.

This is the final algorithm in Phase 4. It takes the empirical validation
results from Milestone 4.4 (rolling betas, shock analyses) and uses them
to upgrade relationship statuses:

  HYPOTHESIZED → WEAKLY_SUPPORTED:
    - When 1+ evidence records exist (from Phase 3.2 evidence upgrader)
    - OR when a rolling beta has been computed (even if not significant)

  WEAKLY_SUPPORTED → VALIDATED:
    - When a rolling beta is computed AND statistically significant (p < 0.05)
      AND the beta direction matches the model's predicted direction
    - OR when 2+ shock analyses show the model predicted the correct direction
    - OR when 2+ evidence records from independent sources exist

  Never downgrade:
    - VALIDATED relationships are never downgraded, even if new evidence
      is weak or contradictory (the existing validation stands)

Core principle: "Never present a hypothesis as an established fact."
Every relationship must have an explicit status. If no evidence exists,
the status remains HYPOTHESIZED. Only empirical evidence can upgrade
to VALIDATED.

Pure function: takes relationships + validation results, returns upgraded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "upgrade_relationship_statuses",
    "determine_validation_status",
    "StatusUpgradeStats",
]


@dataclass
class StatusUpgradeStats:
    """Statistics from a status upgrade run."""

    total: int = 0
    upgraded_to_weakly_supported: int = 0
    upgraded_to_validated: int = 0
    unchanged: int = 0
    final_counts: dict[str, int] = None

    def __post_init__(self):
        if self.final_counts is None:
            self.final_counts = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "upgraded_to_weakly_supported": self.upgraded_to_weakly_supported,
            "upgraded_to_validated": self.upgraded_to_validated,
            "unchanged": self.unchanged,
            "final_counts": self.final_counts,
        }


def determine_validation_status(
    current_status: str,
    *,
    has_evidence: bool = False,
    evidence_count: int = 0,
    independent_sources: int = 0,
    has_beta: bool = False,
    beta_significant: bool = False,
    beta_direction_matches: bool = False,
    shock_count: int = 0,
    shocks_correct_direction: int = 0,
) -> str:
    """Determine the validation status for a single relationship.

    Upgrade rules (only upgrades, never downgrades):

    HYPOTHESIZED → WEAKLY_SUPPORTED:
      - has_evidence (1+ evidence records)
      - OR has_beta (beta was computable, even if not significant)

    WEAKLY_SUPPORTED → VALIDATED:
      - beta_significant AND beta_direction_matches (p < 0.05 and correct sign)
      - OR shocks_correct_direction >= 2 (2+ shocks predicted correctly)
      - OR independent_sources >= 2 (2+ evidence from different organisations)

    VALIDATED is never downgraded.

    Args:
        current_status: current validation status string.
        has_evidence: whether any evidence records exist.
        evidence_count: number of evidence records.
        independent_sources: number of distinct source organisations.
        has_beta: whether a rolling beta was computable.
        beta_significant: whether the beta p-value < 0.05.
        beta_direction_matches: whether the beta sign matches the predicted direction.
        shock_count: number of identified shocks.
        shocks_correct_direction: number of shocks where the model predicted correctly.

    Returns:
        The new validation status string.
    """
    VALIDATED = "validated"
    WEAKLY_SUPPORTED = "weakly_supported"
    HYPOTHESIZED = "hypothesized"

    # Never downgrade VALIDATED.
    if current_status == VALIDATED:
        return VALIDATED

    # Check for VALIDATED upgrade criteria.
    should_validate = (
        (has_beta and beta_significant and beta_direction_matches)
        or (shocks_correct_direction >= 2)
        or (independent_sources >= 2)
    )

    if should_validate:
        return VALIDATED

    # Never downgrade WEAKLY_SUPPORTED either — once we have some evidence,
    # we keep it even if new validation data is thin.
    if current_status == WEAKLY_SUPPORTED:
        return WEAKLY_SUPPORTED

    # Check for WEAKLY_SUPPORTED upgrade criteria from HYPOTHESIZED.
    should_weaken = has_evidence or has_beta or evidence_count > 0

    if should_weaken:
        return WEAKLY_SUPPORTED

    # No evidence → stay at HYPOTHESIZED.
    return HYPOTHESIZED


def upgrade_relationship_statuses(
    relationships: list[dict],
    validation_results: list[dict] | None = None,
    evidence_by_edge: dict[str, list[dict]] | None = None,
) -> tuple[list[dict], StatusUpgradeStats]:
    """Upgrade validation statuses for a list of relationships.

    Args:
        relationships: list of relationship dicts (value-chain edges or exposures)
            with 'id', 'validation_status', and optionally 'from_id'/'to_id' or
            'company_id'/'driver_id'.
        validation_results: list of validation result dicts from run_validation.py,
            each with 'company_id', 'driver_id', 'rolling_beta' (dict with 'beta',
            'p_value', 'n_observations'), and 'shock_analyses' (list).
        evidence_by_edge: dict mapping edge_id → list of evidence dicts (each with
            'source_organisation').

    Returns:
        A tuple of (upgraded_relationships, stats). The relationships are NEW
        dicts (originals not mutated). Each has its 'validation_status' field
        updated.
    """
    val_results = validation_results or []
    ev_by_edge = evidence_by_edge or {}

    # Index validation results by (company_id, driver_id).
    val_by_pair: dict[tuple[str, str], dict] = {}
    for vr in val_results:
        key = (vr.get("company_id", ""), vr.get("driver_id", ""))
        val_by_pair[key] = vr

    stats = StatusUpgradeStats(total=len(relationships))

    upgraded: list[dict] = []
    for rel in relationships:
        rel_copy = dict(rel)
        current_status = rel.get("validation_status", "hypothesized")

        # Determine which identifiers to use for lookup.
        company_id = rel.get("company_id") or rel.get("from_id", "")
        driver_id = rel.get("driver_id") or rel.get("to_id", "")
        edge_id = rel.get("id", "")

        # Look up validation results for this pair.
        val_result = val_by_pair.get((company_id, driver_id), {})

        # Extract validation signals.
        rolling_beta = val_result.get("rolling_beta", {})
        has_beta = rolling_beta.get("beta") is not None
        beta_p = rolling_beta.get("p_value")
        beta_significant = beta_p is not None and beta_p < 0.05
        beta_value = rolling_beta.get("beta")

        # Determine if beta direction matches the predicted direction.
        # The predicted direction is negative if the relationship's direction
        # is "negative" or "hurt_by"; positive if "positive" or "benefits_from".
        rel_direction = rel.get("direction", "")
        edge_type = rel.get("edge_type", "")
        predicted_negative = rel_direction in ("negative",) or edge_type in ("hurt_by", "exposed_to")
        predicted_positive = rel_direction in ("positive",) or edge_type in ("benefits_from",)

        beta_direction_matches = False
        if beta_value is not None:
            if predicted_negative and beta_value < 0:
                beta_direction_matches = True
            elif predicted_positive and beta_value > 0:
                beta_direction_matches = True

        # Extract shock analysis signals.
        shock_analyses = val_result.get("shock_analyses", [])
        shock_count = len(shock_analyses)
        shocks_correct_direction = sum(
            1 for s in shock_analyses
            if s.get("actual_vs_predicted") is not None and s["actual_vs_predicted"] > 0
        )

        # Extract evidence signals.
        evidence_list = ev_by_edge.get(edge_id, [])
        evidence_count = len(evidence_list)
        independent_sources = len(set(
            e.get("source_organisation", "") for e in evidence_list
            if e.get("source_organisation")
        ))
        has_evidence = evidence_count > 0

        # Determine new status.
        new_status = determine_validation_status(
            current_status,
            has_evidence=has_evidence,
            evidence_count=evidence_count,
            independent_sources=independent_sources,
            has_beta=has_beta,
            beta_significant=beta_significant,
            beta_direction_matches=beta_direction_matches,
            shock_count=shock_count,
            shocks_correct_direction=shocks_correct_direction,
        )

        # Track stats.
        if new_status != current_status:
            if new_status == "validated":
                stats.upgraded_to_validated += 1
            elif new_status == "weakly_supported":
                stats.upgraded_to_weakly_supported += 1
        else:
            stats.unchanged += 1

        rel_copy["validation_status"] = new_status
        # Add validation metadata for transparency.
        rel_copy["_validation_metadata"] = {
            "has_evidence": has_evidence,
            "evidence_count": evidence_count,
            "independent_sources": independent_sources,
            "has_beta": has_beta,
            "beta_significant": beta_significant,
            "beta_direction_matches": beta_direction_matches,
            "shock_count": shock_count,
            "shocks_correct_direction": shocks_correct_direction,
            "previous_status": current_status,
            "new_status": new_status,
        }

        upgraded.append(rel_copy)

    # Compute final counts.
    from collections import Counter
    stats.final_counts = dict(Counter(r["validation_status"] for r in upgraded))

    return upgraded, stats
