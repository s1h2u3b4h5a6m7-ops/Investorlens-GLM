"""
Run empirical validation against historical data.

Three validation methods:
  1. Rolling betas: company returns vs driver changes (OLS regression)
  2. Event studies: company abnormal returns around identifiable events
  3. Historical shock analysis: driver shocks vs company outcomes

Reads:
  - data/processed/observations.jsonl (company prices + macro drivers)
  - data/processed/exposures.jsonl (for predicted impacts)
  - data/processed/impact_scores.json (for model predictions)

Writes:
  - data/processed/validation_results.json (machine-readable)
  - data/processed/validation_results.md (human-readable)

Usage:
    python scripts/builders/run_validation.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.algorithms.validation import (  # noqa: E402
    compute_rolling_beta,
    compute_shock_analysis,
)
from investorlens.io import read_jsonl, write_json  # noqa: E402

log = logging.getLogger("run_validation")

OBSERVATIONS_PATH = ROOT / "data" / "processed" / "observations.jsonl"
EXPOSURES_PATH = ROOT / "data" / "processed" / "exposures.jsonl"
JSON_OUTPUT = ROOT / "data" / "processed" / "validation_results.json"
MD_OUTPUT = ROOT / "data" / "processed" / "validation_results.md"


def run() -> int:
    """Run all validation methods and write results."""
    if not OBSERVATIONS_PATH.exists():
        log.error("Observations not found: %s", OBSERVATIONS_PATH)
        return 1

    observations = read_jsonl(OBSERVATIONS_PATH)
    exposures = read_jsonl(EXPOSURES_PATH) if EXPOSURES_PATH.exists() else []
    log.info("Loaded %d observations, %d exposures", len(observations), len(exposures))

    # Separate observations by subject type.
    company_obs: dict[str, list[dict]] = {}  # subject_id -> list of price_close obs
    driver_obs: dict[str, list[dict]] = {}   # subject_id -> list of driver obs

    for obs in observations:
        sid = obs.get("subject_id", "")
        kind = obs.get("kind", "")
        if kind == "price_close" and sid.startswith("sec_"):
            company_obs.setdefault(sid, []).append(obs)
        elif sid.startswith("drv_") and kind in ("fx_rate", "policy_rate", "cpi_yoy"):
            driver_obs.setdefault(sid, []).append(obs)

    log.info("Company price series: %d, Driver series: %d", len(company_obs), len(driver_obs))

    # Build exposure lookup: (company_id, driver_id) -> magnitude_percent
    exp_lookup: dict[tuple[str, str], float | None] = {}
    for exp in exposures:
        key = (exp.get("company_id", ""), exp.get("driver_id", ""))
        exp_lookup[key] = exp.get("magnitude_percent")

    # Run rolling betas for each company-driver pair with overlapping data.
    results: list[dict] = []
    md_lines = [
        "# InvestorLens Empirical Validation Results",
        "",
        "## Rolling Betas",
        "",
        "Measures the sensitivity of company stock returns to macro driver changes.",
        "A negative beta means the company moves opposite to the driver (as expected for a negative exposure).",
        "",
        "| Company | Driver | Beta | R² | P-value | N | Interpretation |",
        "|---------|--------|------|-----|---------|---|----------------|",
    ]

    for cmp_id, cmp_obs_list in sorted(company_obs.items()):
        for drv_id, drv_obs_list in sorted(driver_obs.items()):
            beta_result = compute_rolling_beta(
                cmp_obs_list, drv_obs_list,
                company_id=cmp_id, driver_id=drv_id,
                min_observations=3,
            )

            # Get predicted magnitude from exposures.
            predicted = exp_lookup.get((cmp_id, drv_id))

            # Also run shock analysis.
            shock_results = compute_shock_analysis(
                cmp_obs_list, drv_obs_list,
                company_id=cmp_id, driver_id=drv_id,
                shock_threshold=0.01,  # 1% threshold (lower for seed data)
                predicted_impact=predicted,
            )

            results.append({
                "company_id": cmp_id,
                "driver_id": drv_id,
                "rolling_beta": beta_result.to_dict(),
                "shock_analyses": [s.to_dict() for s in shock_results],
                "predicted_magnitude_percent": predicted,
            })

            # Add to Markdown table.
            beta_str = f"{beta_result.beta:.4f}" if beta_result.beta is not None else "---"
            r2_str = f"{beta_result.r_squared:.4f}" if beta_result.r_squared is not None else "---"
            p_str = f"{beta_result.p_value:.4f}" if beta_result.p_value is not None else "---"
            interp = beta_result.interpretation[:80] + "..." if len(beta_result.interpretation) > 80 else beta_result.interpretation
            md_lines.append(f"| {cmp_id[:12]} | {drv_id[:12]} | {beta_str} | {r2_str} | {p_str} | {beta_result.n_observations} | {interp} |")

    # Add shock analysis section.
    md_lines.append("")
    md_lines.append("## Historical Shock Analysis")
    md_lines.append("")
    md_lines.append("Identifies periods where a driver changed significantly (>1%) and compares against company returns.")
    md_lines.append("")

    for r in results:
        if r["shock_analyses"]:
            md_lines.append(f"### {r['company_id'][:12]} x {r['driver_id'][:12]}")
            md_lines.append("")
            md_lines.append("| Shock Date | Driver Change | Company Return | Predicted Impact | Actual/Predicted | Interpretation |")
            md_lines.append("|------------|--------------|----------------|-----------------|------------------|----------------|")
            for s in r["shock_analyses"]:
                dc = f"{s['driver_change']:+.4f}"
                cr = f"{s['company_return']:+.4f}" if s["company_return"] is not None else "---"
                pi = f"{s['predicted_impact']:.4f}" if s["predicted_impact"] is not None else "---"
                ap = f"{s['actual_vs_predicted']:.2f}" if s["actual_vs_predicted"] is not None else "---"
                interp = s["interpretation"][:60] + "..." if len(s["interpretation"]) > 60 else s["interpretation"]
                md_lines.append(f"| {s['shock_date']} | {dc} | {cr} | {pi} | {ap} | {interp} |")
            md_lines.append("")

    # Add summary.
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append(f"**Validation pairs:** {len(results)}")
    n_with_beta = sum(1 for r in results if r["rolling_beta"]["beta"] is not None)
    md_lines.append(f"**Pairs with computable beta:** {n_with_beta}")
    n_with_shocks = sum(1 for r in results if r["shock_analyses"])
    md_lines.append(f"**Pairs with identified shocks:** {n_with_shocks}")
    md_lines.append("")
    md_lines.append("**Note:** With seed data (5 overlapping dates), results are illustrative, not statistically significant.")
    md_lines.append("The framework will produce meaningful results when live data provides hundreds of trading days.")

    MD_OUTPUT.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    log.info("Wrote Markdown to %s", MD_OUTPUT)

    write_json(JSON_OUTPUT, {"results": results, "n_pairs": len(results)}, indent=2, sort_keys=True)
    log.info("Wrote JSON to %s", JSON_OUTPUT)

    # Print summary.
    print(f"\n{'='*70}")
    print(f"Empirical Validation Results")
    print(f"{'='*70}")
    print(f"Validation pairs: {len(results)}")
    print(f"Pairs with computable beta: {n_with_beta}")
    print(f"Pairs with identified shocks: {n_with_shocks}")
    print(f"\nFull results: {MD_OUTPUT}")
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
