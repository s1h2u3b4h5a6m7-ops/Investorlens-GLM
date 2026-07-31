"""
Build transparent Driver -> Company impact scores.

Reads:
  - data/processed/exposures.jsonl
  - data/master/raw_materials.jsonl (for driver labels)
  - data/master/isin_master.jsonl (for company labels)

Writes:
  - data/processed/impact_scores.json (machine-readable, full decomposition per score)
  - data/processed/impact_scores.md (human-readable, ranked scores + decompositions)

Scoring formula (fully transparent):
  Score = driver_change x magnitude x direction x pricing_power x hedge x validation

Every score has a human-readable decomposition showing each factor.

Usage:
    python scripts/builders/build_scores.py                          # default: +10% shock
    python scripts/builders/build_scores.py --driver-change 0.05      # +5% shock
    python scripts/builders/build_scores.py --driver-change -0.10     # -10% shock
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.algorithms.scoring import score_all_exposures  # noqa: E402
from investorlens.io import read_jsonl, write_json  # noqa: E402

log = logging.getLogger("build_scores")

EXPOSURES_PATH = ROOT / "data" / "processed" / "exposures.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
JSON_OUTPUT = ROOT / "data" / "processed" / "impact_scores.json"
MD_OUTPUT = ROOT / "data" / "processed" / "impact_scores.md"


def _build_driver_labels():
    labels = {}
    if RAW_MATERIALS_PATH.exists():
        for rm in read_jsonl(RAW_MATERIALS_PATH):
            labels[rm.get("id", "")] = rm.get("name", rm.get("id", ""))
    from investorlens.builders.graph import _MACRO_DRIVER_INFO
    from investorlens.ids import make_id
    for slug, info in _MACRO_DRIVER_INFO.items():
        drv_id = make_id("drv", {"slug": slug})
        labels[drv_id] = info["label"]
    return labels


def _build_company_labels():
    labels = {}
    if ISIN_MASTER_PATH.exists():
        from investorlens.ids import make_id
        for c in read_jsonl(ISIN_MASTER_PATH):
            isin = c.get("isin", "")
            if isin:
                sec_id = make_id("sec", {"isin": isin})
                labels[sec_id] = c.get("nse_symbol") or c.get("company_name") or isin
    return labels


def build(driver_change=0.10):
    """Score all exposures and write JSON + Markdown outputs."""
    if not EXPOSURES_PATH.exists():
        log.error("Exposures not found: %s", EXPOSURES_PATH)
        return 1

    exposures = read_jsonl(EXPOSURES_PATH)
    driver_labels = _build_driver_labels()
    company_labels = _build_company_labels()
    log.info("Loaded %d exposures", len(exposures))

    results = score_all_exposures(
        exposures, driver_change,
        driver_labels=driver_labels,
        company_labels=company_labels,
    )

    log.info("Scored %d exposures with driver change %+.1f%%", len(results), driver_change * 100)

    # Write JSON.
    write_json(JSON_OUTPUT, {
        "driver_change": driver_change,
        "score_count": len(results),
        "scores": [r.to_dict() for r in results],
    }, indent=2, sort_keys=True)
    log.info("Wrote JSON to %s", JSON_OUTPUT)

    # Write Markdown.
    md_lines = [
        "# InvestorLens Impact Scores",
        "",
        f"**Driver change:** {driver_change:+.1f}%",
        f"**Scores computed:** {len(results)}",
        "",
        "## Scoring formula (fully transparent)",
        "",
        "```",
        "Score = driver_change * magnitude_percent * direction_factor",
        "        * pricing_power_factor * hedge_factor * validation_factor",
        "```",
        "",
        "| Factor | Values |",
        "|--------|--------|",
        "| direction | positive=+1.0, negative=-1.0, mixed=0.0, neutral=0.0 |",
        "| pricing_power | high=0.3, medium=0.6, low=0.9, none=1.0 |",
        "| hedge | fully_hedged=0.1, partially_hedged=0.5, unhedged=1.0 |",
        "| validation | validated=1.0, weakly_supported=0.7, hypothesized=0.4 |",
        "",
        "**Every score is fully decomposable. No black-box.**",
        "",
        "## Ranked scores",
        "",
        "| Rank | Driver | Company | Score | Direction | Magnitude | Pricing | Hedge | Validation | Metric |",
        "|------|--------|---------|------:|-----------|-----------|---------|-------|------------|--------|",
    ]

    for i, r in enumerate(results, 1):
        mag = f"{r.magnitude_percent:.1f}%" if r.magnitude_percent is not None else "---"
        md_lines.append(
            f"| {i} | {r.driver_label[:20]} | {r.company_label[:15]} | {r.score:+.6f} | "
            f"{r.direction} | {mag} | {r.pricing_power} | {r.hedge_status} | "
            f"{r.validation_status} | {r.financial_metric} |"
        )

    md_lines.append("")
    md_lines.append("## Score decompositions")
    md_lines.append("")

    for r in results:
        md_lines.append(f"### {r.driver_label} -> {r.company_label}")
        md_lines.append("")
        md_lines.append("```")
        md_lines.append(r.decomposition())
        md_lines.append("```")
        md_lines.append("")

    MD_OUTPUT.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    log.info("Wrote Markdown to %s", MD_OUTPUT)

    # Print summary.
    print(f"\n{'='*70}")
    print(f"Impact Scores (driver change: {driver_change:+.1f}%)")
    print(f"{'='*70}")
    print(f"{'Driver':<25s} {'Company':<15s} {'Score':>10s} {'Direction':>10s}")
    print(f"{'-'*25} {'-'*15} {'-'*10} {'-'*10}")
    for r in results[:15]:
        print(f"{r.driver_label[:25]:<25s} {r.company_label[:15]:<15s} {r.score:>10.6f} {r.direction:>10s}")
    if len(results) > 15:
        print(f"  ... and {len(results) - 15} more")
    print(f"\nFull decompositions: {MD_OUTPUT}")

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver-change", type=float, default=0.10,
                        help="Driver change magnitude (default: 0.10 = +10%%)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return build(driver_change=args.driver_change)


if __name__ == "__main__":
    sys.exit(main())
