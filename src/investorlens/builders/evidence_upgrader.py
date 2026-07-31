"""
Evidence upgrader — upgrades ValueChainEdge validation_status based on Evidence records.

Upgrade rules:
  - 0 evidence → HYPOTHESIZED (default, no change)
  - 1 evidence → WEAKLY_SUPPORTED
  - 2+ evidence from independent sources → VALIDATED

"Independent sources" means evidence records from different source_organisation
values. Two pieces of evidence from the same CRISIL report count as 1 source.

Pure function: takes edges + evidence, returns upgraded edges. No I/O.
"""

from __future__ import annotations

from typing import Any

from ..models import Evidence, ValidationStatus, ValueChainEdge

__all__ = ["upgrade_edges_with_evidence", "count_evidence_by_edge"]


def count_evidence_by_edge(evidence: list[Evidence]) -> dict[str, dict[str, Any]]:
    """Count evidence per edge, grouped by source organisation.

    Returns a dict: {edge_id: {"total": N, "organisations": set(...), "records": [Evidence, ...]}}
    """
    by_edge: dict[str, dict[str, Any]] = {}
    for e in evidence:
        edge_id = e.edge_id
        if edge_id not in by_edge:
            by_edge[edge_id] = {"total": 0, "organisations": set(), "records": []}
        by_edge[edge_id]["total"] += 1
        if e.source_organisation:
            by_edge[edge_id]["organisations"].add(e.source_organisation)
        by_edge[edge_id]["records"].append(e)
    return by_edge


def _determine_validation_status(evidence_info: dict[str, Any] | None) -> ValidationStatus:
    """Determine the validation status for an edge based on its evidence.

    Rules:
      - No evidence → HYPOTHESIZED
      - 1 evidence → WEAKLY_SUPPORTED
      - 2+ evidence from independent organisations → VALIDATED
      - 2+ evidence from same organisation → WEAKLY_SUPPORTED (still only 1 source)
    """
    if not evidence_info or evidence_info["total"] == 0:
        return ValidationStatus.HYPOTHESIZED
    if evidence_info["total"] == 1:
        return ValidationStatus.WEAKLY_SUPPORTED
    # 2+ evidence records: check if they're from independent sources
    org_count = len(evidence_info["organisations"])
    if org_count >= 2:
        return ValidationStatus.VALIDATED
    # Multiple evidence but same source organisation → still weakly supported
    return ValidationStatus.WEAKLY_SUPPORTED


def upgrade_edges_with_evidence(
    edges: list[ValueChainEdge],
    evidence: list[Evidence],
) -> tuple[list[ValueChainEdge], dict[str, int]]:
    """Upgrade edge validation statuses based on evidence records.

    Args:
        edges: list of ValueChainEdge records to upgrade.
        evidence: list of Evidence records linking to edge IDs.

    Returns:
        A tuple of (upgraded_edges, stats) where stats is a dict with:
          - "total_edges": total edges processed
          - "edges_with_evidence": edges that have at least 1 evidence record
          - "upgraded_to_weakly_supported": count of edges upgraded to WEAKLY_SUPPORTED
          - "upgraded_to_validated": count of edges upgraded to VALIDATED
          - "unchanged": count of edges that stayed HYPOTHESIZED

    The returned edges are NEW objects (the originals are not mutated).
    Edges that already have VALIDATED status are not downgraded.
    """
    evidence_by_edge = count_evidence_by_edge(evidence)

    stats = {
        "total_edges": len(edges),
        "edges_with_evidence": 0,
        "upgraded_to_weakly_supported": 0,
        "upgraded_to_validated": 0,
        "unchanged": 0,
    }

    upgraded: list[ValueChainEdge] = []
    for edge in edges:
        ev_info = evidence_by_edge.get(edge.id)
        new_status = _determine_validation_status(ev_info)

        if ev_info and ev_info["total"] > 0:
            stats["edges_with_evidence"] += 1

        # Don't downgrade already-validated edges
        if edge.validation_status == ValidationStatus.VALIDATED and new_status != ValidationStatus.VALIDATED:
            new_status = ValidationStatus.VALIDATED

        # Track upgrades
        if new_status != edge.validation_status:
            if new_status == ValidationStatus.WEAKLY_SUPPORTED:
                stats["upgraded_to_weakly_supported"] += 1
            elif new_status == ValidationStatus.VALIDATED:
                stats["upgraded_to_validated"] += 1
        else:
            stats["unchanged"] += 1

        # Create a new edge with the updated status (don't mutate the original)
        upgraded_edge = edge.model_copy(update={"validation_status": new_status})
        upgraded.append(upgraded_edge)

    return upgraded, stats
