"""
Run the Leontief input-output model against InvestorLens value-chain data.

Builds the model from value-chain edges, then simulates shocks to key
macro drivers (USD/INR, crude oil, CPI) and reports the propagation
impact on companies, sectors, and raw materials.

Output:
  - Console: human-readable shock propagation results
  - data/processed/leontief_results.json: machine-readable results

Usage:
    python scripts/builders/run_leontief.py
    python scripts/builders/run_leontief.py --driver drv_fx_usd_inr --magnitude 0.10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.algorithms.leontief import build_model  # noqa: E402
from investorlens.io import read_jsonl, write_json  # noqa: E402

log = logging.getLogger("run_leontief")

EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
PRODUCTS_PATH = ROOT / "data" / "master" / "products.jsonl"
OUTPUT_PATH = ROOT / "data" / "processed" / "leontief_results.json"


def _build_node_labels(edges: list[dict]) -> dict[str, str]:
    """Build a lookup from node IDs to human-readable labels."""
    labels: dict[str, str] = {}
    # Try raw materials
    if RAW_MATERIALS_PATH.exists():
        for rm in read_jsonl(RAW_MATERIALS_PATH):
            labels[rm.get("id", "")] = rm.get("name", rm.get("id", ""))
    # Try products
    if PRODUCTS_PATH.exists():
        for p in read_jsonl(PRODUCTS_PATH):
            labels[p.get("id", "")] = p.get("name", p.get("id", ""))
    # Add edge from_id/to_id labels from edge notes (fallback)
    for e in edges:
        for key in ("from_id", "to_id"):
            nid = e.get(key, "")
            if nid and nid not in labels:
                labels[nid] = nid
    return labels


def run(
    driver_id: str | None = None,
    magnitude: float = 0.10,
) -> int:
    """Build the Leontief model and simulate shocks.

    Args:
        driver_id: if specified, simulate only this driver. If None, simulate
            all macro_driver nodes in the graph.
        magnitude: shock magnitude (default: 0.10 = +10%).

    Returns 0 on success, 1 on failure.
    """
    if not EDGES_PATH.exists():
        log.error("Value-chain edges not found: %s", EDGES_PATH)
        return 1

    edges = read_jsonl(EDGES_PATH)
    log.info("Loaded %d value-chain edges", len(edges))

    node_labels = _build_node_labels(edges)
    model = build_model(edges, node_labels=node_labels)

    log.info("Built Leontief model: %d nodes, %d edges", len(model.node_ids), len(edges))
    log.info("  has_cycles: %s", model.has_cycles)
    log.info("  matrix A shape: %s", model.matrix_a.shape)
    log.info("  matrix L shape: %s", model.matrix_l.shape)

    # Determine which drivers to shock.
    if driver_id:
        drivers = [driver_id]
    else:
        # Shock all macro_driver nodes (drv_*).
        drivers = [nid for nid in model.node_ids if nid.startswith("drv_")]

    if not drivers:
        log.warning("No macro drivers found in the graph. Use --driver to specify one.")
        return 1

    log.info("Simulating shocks to %d driver(s) with magnitude %.1f%%", len(drivers), magnitude * 100)

    results = []
    for drv in drivers:
        result = model.simulate_shock(drv, magnitude, threshold=0.001, max_results=20)
        results.append(result.to_dict())

        # Print human-readable summary.
        print(f"\n{'='*70}")
        print(f"Shock: {result.driver_label} {'+' if magnitude > 0 else ''}{magnitude*100:.1f}%")
        print(f"Affected nodes: {result.affected_count}")
        print(f"Total positive impact: {result.total_impact:.4f}")
        print(f"Max single-node impact: {result.max_impact:.4f}")
        print(f"{'-'*70}")
        print(f"{'Node':<40s} {'Impact':>10s} {'Direction':>10s}")
        print(f"{'-'*40} {'-'*10} {'-'*10}")
        for nid, nlabel, imp in result.impacts[:15]:
            direction = "↑ positive" if imp > 0 else "↓ negative"
            print(f"{nlabel[:40]:<40s} {imp:>10.4f} {direction:>10s}")
        if len(result.impacts) > 15:
            print(f"  ... and {len(result.impacts) - 15} more")

    # Save machine-readable results.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_PATH, {
        "model_info": {
            "node_count": len(model.node_ids),
            "edge_count": len(edges),
            "has_cycles": model.has_cycles,
        },
        "shock_magnitude": magnitude,
        "results": results,
    }, indent=2, sort_keys=True)
    log.info("Wrote results to %s", OUTPUT_PATH)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=str, default=None,
                        help="Specific driver node ID to shock (default: all drv_* nodes)")
    parser.add_argument("--magnitude", type=float, default=0.10,
                        help="Shock magnitude (default: 0.10 = +10%%)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    return run(driver_id=args.driver, magnitude=args.magnitude)


if __name__ == "__main__":
    sys.exit(main())
