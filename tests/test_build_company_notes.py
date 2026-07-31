"""Integration tests for the build_company_notes.py script.

Strategy: build a small fixture dataset (ISIN master + observations + corp
actions) in a tmp directory, then run the build script with that directory
as the data root. Verify the produced Markdown files have the expected
structure.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from investorlens.io import read_jsonl, write_jsonl  # noqa: E402

# Import the build script by path
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "build_company_notes", ROOT / "scripts" / "builders" / "build_company_notes.py"
)
assert _spec is not None and _spec.loader is not None
build_company_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_company_notes)


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def fake_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a small fake data workspace in a tmp directory.

    Creates:
      - data/master/isin_master.jsonl with 2 companies (RELIANCE + SUNPHARMA)
      - data/processed/observations.jsonl with RELIANCE prices + macro observations
      - data/processed/corporate_actions.jsonl with a RELIANCE dividend

    Patches the build script's path constants to point at the tmp dir.
    """
    from investorlens.ids import make_id

    data_dir = tmp_path / "data"
    master_dir = data_dir / "master"
    processed_dir = data_dir / "processed"
    notes_dir = tmp_path / "notes" / "companies"
    master_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)

    # ISIN master
    isin_records = [
        {
            "id": make_id("isin", {"isin": "INE002A01018"}),
            "isin": "INE002A01018",
            "nse_symbol": "RELIANCE",
            "bse_code": "500325",
            "company_name": "Reliance Industries Limited",
            "exchange": "NSE+BSE",
            "active": True,
            "security_type": "equity",
            "face_value": "10.00",
            "effective_from": "1995-01-11",
            "provenance": {"source": "nse+bse", "retrieved_at": "2024-09-30T18:30:00Z"},
        },
        {
            "id": make_id("isin", {"isin": "INE044A01026"}),
            "isin": "INE044A01026",
            "nse_symbol": "SUNPHARMA",
            "bse_code": "524715",
            "company_name": "Sun Pharmaceutical Industries Limited",
            "exchange": "NSE+BSE",
            "active": True,
            "security_type": "equity",
            "face_value": "1.00",
            "effective_from": "1994-10-10",
            "provenance": {"source": "nse+bse", "retrieved_at": "2024-09-30T18:30:00Z"},
        },
    ]
    write_jsonl(master_dir / "isin_master.jsonl", isin_records)

    # Observations: RELIANCE close prices + a macro observation (to ensure
    # macro observations don't appear in company notes).
    reliance_sid = make_id("sec", {"isin": "INE002A01018"})
    sunpharma_sid = make_id("sec", {"isin": "INE044A01026"})
    usd_sid = make_id("drv", {"slug": "fx_usd_inr"})

    obs_records = [
        {
            "id": make_id("obs", {"subject_id": reliance_sid, "kind": "price_close",
                                   "period": "2024-09-30", "as_of": "2024-09-30", "source_id": "nse"}),
            "subject_id": reliance_sid,
            "kind": "price_close",
            "period": "2024-09-30",
            "as_of": "2024-09-30",
            "value": 2750.0,
            "unit": "INR/share",
            "currency": "INR",
            "data_status": "observed",
            "confidence": "high",
            "provenance": {"source": "nse", "extraction_method": "bulk_download",
                           "retrieved_at": "2024-09-30T18:30:00Z"},
        },
        {
            "id": make_id("obs", {"subject_id": reliance_sid, "kind": "volume",
                                   "period": "2024-09-30", "as_of": "2024-09-30", "source_id": "nse"}),
            "subject_id": reliance_sid,
            "kind": "volume",
            "period": "2024-09-30",
            "as_of": "2024-09-30",
            "value": 1000000,
            "unit": "shares",
            "data_status": "observed",
            "confidence": "high",
            "provenance": {"source": "nse", "extraction_method": "bulk_download",
                           "retrieved_at": "2024-09-30T18:30:00Z"},
        },
        # Macro observation — should NOT appear in any company note.
        {
            "id": make_id("obs", {"subject_id": usd_sid, "kind": "fx_rate",
                                   "period": "2024-09-30", "as_of": "2024-09-30", "source_id": "rbi"}),
            "subject_id": usd_sid,
            "kind": "fx_rate",
            "period": "2024-09-30",
            "as_of": "2024-09-30",
            "value": 84.05,
            "unit": "INR/USD",
            "currency": "INR",
            "data_status": "observed",
            "confidence": "high",
            "provenance": {"source": "rbi", "extraction_method": "html_scrape",
                           "retrieved_at": "2024-09-30T18:30:00Z"},
        },
    ]
    write_jsonl(processed_dir / "observations.jsonl", obs_records)

    # Corporate actions: RELIANCE dividend
    ca_records = [
        {
            "id": make_id("ca", {"security_id": reliance_sid, "action_type": "dividend", "ex_date": "2024-09-10"}),
            "security_id": reliance_sid,
            "action_type": "dividend",
            "ex_date": "2024-09-10",
            "amount_per_share": "7",
            "provenance": {"source": "nse", "extraction_method": "bulk_download",
                           "retrieved_at": "2024-09-30T18:30:00Z"},
        },
    ]
    write_jsonl(processed_dir / "corporate_actions.jsonl", ca_records)

    # Patch the script's path constants.
    monkeypatch.setattr(build_company_notes, "ISIN_MASTER_PATH", master_dir / "isin_master.jsonl")
    monkeypatch.setattr(build_company_notes, "OBSERVATIONS_PATH", processed_dir / "observations.jsonl")
    monkeypatch.setattr(build_company_notes, "CORP_ACTIONS_PATH", processed_dir / "corporate_actions.jsonl")
    monkeypatch.setattr(build_company_notes, "VALUE_CHAIN_EDGES_PATH", tmp_path / "nonexistent_vc.jsonl")
    monkeypatch.setattr(build_company_notes, "RAW_MATERIALS_PATH", tmp_path / "nonexistent_rm.jsonl")
    monkeypatch.setattr(build_company_notes, "PRODUCTS_PATH", tmp_path / "nonexistent_prod.jsonl")
    monkeypatch.setattr(build_company_notes, "SUPPLIERS_PATH", tmp_path / "nonexistent_sup.jsonl")
    monkeypatch.setattr(build_company_notes, "CUSTOMERS_PATH", tmp_path / "nonexistent_cust.jsonl")
    monkeypatch.setattr(build_company_notes, "EXPOSURES_PATH", tmp_path / "nonexistent_exp.jsonl")
    monkeypatch.setattr(build_company_notes, "NOTES_DIR", notes_dir)
    monkeypatch.setattr(build_company_notes, "ROOT", tmp_path)

    return tmp_path


