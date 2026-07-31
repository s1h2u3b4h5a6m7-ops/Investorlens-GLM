"""Tests for the evidence upgrader (investorlens.builders.evidence_upgrader)."""

from __future__ import annotations

import pytest

from investorlens.builders.evidence_upgrader import (
    count_evidence_by_edge,
    upgrade_edges_with_evidence,
)
from investorlens.models import (
    Evidence,
    Provenance,
    SourceType,
    ValidationStatus,
    ValueChainEdge,
    ValueChainEdgeType,
)
from investorlens.models.provenance import Confidence


@pytest.fixture
def prov() -> Provenance:
    return Provenance(source="investorlens", confidence=Confidence.MEDIUM)


def _make_edge(prov: Provenance = None, from_id: str = "sec_a", to_id: str = "rm_b") -> ValueChainEdge:
    """Create a ValueChainEdge. The ID is auto-computed from (from_id, to_id, edge_type)."""
    if prov is None:
        prov = Provenance(source="investorlens")
    return ValueChainEdge(
        from_id=from_id,
        to_id=to_id,
        edge_type=ValueChainEdgeType.USES,
        provenance=prov,
    )


def _make_evidence(edge_id: str, org: str, prov: Provenance) -> Evidence:
    return Evidence(
        edge_id=edge_id,
        fact="Test fact",
        source_type=SourceType.CREDIT_RATING_RATIONALE,
        source_organisation=org,
        provenance=prov,
    )


class TestCountEvidenceByEdge:
    def test_empty_evidence(self) -> None:
        result = count_evidence_by_edge([])
        assert result == {}

    def test_single_evidence(self, prov: Provenance) -> None:
        ev = _make_evidence("edge_1", "CRISIL", prov)
        result = count_evidence_by_edge([ev])
        assert "edge_1" in result
        assert result["edge_1"]["total"] == 1
        assert "CRISIL" in result["edge_1"]["organisations"]

    def test_multiple_evidence_same_edge_different_orgs(self, prov: Provenance) -> None:
        ev1 = _make_evidence("edge_1", "CRISIL", prov)
        ev2 = _make_evidence("edge_1", "ICRA", prov)
        result = count_evidence_by_edge([ev1, ev2])
        assert result["edge_1"]["total"] == 2
        assert len(result["edge_1"]["organisations"]) == 2

    def test_multiple_evidence_same_edge_same_org(self, prov: Provenance) -> None:
        ev1 = _make_evidence("edge_1", "CRISIL", prov)
        ev2 = _make_evidence("edge_1", "CRISIL", prov)
        result = count_evidence_by_edge([ev1, ev2])
        assert result["edge_1"]["total"] == 2
        assert len(result["edge_1"]["organisations"]) == 1

    def test_evidence_for_different_edges(self, prov: Provenance) -> None:
        ev1 = _make_evidence("edge_1", "CRISIL", prov)
        ev2 = _make_evidence("edge_2", "ICRA", prov)
        result = count_evidence_by_edge([ev1, ev2])
        assert len(result) == 2
        assert "edge_1" in result
        assert "edge_2" in result


class TestUpgradeEdgesWithEvidence:
    def test_no_evidence_keeps_hypothesized(self, prov: Provenance) -> None:
        edge = _make_edge(prov=prov)
        upgraded, stats = upgrade_edges_with_evidence([edge], [])
        assert upgraded[0].validation_status == ValidationStatus.HYPOTHESIZED
        assert stats["upgraded_to_weakly_supported"] == 0
        assert stats["upgraded_to_validated"] == 0
        assert stats["unchanged"] == 1

    def test_one_evidence_upgrades_to_weakly_supported(self, prov: Provenance) -> None:
        edge = _make_edge(prov=prov)
        ev = _make_evidence(edge.id, "CRISIL", prov)
        upgraded, stats = upgrade_edges_with_evidence([edge], [ev])
        assert upgraded[0].validation_status == ValidationStatus.WEAKLY_SUPPORTED
        assert stats["upgraded_to_weakly_supported"] == 1
        assert stats["upgraded_to_validated"] == 0

    def test_two_evidence_different_orgs_upgrades_to_validated(self, prov: Provenance) -> None:
        edge = _make_edge(prov=prov)
        ev1 = _make_evidence(edge.id, "CRISIL", prov)
        ev2 = _make_evidence(edge.id, "ICRA", prov)
        upgraded, stats = upgrade_edges_with_evidence([edge], [ev1, ev2])
        assert upgraded[0].validation_status == ValidationStatus.VALIDATED
        assert stats["upgraded_to_validated"] == 1

    def test_two_evidence_same_org_stays_weakly_supported(self, prov: Provenance) -> None:
        edge = _make_edge(prov=prov)
        ev1 = _make_evidence(edge.id, "CRISIL", prov)
        ev2 = _make_evidence(edge.id, "CRISIL", prov)
        upgraded, stats = upgrade_edges_with_evidence([edge], [ev1, ev2])
        assert upgraded[0].validation_status == ValidationStatus.WEAKLY_SUPPORTED
        assert stats["upgraded_to_weakly_supported"] == 1
        assert stats["upgraded_to_validated"] == 0

    def test_validated_edge_not_downgraded(self, prov: Provenance) -> None:
        """An edge that's already VALIDATED should not be downgraded even if evidence is removed."""
        edge = ValueChainEdge(
            from_id="a", to_id="b", edge_type=ValueChainEdgeType.USES,
            validation_status=ValidationStatus.VALIDATED,
            provenance=prov,
        )
        upgraded, stats = upgrade_edges_with_evidence([edge], [])
        assert upgraded[0].validation_status == ValidationStatus.VALIDATED

    def test_original_edge_not_mutated(self, prov: Provenance) -> None:
        """The original edge object should not be mutated."""
        edge = _make_edge(prov=prov)
        original_status = edge.validation_status
        ev = _make_evidence(edge.id, "CRISIL", prov)
        upgrade_edges_with_evidence([edge], [ev])
        assert edge.validation_status == original_status  # unchanged

    def test_stats_correct(self, prov: Provenance) -> None:
        # Create 3 edges with different from_ids so they get different IDs.
        edge1 = _make_edge(prov=prov, from_id="sec_a", to_id="rm_x")
        edge2 = _make_edge(prov=prov, from_id="sec_b", to_id="rm_x")
        edge3 = _make_edge(prov=prov, from_id="sec_c", to_id="rm_x")
        edges = [edge1, edge2, edge3]

        evidence = [
            _make_evidence(edge1.id, "CRISIL", prov),  # edge1 → weakly_supported
            _make_evidence(edge2.id, "CRISIL", prov),  # edge2 → weakly_supported (1 org so far)
            _make_evidence(edge2.id, "ICRA", prov),    # edge2 → validated (2 orgs)
            # edge3 has no evidence → stays hypothesized
        ]
        upgraded, stats = upgrade_edges_with_evidence(edges, evidence)
        assert stats["total_edges"] == 3
        assert stats["edges_with_evidence"] == 2
        assert stats["upgraded_to_weakly_supported"] == 1  # edge1
        assert stats["upgraded_to_validated"] == 1          # edge2
        assert stats["unchanged"] == 1                      # edge3

    def test_empty_edges(self, prov: Provenance) -> None:
        upgraded, stats = upgrade_edges_with_evidence([], [])
        assert upgraded == []
        assert stats["total_edges"] == 0
