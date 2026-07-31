"""
Generate a Markdown summary of the InvestorLens pipeline results.

This script reads all processed JSONL files and emits a Markdown summary
suitable for the GitHub Actions "Job Summary" feature (written to
`$GITHUB_STEP_SUMMARY`). The summary includes:

  - Per-file record counts (observations, corporate_actions, isin_master, etc.)
  - Observation-kind breakdown (price_close, policy_rate, cpi_yoy, fx_rate, ...)
  - Source breakdown (nse, bse, yahoo, rbi, mospi, investorlens, ...)
  - Latest retrieval timestamps per source
  - Date coverage (earliest / latest as_of per kind)

Usage:
    python scripts/gh_actions_summary.py
    python scripts/gh_actions_summary.py --output /tmp/summary.md
    python scripts/gh_actions_summary.py --write-step-summary   # writes to $GITHUB_STEP_SUMMARY

The summary is also useful as a CLI diagnostic outside of GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import read_jsonl  # noqa: E402

log = logging.getLogger("gh_actions_summary")

# Files to summarize, in display order.
SUMMARY_FILES: list[tuple[str, str, str]] = [
    # (relative_path, display_name, description)
    ("data/master/isin_master.jsonl",         "ISIN Master",            "Canonical security identity"),
    ("data/master/nse_equities.jsonl",        "NSE Equities",           "Per-source input for ISIN master"),
    ("data/master/bse_scrips.jsonl",          "BSE Scrips",             "Per-source input for ISIN master"),
    ("data/processed/observations.jsonl",     "Observations",           "All atomic facts (prices, rates, FX, CPI)"),
    ("data/processed/corporate_actions.jsonl", "Corporate Actions",     "Splits, bonuses, dividends, mergers, ..."),
]


def _count_records(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in read_jsonl(path))


def _count_by_field(path: Path, field: str) -> Counter:
    """Return a Counter of values for `field` across all records in `path`."""
    out: Counter = Counter()
    if not path.exists():
        return out
    for r in read_jsonl(path):
        v = r.get(field)
        if v is not None:
            out[str(v)] += 1
    return out


def _latest_retrieved_at(path: Path) -> str | None:
    """Return the maximum retrieved_at across all records (ISO string)."""
    if not path.exists():
        return None
    latest: str | None = None
    for r in read_jsonl(path):
        prov = r.get("provenance") or {}
        ts = prov.get("retrieved_at")
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


def _date_coverage(path: Path) -> dict[str, tuple[str, str]]:
    """For observations.jsonl, return {kind: (earliest_as_of, latest_as_of)}."""
    if not path.exists() or path.name != "observations.jsonl":
        return {}
    by_kind: dict[str, list[str]] = defaultdict(list)
    for r in read_jsonl(path):
        kind = r.get("kind")
        as_of = r.get("as_of")
        if kind and as_of:
            by_kind[kind].append(as_of)
    return {k: (min(v), max(v)) for k, v in by_kind.items() if v}


def generate_summary() -> str:
    """Generate the Markdown summary as a string."""
    lines: list[str] = []
    lines.append("# InvestorLens Pipeline Summary")
    lines.append("")
    lines.append(f"Generated: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`")
    lines.append("")

    # ─── File counts table ────────────────────────────────────────────────
    lines.append("## File counts")
    lines.append("")
    lines.append("| File | Records | Description |")
    lines.append("|------|--------:|-------------|")
    for rel, name, desc in SUMMARY_FILES:
        path = ROOT / rel
        n = _count_records(path)
        lines.append(f"| `{rel}` | {n:,} | {desc} |")
    lines.append("")

    # ─── ISIN master breakdown by exchange ────────────────────────────────
    isin_path = ROOT / "data/master/isin_master.jsonl"
    if isin_path.exists():
        by_exchange = _count_by_field(isin_path, "exchange")
        if by_exchange:
            lines.append("### ISIN Master by exchange")
            lines.append("")
            lines.append("| Exchange | Count |")
            lines.append("|----------|------:|")
            for exch in sorted(by_exchange):
                lines.append(f"| {exch} | {by_exchange[exch]:,} |")
            lines.append("")

    # ─── Observations breakdown ───────────────────────────────────────────
    obs_path = ROOT / "data/processed/observations.jsonl"
    if obs_path.exists():
        by_kind = _count_by_field(obs_path, "kind")
        by_source = _count_by_field(obs_path, "provenance.source")
        # provenance is nested — need a custom counter.
        nested_sources: Counter = Counter()
        for r in read_jsonl(obs_path):
            prov = r.get("provenance") or {}
            src = prov.get("source")
            if src:
                nested_sources[src] += 1
        coverage = _date_coverage(obs_path)

        if by_kind:
            lines.append("### Observations by kind")
            lines.append("")
            lines.append("| Kind | Count | Earliest | Latest |")
            lines.append("|------|------:|----------|--------|")
            for kind in sorted(by_kind):
                count = by_kind[kind]
                earliest, latest = coverage.get(kind, ("", ""))
                lines.append(f"| `{kind}` | {count:,} | {earliest} | {latest} |")
            lines.append("")

        if nested_sources:
            lines.append("### Observations by source")
            lines.append("")
            lines.append("| Source | Count |")
            lines.append("|--------|------:|")
            for src in sorted(nested_sources):
                lines.append(f"| `{src}` | {nested_sources[src]:,} |")
            lines.append("")

    # ─── Corporate actions breakdown ──────────────────────────────────────
    ca_path = ROOT / "data/processed/corporate_actions.jsonl"
    if ca_path.exists():
        by_type = _count_by_field(ca_path, "action_type")
        if by_type:
            lines.append("### Corporate Actions by type")
            lines.append("")
            lines.append("| Type | Count |")
            lines.append("|------|------:|")
            for t in sorted(by_type):
                lines.append(f"| `{t}` | {by_type[t]:,} |")
            lines.append("")

    # ─── Latest retrieval timestamps ──────────────────────────────────────
    lines.append("### Latest retrieval timestamps")
    lines.append("")
    lines.append("| File | Last retrieved_at |")
    lines.append("|------|-------------------|")
    for rel, name, _ in SUMMARY_FILES:
        path = ROOT / rel
        ts = _latest_retrieved_at(path)
        lines.append(f"| `{rel}` | {ts or '(none)'} |")
    lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the summary script.

    Args:
        argv: optional argument list (for testing). If None, uses sys.argv.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write summary to this file. Defaults to stdout.",
    )
    parser.add_argument(
        "--write-step-summary",
        action="store_true",
        help="Append summary to $GITHUB_STEP_SUMMARY (for GitHub Actions UI).",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    summary = generate_summary()

    if args.output:
        Path(args.output).write_text(summary, encoding="utf-8")
        log.info("Wrote summary to %s", args.output)
    else:
        print(summary, end="")

    if args.write_step_summary:
        step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary_path:
            with open(step_summary_path, "a", encoding="utf-8") as f:
                f.write(summary)
            log.info("Appended summary to $GITHUB_STEP_SUMMARY (%s)", step_summary_path)
        else:
            log.warning("--write-step-summary given but $GITHUB_STEP_SUMMARY is not set; ignoring.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
