"""
Build the Drivers × Companies exposure matrix.

Reads:
  - data/processed/exposures.jsonl
  - data/research/evidence.jsonl
  - data/master/raw_materials.jsonl (for driver labels)
  - data/master/isin_master.jsonl (for company labels)

Writes:
  - data/processed/exposure_matrix.json (machine-readable, full decomposition)
  - data/processed/exposure_matrix.md (human-readable Markdown table)

Every populated cell in the matrix is fully decomposable:
  Driver → Exposure(direction, transmission, pricing_power, hedge, lag,
  magnitude, metric) → Evidence(source, page, fact) → Validation status

No black-box scores.

Usage:
    python scripts/builders/build_exposure_matrix.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.algorithms.exposure_matrix import build_exposure_matrix  # noqa: E402
from investorlens.io import read_jsonl, write_json  # noqa: E402

log = logging.getLogger("build_exposure_matrix")

EXPOSURES_PATH = ROOT / "data" / "processed" / "exposures.jsonl"
EVIDENCE_PATH = ROOT / "data" / "research" / "evidence.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
JSON_OUTPUT = ROOT / "data" / "processed" / "exposure_matrix.json"
MD_OUTPUT = ROOT / "data" / "processed" / "exposure_matrix.md"


def _build_driver_labels() -> dict[str, str]:
    """Build a lookup from driver_id → human-readable label."""
    labels: dict[str, str] = {}
    # Raw materials
    if RAW_MATERIALS_PATH.exists():
        for rm in read_jsonl(RAW_MATERIALS_PATH):
            labels[rm.get("id", "")] = rm.get("name", rm.get("id", ""))
    # Known macro driver slugs → labels
    from investorlens.builders.graph import _MACRO_DRIVER_INFO
    from investorlens.ids import make_id
    for slug, info in _MACRO_DRIVER_INFO.items():
        drv_id = make_id("drv", {"slug": slug})
        labels[drv_id] = info["label"]
    return labels


def _build_company_labels() -> dict[str, str]:
    """Build a lookup from company_id (sec_*) → human-readable label."""
    labels: dict[str, str] = {}
    if ISIN_MASTER_PATH.exists():
        from investorlens.ids import make_id
        for c in read_jsonl(ISIN_MASTER_PATH):
            isin = c.get("isin", "")
            if isin:
                sec_id = make_id("sec", {"isin": isin})
                label = c.get("nse_symbol") or c.get("company_name") or isin
                labels[sec_id] = label
    return labels


def build() -> int:
    """Build the exposure matrix and write JSON + Markdown outputs."""
    if not EXPOSURES_PATH.exists():
        log.error("Exposures not found: %s", EXPOSURES_PATH)
        return 1

    exposures = read_jsonl(EXPOSURES_PATH)
    evidence = read_jsonl(EVIDENCE_PATH) if EVIDENCE_PATH.exists() else []
    driver_labels = _build_driver_labels()
    company_labels = _build_company_labels()

    log.info("Loaded %d exposures, %d evidence records", len(exposures), len(evidence))

    matrix = build_exposure_matrix(
        exposures, evidence,
        driver_labels=driver_labels,
        company_labels=company_labels,
    )

    log.info("Matrix: %d drivers × %d companies = %d cells (%d populated, %.1f%% fill rate)",
             matrix.n_drivers, matrix.n_companies, matrix.n_total,
             matrix.n_populated,
             matrix.n_populated / matrix.n_total * 100 if matrix.n_total > 0 else 0)

    # Write JSON output.
    write_json(JSON_OUTPUT, matrix.to_dict(), indent=2, sort_keys=True)
    log.info("Wrote JSON to %s", JSON_OUTPUT)

    # Write Markdown output.
    md_lines = [
        "# InvestorLens Exposure Matrix",
        "",
        f"**Size:** {matrix.n_drivers} drivers × {matrix.n_companies} companies = {matrix.n_total} cells",
        f"**Populated:** {matrix.n_populated} / {matrix.n_total}"
        + (f" ({matrix.n_populated / matrix.n_total * 100:.1f}% fill rate)" if matrix.n_total > 0 else ""),
        "",
        "Every populated cell is fully decomposable into an evidence chain:",
        "Driver → Exposure(direction, transmission, pricing_power, hedge, lag, magnitude, metric) → Evidence → Validation",
        "",
        "No black-box scores.",
        "",
        "## Matrix",
        "",
        matrix.to_markdown(),
        "",
        "## Cell decompositions",
        "",
    ]

    # Add decomposition for each populated cell.
    for drv_id, drv_label, _ in matrix.drivers:
        for cmp_id, cmp_label in matrix.companies:
            cell = matrix.get_cell(drv_id, cmp_id)
            if not cell.is_empty:
                md_lines.append(f"### {drv_label} → {cmp_label}")
                md_lines.append("")
                md_lines.append("```")
                md_lines.append(cell.decomposition())
                md_lines.append("```")
                md_lines.append("")

    MD_OUTPUT.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    log.info("Wrote Markdown to %s", MD_OUTPUT)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return build()


if __name__ == "__main__":
    sys.exit(main())
