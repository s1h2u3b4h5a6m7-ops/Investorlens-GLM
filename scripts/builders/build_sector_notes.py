"""
Build per-sector Markdown knowledge notes from priority sectors + value-chain data.

Reads:
  - data/master/priority_sectors.jsonl
  - data/processed/value_chain_edges.jsonl
  - data/master/raw_materials.jsonl
  - data/master/products.jsonl

Writes:
  - notes/sectors/<slug>.md  (one Markdown note per priority sector)

Idempotent: re-running with fixed --retrieved-at produces byte-identical output.

Usage:
    python scripts/builders/build_sector_notes.py
    python scripts/builders/build_sector_notes.py --retrieved-at 2024-09-30T18:30:00Z
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.builders import build_sector_note  # noqa: E402
from investorlens.io import read_jsonl  # noqa: E402
from investorlens.models import Provenance, ValueChainEdge  # noqa: E402

log = logging.getLogger("build_sector_notes")

PRIORITY_SECTORS_PATH = ROOT / "data" / "master" / "priority_sectors.jsonl"
VALUE_CHAIN_EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
PRODUCTS_PATH = ROOT / "data" / "master" / "products.jsonl"
NOTES_DIR = ROOT / "notes" / "sectors"


def _load_priority_sectors() -> list[dict]:
    if not PRIORITY_SECTORS_PATH.exists():
        log.warning("Priority sectors not found: %s", PRIORITY_SECTORS_PATH)
        return []
    records = read_jsonl(PRIORITY_SECTORS_PATH)
    log.info("Loaded %d priority sectors", len(records))
    return records


def _load_value_chain_edges() -> list[ValueChainEdge]:
    if not VALUE_CHAIN_EDGES_PATH.exists():
        log.warning("Value-chain edges not found: %s", VALUE_CHAIN_EDGES_PATH)
        return []
    raw = read_jsonl(VALUE_CHAIN_EDGES_PATH)
    out: list[ValueChainEdge] = []
    for i, row in enumerate(raw):
        try:
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown", notes=f"synthesized (edge row {i})"
                ).model_dump(mode="json")
            out.append(ValueChainEdge(**row))
        except Exception as e:
            log.debug("Skipped edge row %d: %s", i, e)
    log.info("Loaded %d value-chain edges", len(out))
    return out


def _load_raw_materials() -> list[dict]:
    if not RAW_MATERIALS_PATH.exists():
        return []
    return read_jsonl(RAW_MATERIALS_PATH)


def _load_products() -> list[dict]:
    if not PRODUCTS_PATH.exists():
        return []
    return read_jsonl(PRODUCTS_PATH)


def build(*, retrieved_at: datetime | None = None, notes_dir: Path | None = None) -> int:
    """Build sector notes and write them to notes/sectors/."""
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)
    notes_dir = notes_dir or NOTES_DIR

    sectors = _load_priority_sectors()
    edges = _load_value_chain_edges()
    raw_materials = _load_raw_materials()
    products = _load_products()

    if not sectors:
        log.error("No priority sectors found. Run scripts/seed_value_chain.py first.")
        return 0

    # Group edges by from_id (sector ID).
    edges_by_from: dict[str, list[ValueChainEdge]] = {}
    for e in edges:
        edges_by_from.setdefault(e.from_id, []).append(e)

    notes_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for sector in sectors:
        slug = sector.get("slug", sector.get("sector_name", "unknown").lower().replace(" ", "_"))
        sector_id = _sector_node_id(sector.get("sector_name", ""))
        sector_edges = edges_by_from.get(sector_id, [])

        note_md = build_sector_note(
            sector,
            sector_edges,
            raw_materials,
            products,
            last_updated=retrieved_at,
        )

        note_path = notes_dir / f"{slug}.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = note_path.with_suffix(".md.tmp")
        tmp.write_text(note_md, encoding="utf-8")
        tmp.replace(note_path)
        written += 1
        log.info("  wrote %s (%d edges)", note_path.name, len(sector_edges))

    log.info("Wrote %d sector notes to %s", written, notes_dir)
    return written


def _sector_node_id(sector_name: str) -> str:
    """Compute the sctr_ ID for a sector name (must match the graph builder)."""
    from investorlens.builders.graph import slugify_sector
    from investorlens.ids import make_id
    return make_id("sctr", {"name": slugify_sector(sector_name)})


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

    count = build(retrieved_at=retrieved_at)
    log.info("Done. Wrote %d notes.", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
