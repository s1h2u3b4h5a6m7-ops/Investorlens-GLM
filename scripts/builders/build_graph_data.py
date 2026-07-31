"""
Build graph data JSON for the InvestorLens web graph.

Reads:
  - data/master/isin_master.jsonl
  - data/processed/observations.jsonl
  - data/processed/corporate_actions.jsonl

Writes:
  - web-graph/public/graph-data.json  (consumed by the React + Cytoscape.js app)

The graph contains:
  - Company nodes (one per ISIN with data)
  - Sector nodes (one per distinct sector)
  - Macro driver nodes (one per distinct macro driver in observations)
  - belongs_to edges (company → sector)
  - exposed_to edges (company → macro driver; Phase 1 placeholder)

Idempotent: re-running with the same inputs + timestamp produces byte-identical
output (sorted keys, deterministic edge IDs).

Usage:
    python scripts/builders/build_graph_data.py
    python scripts/builders/build_graph_data.py --generated-at 2024-09-30T18:30:00Z
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.builders import build_graph_data  # noqa: E402
from investorlens.io import read_jsonl, write_json  # noqa: E402

log = logging.getLogger("build_graph_data")

ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
OBSERVATIONS_PATH = ROOT / "data" / "processed" / "observations.jsonl"
CORP_ACTIONS_PATH = ROOT / "data" / "processed" / "corporate_actions.jsonl"
VALUE_CHAIN_EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
PRODUCTS_PATH = ROOT / "data" / "master" / "products.jsonl"
OUTPUT_PATH = ROOT / "web-graph" / "public" / "graph-data.json"


def build(generated_at: datetime | None = None) -> int:
    """Build graph data and write to web-graph/public/graph-data.json.

    Returns 0 on success, 1 on failure.
    """
    if not ISIN_MASTER_PATH.exists():
        log.error("ISIN master not found: %s", ISIN_MASTER_PATH)
        return 1

    isin_master = read_jsonl(ISIN_MASTER_PATH)
    observations = read_jsonl(OBSERVATIONS_PATH) if OBSERVATIONS_PATH.exists() else []
    corp_actions = read_jsonl(CORP_ACTIONS_PATH) if CORP_ACTIONS_PATH.exists() else []
    value_chain_edges = read_jsonl(VALUE_CHAIN_EDGES_PATH) if VALUE_CHAIN_EDGES_PATH.exists() else []
    raw_materials = read_jsonl(RAW_MATERIALS_PATH) if RAW_MATERIALS_PATH.exists() else []
    products = read_jsonl(PRODUCTS_PATH) if PRODUCTS_PATH.exists() else []

    log.info("Loaded %d ISIN master, %d observations, %d corp actions, %d value-chain edges",
             len(isin_master), len(observations), len(corp_actions), len(value_chain_edges))

    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    graph = build_graph_data(
        isin_master, observations, corp_actions,
        value_chain_edges=value_chain_edges if value_chain_edges else None,
        raw_materials=raw_materials if raw_materials else None,
        products=products if products else None,
        generated_at=generated_at,
    )

    log.info("Built graph: %d nodes (%d companies, %d sectors, %d macro drivers), %d edges",
             graph["metadata"]["node_count"],
             graph["metadata"]["company_count"],
             graph["metadata"]["sector_count"],
             graph["metadata"]["macro_driver_count"],
             graph["metadata"]["edge_count"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_PATH, graph, indent=2, sort_keys=True)
    log.info("Wrote %s", OUTPUT_PATH.relative_to(ROOT) if OUTPUT_PATH.is_relative_to(ROOT) else OUTPUT_PATH)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generated-at",
        type=str,
        default=None,
        help="ISO-8601 UTC timestamp for metadata. Defaults to now().",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    generated_at = None
    if args.generated_at:
        generated_at = datetime.fromisoformat(args.generated_at)
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)

    return build(generated_at=generated_at)


if __name__ == "__main__":
    sys.exit(main())
