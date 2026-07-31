"""Tests for the status upgrader (investorlens.algorithms.status_upgrader)."""

from __future__ import annotations

import pytest

from investorlens.algorithms.status_upgrader import (
    StatusUpgradeStats,
    determine_validation_status,
    upgrade_relationship_statuses,
)


class TestDetermineValidationStatus:
    def test_hypothesized_with_no_evidence_stays_hypothesized(self) -> None:
        result = determine_validation_status("hypothesized")
        assert result == "hypothesized"

    def test_hypothesized_with_evidence_upgrades_to_weakly(self) -> None:
        result = determine_validation_status("hypothesized", has_evidence=True)
        assert result == "weakly_supported"

    def test_hypothesized_with_beta_upgrades_to_weakly(self) -> None:
        result = determine_validation_status("hypothesized", has_beta=True)
        assert result == "weakly_supported"

    def test_weakly_with_significant_beta_and_correct_direction_upgrades_to_validated(self) -> None:
        result = determine_validation_status(
            "weakly_supported",
            has_beta=True, beta_significant=True, beta_direction_matches=True,
        )
        assert result == "validated"

    def test_weakly_with_significant_beta_but_wrong_direction_stays_weakly(self) -> None:
        result = determine_validation_status(
            "weakly_supported",
            has_beta=True, beta_significant=True, beta_direction_matches=False,
        )
        assert result == "weakly_supported"

    def test_weakly_with_2_correct_shocks_upgrades_to_validated(self) -> None:
        result = determine_validation_status(
            "weakly_supported",
            shock_count=3, shocks_correct_direction=2,
        )
        assert result == "validated"

    def test_weakly_with_1_correct_shock_stays_weakly(self) -> None:
        result = determine_validation_status(
            "weakly_supported",
            shock_count=2, shocks_correct_direction=1,
        )
        assert result == "weakly_supported"

    def test_weakly_with_2_independent_sources_upgrades_to_validated(self) -> None:
        result = determine_validation_status(
            "weakly_supported",
            independent_sources=2,
        )
        assert result == "validated"

    def test_validated_never_downgraded(self) -> None:
        """A VALIDATED status should never be downgraded, even with no evidence."""
        result = determine_validation_status("validated")
        assert result == "validated"

    def test_validated_never_downgraded_even_with_weak_evidence(self) -> None:
        result = determine_validation_status(
            "validated",
            has_evidence=False, has_beta=False,
        )
        assert result == "validated"


class TestUpgradeRelationshipStatuses:
    def test_empty_relationships(self) -> None:
        upgraded, stats = upgrade_relationship_statuses([])
        assert upgraded == []
        assert stats.total == 0

    def test_hypothesized_with_no_validation_stays_hypothesized(self) -> None:
        relationships = [
            {"id": "edge_1", "validation_status": "hypothesized", "from_id": "a", "to_id": "b"},
        ]
        upgraded, stats = upgrade_relationship_statuses(relationships)
        assert upgraded[0]["validation_status"] == "hypothesized"
        assert stats.unchanged == 1

    def test_upgrades_with_evidence(self) -> None:
        relationships = [
            {"id": "edge_1", "validation_status": "hypothesized", "from_id": "a", "to_id": "b"},
        ]
        evidence = {"edge_1": [{"source_organisation": "CRISIL"}]}
        upgraded, stats = upgrade_relationship_statuses(relationships, evidence_by_edge=evidence)
        assert upgraded[0]["validation_status"] == "weakly_supported"
        assert stats.upgraded_to_weakly_supported == 1

    def test_upgrades_with_significant_beta(self) -> None:
        relationships = [
            {"id": "edge_1", "validation_status": "weakly_supported",
             "company_id": "sec_a", "driver_id": "drv_b", "direction": "negative"},
        ]
        validation_results = [
            {"company_id": "sec_a", "driver_id": "drv_b",
             "rolling_beta": {"beta": -0.5, "p_value": 0.01, "n_observations": 100},
             "shock_analyses": []},
        ]
        upgraded, stats = upgrade_relationship_statuses(relationships, validation_results)
        assert upgraded[0]["validation_status"] == "validated"
        assert stats.upgraded_to_validated == 1

    def test_does_not_upgrade_with_wrong_direction_beta(self) -> None:
        """If the model predicts negative but beta is positive, don't validate."""
        relationships = [
            {"id": "edge_1", "validation_status": "weakly_supported",
             "company_id": "sec_a", "driver_id": "drv_b", "direction": "negative"},
        ]
        validation_results = [
            {"company_id": "sec_a", "driver_id": "drv_b",
             "rolling_beta": {"beta": 0.5, "p_value": 0.01, "n_observations": 100},
             "shock_analyses": []},
        ]
        upgraded, stats = upgrade_relationship_statuses(relationships, validation_results)
        assert upgraded[0]["validation_status"] == "weakly_supported"

    def test_validated_not_downgraded(self) -> None:
        relationships = [
            {"id": "edge_1", "validation_status": "validated", "from_id": "a", "to_id": "b"},
        ]
        upgraded, stats = upgrade_relationship_statuses(relationships)
        assert upgraded[0]["validation_status"] == "validated"

    def test_validation_metadata_added(self) -> None:
        """Each upgraded relationship should have _validation_metadata for transparency."""
        relationships = [
            {"id": "edge_1", "validation_status": "hypothesized", "from_id": "a", "to_id": "b"},
        ]
        evidence = {"edge_1": [{"source_organisation": "CRISIL"}]}
        upgraded, _ = upgrade_relationship_statuses(relationships, evidence_by_edge=evidence)
        assert "_validation_metadata" in upgraded[0]
        meta = upgraded[0]["_validation_metadata"]
        assert meta["has_evidence"] is True
        assert meta["evidence_count"] == 1
        assert meta["independent_sources"] == 1
        assert meta["previous_status"] == "hypothesized"
        assert meta["new_status"] == "weakly_supported"

    def test_stats_correct(self) -> None:
        relationships = [
            {"id": "e1", "validation_status": "hypothesized", "from_id": "a", "to_id": "b"},
            {"id": "e2", "validation_status": "hypothesized", "from_id": "c", "to_id": "d"},
            {"id": "e3", "validation_status": "validated", "from_id": "e", "to_id": "f"},
        ]
        evidence = {"e1": [{"source_organisation": "CRISIL"}]}
        upgraded, stats = upgrade_relationship_statuses(relationships, evidence_by_edge=evidence)
        assert stats.total == 3
        assert stats.upgraded_to_weakly_supported == 1  # e1
        assert stats.upgraded_to_validated == 0
        assert stats.unchanged == 2  # e2 stays hypothesized, e3 stays validated
        assert stats.final_counts["hypothesized"] == 1
        assert stats.final_counts["weakly_supported"] == 1
        assert stats.final_counts["validated"] == 1

    def test_original_not_mutated(self) -> None:
        relationships = [
            {"id": "e1", "validation_status": "hypothesized", "from_id": "a", "to_id": "b"},
        ]
        evidence = {"e1": [{"source_organisation": "CRISIL"}]}
        upgrade_relationship_statuses(relationships, evidence_by_edge=evidence)
        assert relationships[0]["validation_status"] == "hypothesized"  # unchanged

    def test_stats_to_dict(self) -> None:
        stats = StatusUpgradeStats(total=10, upgraded_to_weakly_supported=3, upgraded_to_validated=1)
        d = stats.to_dict()
        assert d["total"] == 10
        assert d["upgraded_to_weakly_supported"] == 3
        assert d["upgraded_to_validated"] == 1