class TestBuildCompanyNotes:
    def test_writes_notes_for_companies_with_data(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        """RELIANCE has observations + corp actions → note written.
        SUNPHARMA has no observations and no corp actions → skipped."""
        count = build_company_notes.build(retrieved_at=fixed_ts)
        assert count == 1  # only RELIANCE

        notes_dir = fake_workspace / "notes" / "companies"
        files = list(notes_dir.glob("*.md"))
        assert len(files) == 1
        assert files[0].name == "reliance.md"

    def test_note_contains_yaml_frontmatter(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        build_company_notes.build(retrieved_at=fixed_ts)
        note = (fake_workspace / "notes" / "companies" / "reliance.md").read_text(encoding="utf-8")
        assert note.startswith("---\n")
        assert "isin: INE002A01018" in note
        assert "nse_symbol: RELIANCE" in note
        assert "company_name:" in note

    def test_note_contains_observations_table(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        build_company_notes.build(retrieved_at=fixed_ts)
        note = (fake_workspace / "notes" / "companies" / "reliance.md").read_text(encoding="utf-8")
        assert "### Price observations" in note
        assert "2750" in note
        assert "1000000" in note  # volume

    def test_note_contains_corporate_actions_table(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        build_company_notes.build(retrieved_at=fixed_ts)
        note = (fake_workspace / "notes" / "companies" / "reliance.md").read_text(encoding="utf-8")
        assert "## Corporate actions" in note
        assert "dividend" in note
        assert "7" in note  # dividend amount

    def test_note_does_not_include_macro_observations(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        """The USD/INR observation should NOT appear in the RELIANCE note
        (it's a macro driver observation, not a company observation)."""
        build_company_notes.build(retrieved_at=fixed_ts)
        note = (fake_workspace / "notes" / "companies" / "reliance.md").read_text(encoding="utf-8")
        # The macro observation value (84.05) should not be in the price table.
        # It WILL appear in the macro_exposures section as a list of driver slugs.
        assert "84.05" not in note.split("## Financials")[1].split("## Macro exposures")[0]

    def test_only_isins_filter(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        """Filtering to a specific ISIN should write only that company's note."""
        # Add a SUNPHARMA observation so it would be written if not filtered.
        from investorlens.ids import make_id
        from investorlens.io import upsert_records

        sunpharma_sid = make_id("sec", {"isin": "INE044A01026"})
        upsert_records(
            fake_workspace / "data" / "processed" / "observations.jsonl",
            [{
                "id": make_id("obs", {"subject_id": sunpharma_sid, "kind": "price_close",
                                       "period": "2024-09-30", "as_of": "2024-09-30", "source_id": "nse"}),
                "subject_id": sunpharma_sid,
                "kind": "price_close",
                "period": "2024-09-30",
                "as_of": "2024-09-30",
                "value": 1842.0,
                "unit": "INR/share",
                "currency": "INR",
                "data_status": "observed",
                "confidence": "high",
                "provenance": {"source": "nse", "extraction_method": "bulk_download",
                               "retrieved_at": "2024-09-30T18:30:00Z"},
            }],
            key="id",
        )

        count = build_company_notes.build(
            only_isins=["INE002A01018"],
            retrieved_at=fixed_ts,
        )
        assert count == 1
        files = list((fake_workspace / "notes" / "companies").glob("*.md"))
        assert len(files) == 1
        assert files[0].name == "reliance.md"

    def test_idempotent_with_fixed_timestamp(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        """Re-running with the same retrieved_at produces byte-identical output."""
        build_company_notes.build(retrieved_at=fixed_ts)
        note_path = fake_workspace / "notes" / "companies" / "reliance.md"
        content1 = note_path.read_bytes()

        build_company_notes.build(retrieved_at=fixed_ts)
        content2 = note_path.read_bytes()

        assert content1 == content2

    def test_returns_zero_when_no_isin_master(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        fixed_ts: datetime,
    ) -> None:
        """If ISIN master doesn't exist, build returns 0 (not an error)."""
        monkeypatch.setattr(build_company_notes, "ISIN_MASTER_PATH", tmp_path / "nonexistent.jsonl")
        count = build_company_notes.build(retrieved_at=fixed_ts)
        assert count == 0

    def test_main_cli_returns_zero(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        """The main() function should exit 0 on success."""
        rc = build_company_notes.main([
            "--retrieved-at", fixed_ts.isoformat(),
            "--log-level", "WARNING",
        ])
        assert rc == 0
        assert (fake_workspace / "notes" / "companies" / "reliance.md").exists()

    def test_main_cli_with_only_isins(
        self,
        fake_workspace: Path,
        fixed_ts: datetime,
    ) -> None:
        rc = build_company_notes.main([
            "--only-isins", "INE002A01018",
            "--retrieved-at", fixed_ts.isoformat(),
            "--log-level", "WARNING",
        ])
        assert rc == 0
        files = list((fake_workspace / "notes" / "companies").glob("*.md"))
        assert len(files) == 1
