"""
Leontief input-output model for shock propagation through the value chain.

This module implements a simplified Leontief model adapted to InvestorLens's
value-chain graph. Instead of using economy-wide Supply and Use Tables (SUT),
we build the input-output matrix directly from value-chain edges — each edge
represents a "flow" from one node to another with a magnitude (percentage).

────────────────────────────────────────────────────────────────────────
MATHEMATICAL FOUNDATION (documented per Operating Principle 11)
────────────────────────────────────────────────────────────────────────

Setup:
  - N nodes in the value-chain graph (companies, sectors, raw_materials,
    products, macro_drivers).
  - A is the N×N technical coefficient matrix:
      A[i][j] = weight of edge from node i to node j / sum of all edge weights into node j
    If node j has no incoming edges, A[i][j] = 0 for all i.
    Each column of A sums to ≤ 1 (node j's total input share).

Leontief Inverse:
  L = (I - A)^(-1)
  where I is the N×N identity matrix.

  L[i][j] captures the total (direct + indirect) output from node i required
  to satisfy one unit of final demand for node j. If L[i][j] = 0.5, a 1-unit
  increase in demand for j requires 0.5 units of output from i (including
  all indirect effects through the chain).

Shock Propagation:
  A shock to driver d with magnitude s (e.g. crude oil price +10%):
    Δx = L × e_d × s
  where e_d is the unit vector for driver d (1 at position d, 0 elsewhere).

  Δx[i] = L[i][d] × s = the total impact on node i from the shock to d.

  If Δx[i] > 0: node i is positively affected (output increases).
  If Δx[i] < 0: node i is negatively affected (output decreases).
  If Δx[i] ≈ 0: node i is not materially affected.

Assumptions and Limitations:
  1. LINEARITY: The model assumes proportional relationships (double the
     shock = double the impact). Real-world relationships may be non-linear
     (e.g. capacity constraints, threshold effects).
  2. STATIC: The model captures a snapshot, not dynamics. It doesn't model
     time lags, inventory cycles, or adjustment paths.
  3. NO SUBSTITUTION: The model assumes the input-output structure doesn't
     change in response to the shock. In reality, companies may substitute
     inputs, change suppliers, or innovate around constraints.
  4. NORMALIZED WEIGHTS: Edge weights are normalized so each column sums to
     ≤ 1. This is an approximation — real input-output tables use monetary
     values, not percentage weights.
  5. NO FEEDBACK LOOPS: If the graph has cycles, the Leontief inverse may
     amplify effects unrealistically. We detect cycles and warn.

DO NOT present model outputs as predictions. They are directional indicators
of relative exposure, not quantitative forecasts. Phase 4.4 (empirical
validation) will test whether the model's predictions match historical data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "LeontiefModel",
    "ShockResult",
    "build_model",
    "simulate_shock",
]


@dataclass
class ShockResult:
    """Result of a shock propagation simulation.

    Fields:
      - driver_id: the node ID of the shocked driver
      - driver_label: human-readable name of the driver
      - shock_magnitude: the input shock magnitude (e.g. 0.10 for +10%)
      - impacts: list of (node_id, node_label, impact_value) sorted by
        absolute impact descending. Only nodes with |impact| > threshold
        are included.
      - total_impact: sum of all positive impacts (gross output expansion)
      - max_impact: the largest single-node impact
      - affected_count: number of nodes with |impact| > threshold
    """

    driver_id: str
    driver_label: str
    shock_magnitude: float
    impacts: list[tuple[str, str, float]] = field(default_factory=list)
    total_impact: float = 0.0
    max_impact: float = 0.0
    affected_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "driver_id": self.driver_id,
            "driver_label": self.driver_label,
            "shock_magnitude": self.shock_magnitude,
            "impacts": [
                {"node_id": nid, "node_label": nlabel, "impact": round(imp, 6)}
                for nid, nlabel, imp in self.impacts
            ],
            "total_impact": round(self.total_impact, 6),
            "max_impact": round(self.max_impact, 6),
            "affected_count": self.affected_count,
        }


@dataclass
class LeontiefModel:
    """A computed Leontief model ready for shock simulation.

    Fields:
      - node_ids: ordered list of node IDs (maps matrix indices to node IDs)
      - node_labels: ordered list of human-readable labels (parallel to node_ids)
      - matrix_a: N×N technical coefficient matrix (column-normalized edge weights)
      - matrix_l: N×N Leontief inverse = (I - A)^(-1)
      - has_cycles: True if the graph has cycles (may cause unrealistic amplification)
    """

    node_ids: list[str]
    node_labels: list[str]
    matrix_a: np.ndarray
    matrix_l: np.ndarray
    has_cycles: bool

    def simulate_shock(
        self,
        driver_id: str,
        magnitude: float,
        *,
        threshold: float = 0.001,
        max_results: int = 50,
    ) -> ShockResult:
        """Simulate a shock to a driver and return the propagation results.

        Args:
            driver_id: the node ID of the driver to shock.
            magnitude: the shock magnitude (e.g. 0.10 for +10%, -0.05 for -5%).
            threshold: minimum |impact| to include in results.
            max_results: maximum number of impacted nodes to return.

        Returns:
            A ShockResult with ranked impacts.
        """
        if driver_id not in self.node_ids:
            return ShockResult(
                driver_id=driver_id,
                driver_label="(unknown)",
                shock_magnitude=magnitude,
            )

        d_idx = self.node_ids.index(driver_id)
        driver_label = self.node_labels[d_idx]

        # Shock vector: unit vector at driver position × magnitude
        # For SUPPLY shocks (our use case: driver shock → downstream impact),
        # we use the ROW of L at position d: impacts[j] = L[d][j] × magnitude
        # This captures: "if driver d's output changes by `magnitude`, how much
        # does node j's output change?" — including direct and indirect effects.
        #
        # Mathematical basis:
        #   L = (I - A)^{-1}
        #   L[d][j] = total flow from d to j (direct + indirect)
        #   A supply shock to d propagates: d → direct dependents → their dependents → ...
        #   The row L[d][:] captures this full propagation chain.
        impacts = self.matrix_l[d_idx, :] * magnitude

        # Build sorted impact list.
        impact_list: list[tuple[str, str, float]] = []
        for i, (nid, nlabel) in enumerate(zip(self.node_ids, self.node_labels)):
            if i == d_idx:
                continue  # skip the driver itself
            imp = float(impacts[i])
            if abs(imp) > threshold:
                impact_list.append((nid, nlabel, imp))

        # Sort by absolute impact descending.
        impact_list.sort(key=lambda x: abs(x[2]), reverse=True)
        impact_list = impact_list[:max_results]

        positive_impacts = [imp for _, _, imp in impact_list if imp > 0]
        total_impact = sum(positive_impacts)
        max_impact = max((abs(imp) for _, _, imp in impact_list), default=0.0)

        return ShockResult(
            driver_id=driver_id,
            driver_label=driver_label,
            shock_magnitude=magnitude,
            impacts=impact_list,
            total_impact=round(total_impact, 6),
            max_impact=round(max_impact, 6),
            affected_count=len(impact_list),
        )


def build_model(
    edges: list[dict],
    node_labels: dict[str, str] | None = None,
    *,
    reverse_exposure_edges: bool = True,
) -> LeontiefModel:
    """Build a Leontief model from value-chain edges.

    Args:
        edges: list of edge dicts, each with:
            - from_id: source node ID
            - to_id: target node ID
            - magnitude_percent: optional weight (0-100). If None, weight=1.0.
            - edge_type: optional type (used for reversing exposure edges)
        node_labels: optional dict mapping node_id → human-readable label.
        reverse_exposure_edges: if True (default), reverse the direction of
            exposure-type edges (hurt_by, exposed_to, benefits_from) so that
            the driver becomes the source and the company becomes the target.
            This is necessary because in the value-chain graph, exposure edges
            go Company → Driver ("company is hurt by driver"), but for shock
            propagation we need Driver → Company ("driver shock affects company").

    Returns:
        A LeontiefModel ready for shock simulation.
    """
    labels = node_labels or {}

    # Pre-process edges: reverse exposure-type edges if requested.
    _EXPOSURE_TYPES = {"hurt_by", "exposed_to", "benefits_from"}
    processed_edges = []
    for e in edges:
        edge_type = e.get("edge_type", "")
        if reverse_exposure_edges and edge_type in _EXPOSURE_TYPES:
            # Reverse: swap from_id and to_id
            processed_edges.append({
                **e,
                "from_id": e.get("to_id", ""),
                "to_id": e.get("from_id", ""),
            })
        else:
            processed_edges.append(e)

    edges = processed_edges

    # Collect unique node IDs.
    node_set: set[str] = set()
    for e in edges:
        node_set.add(e.get("from_id", ""))
        node_set.add(e.get("to_id", ""))
    node_set.discard("")
    node_ids = sorted(node_set)
    n = len(node_ids)
    node_index = {nid: i for i, nid in enumerate(node_ids)}

    if n == 0:
        return LeontiefModel(
            node_ids=[],
            node_labels=[],
            matrix_a=np.zeros((0, 0)),
            matrix_l=np.zeros((0, 0)),
            has_cycles=False,
        )

    # Build raw weight matrix.
    raw_matrix = np.zeros((n, n))
    for e in edges:
        from_id = e.get("from_id", "")
        to_id = e.get("to_id", "")
        if from_id not in node_index or to_id not in node_index:
            continue
        i = node_index[from_id]
        j = node_index[to_id]
        weight = e.get("magnitude_percent")
        if weight is not None:
            raw_matrix[i][j] = weight / 100.0  # convert % to fraction
        else:
            raw_matrix[i][j] = 1.0  # unweighted = 1.0

    # Normalize each column so it sums to ≤ 1.
    matrix_a = np.zeros((n, n))
    for j in range(n):
        col_sum = raw_matrix[:, j].sum()
        if col_sum > 0:
            matrix_a[:, j] = raw_matrix[:, j] / col_sum
        # else: column stays zero (node j has no inputs)

    # Detect cycles: check if any node appears in both from and to of edges
    # (i.e. if the graph has any back-path). A simpler check: if any diagonal
    # element of A is > 0, or if (I - A) is nearly singular.
    has_cycles = False
    for i in range(n):
        if matrix_a[i][i] > 0:
            has_cycles = True
            break
    if not has_cycles:
        # Check if the spectral radius of A is close to 1 (indicates cycles
        # or strong feedback).
        try:
            eigenvalues = np.linalg.eigvals(matrix_a)
            spectral_radius = max(abs(eigenvalues))
            if spectral_radius > 0.95:
                has_cycles = True
        except np.linalg.LinAlgError:
            has_cycles = True

    # Compute Leontief inverse: L = (I - A)^(-1)
    identity = np.eye(n)
    try:
        matrix_l = np.linalg.inv(identity - matrix_a)
    except np.linalg.LinAlgError:
        # Singular matrix — use pseudo-inverse as fallback.
        matrix_l = np.linalg.pinv(identity - matrix_a)

    node_label_list = [labels.get(nid, nid) for nid in node_ids]

    return LeontiefModel(
        node_ids=node_ids,
        node_labels=node_label_list,
        matrix_a=matrix_a,
        matrix_l=matrix_l,
        has_cycles=has_cycles,
    )


def simulate_shock(
    model: LeontiefModel,
    driver_id: str,
    magnitude: float,
    *,
    threshold: float = 0.001,
    max_results: int = 50,
) -> ShockResult:
    """Simulate a shock to a driver in the model.

    Convenience wrapper around model.simulate_shock().
    """
    return model.simulate_shock(
        driver_id,
        magnitude,
        threshold=threshold,
        max_results=max_results,
    )
