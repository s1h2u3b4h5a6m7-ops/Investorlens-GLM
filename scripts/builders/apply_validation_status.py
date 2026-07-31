"""
Apply validation status to all relationships — the final Phase 4 algorithm.

Uses the empirical validation results (from Milestone 4.4) and evidence
records (from Milestone 3.2) to upgrade relationship statuses:

  HYPOTHESIZED -> WEAKLY_SUPPORTED (with evidence or computable beta)
  WEAKLY_SUPPORTED -> VALIDATED (significant beta + correct direction,
    or 2+ correct shocks, or 2+ independent sources)

Never downgrades. Never presents a hypothesis as an established fact.

Reads:
  - data/processed/value_chain_edges.jsonl
  - data/processed/exposures.jsonl
  - data/research/evidence.jsonl
  - data/processed/validation_results.json

Writes (upgraded):
  - data/processed/value_chain_edges.jsonl
  - data/processed/exposures.jsonl
  - data/processed/relationship_status_report.json (summary)
  - data/processed/relationship_status_report.md (human-readable)

Usage:
    python scripts/builders/apply_validation_status.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.algorithms.status_upgrader import upgrade_relationship_statuses  # noqa: E402
from investorlens.io import read_jsonl, upsert_records, write_json  # noqa: E402

log = logging.getLogger("apply_validation_status")

EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
EXPOSURES_PATH = ROOT / "data" / "processed" / "exposures.jsonl"
EVIDENCE_PATH = ROOT / "data" / "research" / "evidence.jsonl"
VALIDATION_PATH = ROOT / "data" / "processed" / "validation_results.json"
REPORT_JSON = ROOT / "data" / "processed" / "relationship_status_report.json"
REPORT_MD = ROOT / "data" / "processed" / "relationship_status_report.md"


def run() -> int:
    """Apply validation statuses to all relationships and write reports."""
    # Load all data.
    edges = read_jsonl(EDGES_PATH) if EDGES_PATH.exists() else []
    exposures = read_jsonl(EXPOSURES_PATH) if EXPOSURES_PATH.exists() else []
    evidence = read_jsonl(EVIDENCE_PATH) if EVIDENCE_PATH.exists() else []

    # Load validation results.
    validation_results = []
    if VALIDATION_PATH.exists():
        from investorlens.io import read_json
        val_data = read_json(VALIDATION_PATH)
        validation_results = val_data.get("results", [])

    log.info("Loaded %d edges, %d exposures, %d evidence, %d validation results",
             len(edges), len(exposures), len(evidence), len(validation_results))

    # Index evidence by edge_id.
    evidence_by_edge: dict[str, list[dict]] = {}
    for ev in evidence:
        eid = ev.get("edge_id", "")
        if eid:
            evidence_by_edge.setdefault(eid, []).append(ev)

    # Upgrade value-chain edges.
    log.info("Upgrading value-chain edges...")
    upgraded_edges, edge_stats = upgrade_relationship_statuses(
        edges, validation_results, evidence_by_edge,
    )
    log.info("  Edge stats: %s", edge_stats.to_dict())

    # Upgrade exposures.
    log.info("Upgrading exposures...")
    upgraded_exposures, exp_stats = upgrade_relationship_statuses(
        exposures, validation_results, evidence_by_edge,
    )
    log.info("  Exposure stats: %s", exp_stats.to_dict())

    # Write upgraded relationships back.
    edge_payload = [{k: v for k, v in e.items() if not k.startswith("_")} for e in upgraded_edges]
    upsert_records(EDGES_PATH, edge_payload, key="id")

    exp_payload = [{k: v for k, v in e.items() if not k.startswith("_")} for e in upgraded_exposures]
    upsert_records(EXPOSURES_PATH, exp_payload, key="id")

    # Build report.
    from collections import Counter
    all_upgraded = upgraded_edges + upgraded_exposures
    final_counts = dict(Counter(r["validation_status"] for r in all_upgraded))
    total = len(all_upgraded)

    report = {
        "total_relationships": total,
        "final_counts": final_counts,
        "edge_stats": edge_stats.to_dict(),
        "exposure_stats": exp_stats.to_dict(),
        "principle": "Never present a hypothesis as an established fact. Every relationship has an explicit validation status.",
    }
    write_json(REPORT_JSON, report, indent=2, sort_keys=True)
    log.info("Wrote JSON report to %s", REPORT_JSON)

    # Write Markdown report.
    md_lines = [
        "# InvestorLens Relationship Status Report",
        "",
        "## Summary",
        "",
        f"**Total relationships:** {total}",
        f"**VALIDATED:** {final_counts.get('validated', 0)}",
        f"**WEAKLY_SUPPORTED:** {final_counts.get('weakly_supported', 0)}",
        f"**HYPOTHESIZED:** {final_counts.get('hypothesized', 0)}",
        "",
        "## Upgrade statistics",
        "",
        "### Value-chain edges",
        f"- Total: {edge_stats.total}",
        f"- Upgraded to WEAKLY_SUPPORTED: {edge_stats.upgraded_to_weakly_supported}",
        f"- Upgraded to VALIDATED: {edge_stats.upgraded_to_validated}",
        f"- Unchanged: {edge_stats.unchanged}",
        f"- Final counts: {edge_stats.final_counts}",
        "",
        "### Exposures",
        f"- Total: {exp_stats.total}",
        f"- Upgraded to WEAKLY_SUPPORTED: {exp_stats.upgraded_to_weakly_supported}",
        f"- Upgraded to VALIDATED: {exp_stats.upgraded_to_validated}",
        f"- Unchanged: {exp_stats.unchanged}",
        f"- Final counts: {exp_stats.final_counts}",
        "",
        "## Status definitions",
        "",
        "| Status | Meaning |",
        "|--------|---------|",
        "| VALIDATED | Supported by empirical evidence (significant beta with correct direction, or 2+ correct shocks, or 2+ independent sources) |",
        "| WEAKLY_SUPPORTED | Some evidence exists but validation is incomplete |",
        "| HYPOTHESIZED | Economically plausible but not validated — no evidence |",
        "",
        "**Core principle: Never present a hypothesis as an established fact.**",
        "",
        "## Validation criteria",
        "",
        "A relationship is upgraded to VALIDATED when ANY of:",
        "- Rolling beta is statistically significant (p < 0.05) AND direction matches the model's prediction",
        "- 2+ historical shocks where the model predicted the correct direction",
        "- 2+ evidence records from independent source organisations",
        "",
        "A relationship is upgraded to WEAKLY_SUPPORTED when:",
        "- 1+ evidence records exist, OR",
        "- A rolling beta was computable (even if not significant)",
        "",
        "Never downgraded: VALIDATED and WEAKLY_SUPPORTED statuses are permanent.",
        "",
        "## Per-relationship details",
        "",
        "| ID | Type | Previous | New | Evidence | Beta | Sig. | Shocks | Direction Match |",
        "|----|------|----------|-----|----------|------|------|--------|-----------------|",
    ]

    for r in all_upgraded:
        meta = r.get("_validation_metadata", {})
        prev = meta.get("previous_status", "?")
        new = meta.get("new_status", "?")
        ev_count = meta.get("evidence_count", 0)
        has_beta = "Y" if meta.get("has_beta") else "N"
        sig = "Y" if meta.get("beta_significant") else "N"
        shocks = meta.get("shock_count", 0)
        dir_match = "Y" if meta.get("beta_direction_matches") else "N"
        rel_type = "edge" if "from_id" in r else "exposure"
        md_lines.append(
            f"| {r.get('id', '?')[:16]} | {rel_type} | {prev} | {new} | {ev_count} | {has_beta} | {sig} | {shocks} | {dir_match} |"
        )

    REPORT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    log.info("Wrote Markdown report to %s", REPORT_MD)

    # Print summary.
    print(f"\n{'='*70}")
    print(f"Relationship Status Report")
    print(f"{'='*70}")
    print(f"Total relationships: {total}")
    print(f"  VALIDATED:         {final_counts.get('validated', 0)}")
    print(f"  WEAKLY_SUPPORTED:  {final_counts.get('weakly_supported', 0)}")
    print(f"  HYPOTHESIZED:      {final_counts.get('hypothesized', 0)}")
    print(f"\nFull report: {REPORT_MD}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return run()


if __name__ == "__main__":
    sys.exit(main())
