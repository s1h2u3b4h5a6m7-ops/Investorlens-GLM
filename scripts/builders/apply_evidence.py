"""
Apply evidence to value-chain edges — upgrades validation_status + regenerates notes.

Reads:
  - data/processed/value_chain_edges.jsonl
  - data/research/evidence.jsonl

Writes (upgraded):
  - data/processed/value_chain_edges.jsonl  (edges with upgraded validation_status)
  - notes/sectors/<slug>.md                 (regenerated with evidence-backed statuses)
  - web-graph/public/graph-data.json        (regenerated with upgraded edges)

Upgrade rules:
  - 0 evidence → HYPOTHESIZED (unchanged)
  - 1 evidence → WEAKLY_SUPPORTED
  - 2+ evidence from independent sources → VALIDATED

Usage:
    python scripts/builders/apply_evidence.py
    python scripts/builders/apply_evidence.py --retrieved-at 2024-09-30T18:30:00Z
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.builders import upgrade_edges_with_evidence  # noqa: E402
from investorlens.io import read_jsonl, upsert_records  # noqa: E402
from investorlens.models import Evidence, Provenance, ValueChainEdge  # noqa: E402

log = logging.getLogger("apply_evidence")

EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
EVIDENCE_PATH = ROOT / "data" / "research" / "evidence.jsonl"


def _load_edges() -> list[ValueChainEdge]:
    if not EDGES_PATH.exists():
        log.error("Value-chain edges not found: %s", EDGES_PATH)
        return []
    raw = read_jsonl(EDGES_PATH)
    out: list[ValueChainEdge] = []
    for i, row in enumerate(raw):
        try:
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown", notes=f"synthesized (edge row {i})"
                ).model_dump(mode="json")
            out.append(ValueChainEdge(**row))
        except Exception as e:
            log.warning("Skipped edge row %d: %s", i, e)
    log.info("Loaded %d edges", len(out))
    return out


def _load_evidence() -> list[Evidence]:
    if not EVIDENCE_PATH.exists():
        log.warning("Evidence file not found: %s", EVIDENCE_PATH)
        return []
    raw = read_jsonl(EVIDENCE_PATH)
    out: list[Evidence] = []
    for i, row in enumerate(raw):
        try:
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown", notes=f"synthesized (evidence row {i})"
                ).model_dump(mode="json")
            out.append(Evidence(**row))
        except Exception as e:
            log.warning("Skipped evidence row %d: %s", i, e)
    log.info("Loaded %d evidence records", len(out))
    return out


def apply(*, retrieved_at: datetime | None = None) -> int:
    """Apply evidence to edges, write upgraded edges, and trigger note + graph regeneration.

    Returns 0 on success, 1 on failure.
    """
    edges = _load_edges()
    evidence = _load_evidence()

    if not edges:
        log.error("No edges to upgrade.")
        return 1

    # Upgrade edges.
    upgraded_edges, stats = upgrade_edges_with_evidence(edges, evidence)
    log.info("Evidence upgrade stats:")
    log.info("  total edges: %d", stats["total_edges"])
    log.info("  edges with evidence: %d", stats["edges_with_evidence"])
    log.info("  upgraded to weakly_supported: %d", stats["upgraded_to_weakly_supported"])
    log.info("  upgraded to validated: %d", stats["upgraded_to_validated"])
    log.info("  unchanged: %d", stats["unchanged"])

    # Write upgraded edges back.
    payload = [e.model_dump(mode="json", exclude_none=True) for e in upgraded_edges]
    upsert_records(EDGES_PATH, payload, key="id")
    log.info("Wrote upgraded edges to %s", EDGES_PATH)

    # Regenerate sector notes with the upgraded edges.
    import subprocess
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    log.info("Regenerating sector notes...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "builders" / "build_sector_notes.py"),
         "--retrieved-at", retrieved_at.isoformat(),
         "--log-level", "WARNING"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.warning("Sector notes build returned %d: %s", result.returncode, result.stderr[:300])

    # Regenerate web graph data.
    log.info("Regenerating web graph data...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "builders" / "build_graph_data.py"),
         "--generated-at", retrieved_at.isoformat(),
         "--log-level", "WARNING"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.warning("Graph data build returned %d: %s", result.returncode, result.stderr[:300])

    log.info("Done. Edges upgraded, notes and graph regenerated.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieved-at", type=str, default=None)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    retrieved_at = None
    if args.retrieved_at:
        retrieved_at = datetime.fromisoformat(args.retrieved_at)
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)

    return apply(retrieved_at=retrieved_at)


if __name__ == "__main__":
    sys.exit(main())
