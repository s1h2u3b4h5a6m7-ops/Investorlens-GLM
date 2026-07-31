"""
Build per-company Markdown knowledge notes from structured data.

Reads:
  - data/master/isin_master.jsonl       (canonical company identity)
  - data/processed/observations.jsonl   (price/volume/turnover observations)
  - data/processed/corporate_actions.jsonl (corp actions per security)

Writes:
  - notes/companies/<slug>.md           (one Markdown note per company)

The notes are Dataview-compatible (YAML frontmatter with simple types) and
human-readable (sections for Business, Products, Customers, Suppliers, etc.).
Sections without underlying research data are emitted as empty placeholders
with a clear note that the data hasn't been researched yet.

Idempotent: re-running produces byte-identical output (with --retrieved-at
for a fixed timestamp).

Usage:
    python scripts/builders/build_company_notes.py
    python scripts/builders/build_company_notes.py --only-isins INE002A01018,INE467B01029
    python scripts/builders/build_company_notes.py --retrieved-at 2024-09-30T18:30:00Z
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

from investorlens.builders import build_company_note, slugify_company  # noqa: E402
from investorlens.ids import make_id  # noqa: E402
from investorlens.io import read_jsonl  # noqa: E402
from investorlens.models import CorporateAction, Observation, Provenance  # noqa: E402

log = logging.getLogger("build_company_notes")

ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
OBSERVATIONS_PATH = ROOT / "data" / "processed" / "observations.jsonl"
CORP_ACTIONS_PATH = ROOT / "data" / "processed" / "corporate_actions.jsonl"
VALUE_CHAIN_EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
RAW_MATERIALS_PATH = ROOT / "data" / "master" / "raw_materials.jsonl"
PRODUCTS_PATH = ROOT / "data" / "master" / "products.jsonl"
SUPPLIERS_PATH = ROOT / "data" / "master" / "suppliers.jsonl"
CUSTOMERS_PATH = ROOT / "data" / "master" / "customers.jsonl"
EXPOSURES_PATH = ROOT / "data" / "processed" / "exposures.jsonl"
NOTES_DIR = ROOT / "notes" / "companies"


def _load_isin_master() -> list[dict]:
    if not ISIN_MASTER_PATH.exists():
        log.warning("ISIN master not found: %s", ISIN_MASTER_PATH)
        return []
    records = read_jsonl(ISIN_MASTER_PATH)
    log.info("Loaded %d ISIN master records from %s", len(records), ISIN_MASTER_PATH.relative_to(ROOT))
    return records


def _load_observations() -> list[Observation]:
    if not OBSERVATIONS_PATH.exists():
        log.warning("Observations not found: %s", OBSERVATIONS_PATH)
        return []
    raw = read_jsonl(OBSERVATIONS_PATH)
    out: list[Observation] = []
    skipped = 0
    for i, row in enumerate(raw):
        try:
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown",
                    notes=f"synthesized during build (obs row {i})",
                ).model_dump(mode="json")
            out.append(Observation(**row))
        except Exception as e:
            skipped += 1
            log.debug("Skipped observation row %d: %s", i, e)
    if skipped:
        log.info("Skipped %d malformed observation rows.", skipped)
    log.info("Loaded %d observations from %s", len(out), OBSERVATIONS_PATH.relative_to(ROOT))
    return out


def _load_corp_actions() -> list[CorporateAction]:
    if not CORP_ACTIONS_PATH.exists():
        log.warning("Corporate actions not found: %s", CORP_ACTIONS_PATH)
        return []
    raw = read_jsonl(CORP_ACTIONS_PATH)
    out: list[CorporateAction] = []
    skipped = 0
    for i, row in enumerate(raw):
        try:
            if "provenance" not in row or not row.get("provenance"):
                row["provenance"] = Provenance(
                    source="unknown",
                    notes=f"synthesized during build (ca row {i})",
                ).model_dump(mode="json")
            out.append(CorporateAction(**row))
        except Exception as e:
            skipped += 1
            log.debug("Skipped corp action row %d: %s", i, e)
    if skipped:
        log.info("Skipped %d malformed corp action rows.", skipped)
    log.info("Loaded %d corporate actions from %s", len(out), CORP_ACTIONS_PATH.relative_to(ROOT))
    return out


def _index_observations_by_subject(observations: list[Observation]) -> dict[str, list[Observation]]:
    """Group observations by subject_id."""
    out: dict[str, list[Observation]] = {}
    for o in observations:
        out.setdefault(o.subject_id, []).append(o)
    return out


def _index_corp_actions_by_security(cas: list[CorporateAction]) -> dict[str, list[CorporateAction]]:
    """Group corp actions by security_id."""
    out: dict[str, list[CorporateAction]] = {}
    for ca in cas:
        out.setdefault(ca.security_id, []).append(ca)
    return out


def _write_note_atomic(path: Path, content: str) -> None:
    """Atomically write the note to disk (tmp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def build(
    *,
    only_isins: list[str] | None = None,
    retrieved_at: datetime | None = None,
    notes_dir: Path | None = None,
) -> int:
    """Build company notes and write them to notes/companies/.

    Args:
        only_isins: optional list of ISINs to filter to. If None, builds notes
            for all companies in the ISIN master.
        retrieved_at: UTC timestamp for the `last_updated` field. Defaults to
            now(). Pass a fixed value for byte-identical re-runs.
        notes_dir: override the notes directory (for testing). Defaults to
            ROOT / "notes" / "companies".

    Returns:
        Number of notes written.
    """
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    notes_dir = notes_dir or NOTES_DIR

    isin_master = _load_isin_master()
    observations = _load_observations()
    corp_actions = _load_corp_actions()

    # Load value-chain data (Phase 3).
    vc_edges_raw = read_jsonl(VALUE_CHAIN_EDGES_PATH) if VALUE_CHAIN_EDGES_PATH.exists() else []
    raw_materials = read_jsonl(RAW_MATERIALS_PATH) if RAW_MATERIALS_PATH.exists() else []
    products = read_jsonl(PRODUCTS_PATH) if PRODUCTS_PATH.exists() else []
    suppliers = read_jsonl(SUPPLIERS_PATH) if SUPPLIERS_PATH.exists() else []
    customers = read_jsonl(CUSTOMERS_PATH) if CUSTOMERS_PATH.exists() else []
    exposures_raw = read_jsonl(EXPOSURES_PATH) if EXPOSURES_PATH.exists() else []

    if not isin_master:
        log.error("No ISIN master records found. Run fetchers + build_isin_master first.")
        return 0

    # Filter to requested ISINs.
    if only_isins:
        only_set = {i.upper() for i in only_isins}
        isin_master = [r for r in isin_master if (r.get("isin") or "").upper() in only_set]
        log.info("Filtered to %d ISINs.", len(isin_master))

    # Index observations + corp actions + value-chain edges by subject/security ID.
    obs_by_subject = _index_observations_by_subject(observations)
    ca_by_security = _index_corp_actions_by_security(corp_actions)

    # Index value-chain edges by from_id.
    vc_by_from: dict[str, list[dict]] = {}
    for e in vc_edges_raw:
        fid = e.get("from_id")
        if fid:
            vc_by_from.setdefault(fid, []).append(e)

    # Index exposures by company_id.
    exp_by_company: dict[str, list[dict]] = {}
    for e in exposures_raw:
        cid = e.get("company_id")
        if cid:
            exp_by_company.setdefault(cid, []).append(e)

    # Build notes.
    notes_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    for company in isin_master:
        isin = company.get("isin")
        if not isin:
            skipped += 1
            continue

        # Compute the security_id (same formula as everywhere else).
        security_id = make_id("sec", {"isin": isin})
        company_obs = obs_by_subject.get(security_id, [])
        company_cas = ca_by_security.get(security_id, [])
        company_vc = vc_by_from.get(security_id, [])
        company_exp = exp_by_company.get(security_id, [])

        # Skip companies with no data at all.
        if not company_obs and not company_cas and not company_vc and not company_exp:
            log.debug("Skipping %s — no observations, corp actions, value-chain edges, or exposures.", isin)
            skipped += 1
            continue

        note_md = build_company_note(
            company,
            company_obs,
            company_cas,
            value_chain_edges=company_vc if company_vc else None,
            raw_materials=raw_materials if raw_materials else None,
            products=products if products else None,
            suppliers=suppliers if suppliers else None,
            customers=customers if customers else None,
            exposures=company_exp if company_exp else None,
            macro_drivers=None,
            last_updated=retrieved_at,
        )

        slug = slugify_company(
            company.get("company_name", ""),
            nse_symbol=company.get("nse_symbol"),
            isin=isin,
        )
        note_path = notes_dir / f"{slug}.md"
        _write_note_atomic(note_path, note_md)
        written += 1
        log.info("  wrote %s (%d obs, %d corp actions, %d vc edges)",
                 note_path.relative_to(ROOT) if note_path.is_relative_to(ROOT) else note_path,
                 len(company_obs), len(company_cas), len(company_vc))

    log.info("Wrote %d notes to %s (skipped %d companies with no data).",
             written, notes_dir.relative_to(ROOT) if notes_dir.is_relative_to(ROOT) else notes_dir, skipped)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only-isins",
        type=str,
        default=None,
        help="Comma-separated ISINs to filter to. Defaults to all companies in master.",
    )
    parser.add_argument(
        "--retrieved-at",
        type=str,
        default=None,
        help="ISO-8601 UTC timestamp for `last_updated`. Defaults to now().",
    )
    parser.add_argument(
        "--notes-dir",
        type=str,
        default=None,
        help="Override the notes directory (for testing).",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    only_isins = (
        [i.strip().upper() for i in args.only_isins.split(",") if i.strip()]
        if args.only_isins else None
    )
    retrieved_at = None
    if args.retrieved_at:
        retrieved_at = datetime.fromisoformat(args.retrieved_at)
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    notes_dir = Path(args.notes_dir) if args.notes_dir else None

    count = build(only_isins=only_isins, retrieved_at=retrieved_at, notes_dir=notes_dir)
    log.info("Done. Wrote %d notes.", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
