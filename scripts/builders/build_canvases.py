"""
Build Obsidian Canvas files from the ISIN master.

Reads:
  - data/master/isin_master.jsonl       (canonical company identity, grouped by sector)

Writes:
  - notes/canvases/sectors/<slug>.canvas  (one per sector with ≥1 company)
  - notes/canvases/index.canvas           (top-level index linking all sector canvases)

Each sector canvas has ≤80 nodes (the ROADMAP limit for Obsidian Canvas
readability). Sectors with >80 companies are truncated with a note pointing
to the web graph (Phase 2.3).

Idempotent: re-running produces byte-identical output (with --retrieved-at
for a fixed timestamp — though canvases don't carry timestamps, the JSON
key ordering is deterministic).

Usage:
    python scripts/builders/build_canvases.py
    python scripts/builders/build_canvases.py --log-level DEBUG
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.builders import build_index_canvas, build_sector_canvas  # noqa: E402
from investorlens.io import read_jsonl, write_json  # noqa: E402

log = logging.getLogger("build_canvases")

ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
CANVASES_DIR = ROOT / "notes" / "canvases"
SECTORS_DIR = CANVASES_DIR / "sectors"


def _slugify_sector(name: str) -> str:
    """Convert a sector name to a URL-safe slug for the canvas filename."""
    s = name.lower().strip()
    s = s.replace(" ", "_").replace("/", "_").replace("&", "and")
    s = "".join(c for c in s if c.isalnum() or c == "_")
    return s or "unknown"


def _write_canvas_atomic(path: Path, canvas_dict: dict) -> None:
    """Atomically write the canvas dict as JSON to `path`.

    Uses sorted keys for deterministic output (byte-identical across runs).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, canvas_dict, indent=2, sort_keys=True)


def _group_companies_by_sector(companies: list[dict]) -> dict[str, list[dict]]:
    """Group ISIN master records by their `sector` field.

    Companies with no sector are grouped under "(Unclassified)".
    """
    groups: dict[str, list[dict]] = {}
    for c in companies:
        sector = c.get("sector") or "(Unclassified)"
        groups.setdefault(sector, []).append(c)
    return groups


def build() -> int:
    """Build all sector canvases + the index canvas.

    Returns the number of canvas files written.
    """
    if not ISIN_MASTER_PATH.exists():
        log.error("ISIN master not found: %s", ISIN_MASTER_PATH)
        return 0

    isin_master = read_jsonl(ISIN_MASTER_PATH)
    log.info("Loaded %d ISIN master records.", len(isin_master))

    if not isin_master:
        log.error("ISIN master is empty.")
        return 0

    # Group by sector.
    by_sector = _group_companies_by_sector(isin_master)
    log.info("Found %d sectors.", len(by_sector))

    # Build sector canvases.
    SECTORS_DIR.mkdir(parents=True, exist_ok=True)
    sector_canvas_paths: dict[str, str] = {}
    canvases_written = 0

    for sector_name, companies in sorted(by_sector.items()):
        if not companies:
            continue

        slug = _slugify_sector(sector_name)
        canvas_path = SECTORS_DIR / f"{slug}.canvas"
        vault_rel_path = f"notes/canvases/sectors/{slug}.canvas"

        canvas_dict = build_sector_canvas(sector_name, companies)
        _write_canvas_atomic(canvas_path, canvas_dict)
        sector_canvas_paths[sector_name] = vault_rel_path
        canvases_written += 1

        truncation = len(companies) > 80
        log.info(
            "  wrote %s (%d companies%s)",
            canvas_path.relative_to(ROOT) if canvas_path.is_relative_to(ROOT) else canvas_path,
            len(companies),
            " — TRUNCATED to 80" if truncation else "",
        )

    # Build the index canvas.
    sectors_for_index = [(name, cos) for name, cos in sorted(by_sector.items()) if cos]
    index_dict = build_index_canvas(sectors_for_index, sector_canvas_paths=sector_canvas_paths)
    index_path = CANVASES_DIR / "index.canvas"
    _write_canvas_atomic(index_path, index_dict)
    canvases_written += 1
    log.info(
        "  wrote %s (%d sectors)",
        index_path.relative_to(ROOT) if index_path.is_relative_to(ROOT) else index_path,
        len(sectors_for_index),
    )

    log.info("Wrote %d canvas files to %s.", canvases_written, CANVASES_DIR.relative_to(ROOT))
    return canvases_written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    count = build()
    log.info("Done. Wrote %d canvas files.", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
