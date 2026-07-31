"""Tests for the GitHub Actions summary script (scripts/gh_actions_summary.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Import the script module by path
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "gh_actions_summary", ROOT / "scripts" / "gh_actions_summary.py"
)
assert _spec is not None and _spec.loader is not None
gh_actions_summary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gh_actions_summary)


@pytest.fixture
def empty_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the script's ROOT to a tmp dir with empty JSONL files."""
    # Create the expected directory structure.
    (tmp_path / "data" / "master").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    # Create empty JSONL files (write a single newline so read_jsonl returns []).
    for rel, _, _ in gh_actions_summary.SUMMARY_FILES:
        (tmp_path / rel).write_text("", encoding="utf-8")
    monkeypatch.setattr(gh_actions_summary, "ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def populated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A workspace with realistic seeded data for the summary."""
    from investorlens.io import write_jsonl

    (tmp_path / "data" / "master").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)

    # ISIN master with 3 exchanges
    write_jsonl(tmp_path / "data/master/isin_master.jsonl", [
        {"id": "isin_a", "isin": "INE001A01018", "exchange": "NSE", "company_name": "A"},
        {"id": "isin_b", "isin": "INE002A01027", "exchange": "BSE", "company_name": "B"},
        {"id": "isin_c", "isin": "INE003A01034", "exchange": "NSE+BSE", "company_name": "C"},
    ])

    # Observations across kinds/sources
    write_jsonl(tmp_path / "data/processed/observations.jsonl", [
        {"id": "obs_1", "subject_id": "sec_a", "kind": "price_close", "as_of": "2024-09-30",
         "provenance": {"source": "nse", "retrieved_at": "2024-10-01T10:00:00Z"}},
        {"id": "obs_2", "subject_id": "sec_a", "kind": "price_close", "as_of": "2024-10-01",
         "provenance": {"source": "nse", "retrieved_at": "2024-10-02T10:00:00Z"}},
        {"id": "obs_3", "subject_id": "sec_a", "kind": "price_close_adj", "as_of": "2024-09-30",
         "provenance": {"source": "investorlens", "retrieved_at": "2024-10-01T11:00:00Z"}},
        {"id": "obs_4", "subject_id": "drv_1", "kind": "policy_rate", "as_of": "2024-10-09",
         "provenance": {"source": "rbi", "retrieved_at": "2024-10-09T13:30:00Z"}},
        {"id": "obs_5", "subject_id": "drv_2", "kind": "fx_rate", "as_of": "2024-10-04",
         "provenance": {"source": "rbi", "retrieved_at": "2024-10-09T13:30:00Z"}},
        {"id": "obs_6", "subject_id": "drv_3", "kind": "cpi_yoy", "as_of": "2024-09-01",
         "provenance": {"source": "mospi", "retrieved_at": "2024-10-14T18:00:00Z"}},
    ])

    # Corporate actions
    write_jsonl(tmp_path / "data/processed/corporate_actions.jsonl", [
        {"id": "ca_1", "action_type": "split", "ex_date": "2024-01-15",
         "provenance": {"source": "nse", "retrieved_at": "2024-10-01T10:00:00Z"}},
        {"id": "ca_2", "action_type": "dividend", "ex_date": "2024-02-15",
         "provenance": {"source": "nse", "retrieved_at": "2024-10-01T10:00:00Z"}},
        {"id": "ca_3", "action_type": "bonus", "ex_date": "2024-03-15",
         "provenance": {"source": "nse", "retrieved_at": "2024-10-01T10:00:00Z"}},
    ])

    monkeypatch.setattr(gh_actions_summary, "ROOT", tmp_path)
    return tmp_path


class TestGenerateSummary:
    def test_empty_workspace_produces_minimal_summary(self, empty_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "# InvestorLens Pipeline Summary" in summary
        assert "## File counts" in summary
        # All counts should be 0
        assert "| 0 |" in summary

    def test_populated_summary_has_expected_sections(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "# InvestorLens Pipeline Summary" in summary
        assert "## File counts" in summary
        assert "### ISIN Master by exchange" in summary
        assert "### Observations by kind" in summary
        assert "### Observations by source" in summary
        assert "### Corporate Actions by type" in summary
        assert "### Latest retrieval timestamps" in summary

    def test_file_counts_correct(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        # ISIN master has 3 records
        assert "| `data/master/isin_master.jsonl` | 3 |" in summary
        # Observations has 6 records
        assert "| `data/processed/observations.jsonl` | 6 |" in summary
        # Corp actions has 3 records
        assert "| `data/processed/corporate_actions.jsonl` | 3 |" in summary

    def test_isin_master_exchange_breakdown(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "| NSE | 1 |" in summary
        assert "| BSE | 1 |" in summary
        assert "| NSE+BSE | 1 |" in summary

    def test_observations_kind_breakdown(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        # price_close: 2 records
        assert "| `price_close` | 2 |" in summary
        # policy_rate: 1 record
        assert "| `policy_rate` | 1 |" in summary
        # fx_rate: 1 record
        assert "| `fx_rate` | 1 |" in summary
        # cpi_yoy: 1 record
        assert "| `cpi_yoy` | 1 |" in summary

    def test_observations_source_breakdown(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        # nse: 2 (price_close × 2)
        assert "| `nse` | 2 |" in summary
        # rbi: 2 (policy_rate + fx_rate)
        assert "| `rbi` | 2 |" in summary
        # mospi: 1 (cpi_yoy)
        assert "| `mospi` | 1 |" in summary
        # investorlens: 1 (price_close_adj)
        assert "| `investorlens` | 1 |" in summary

    def test_corporate_actions_type_breakdown(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "| `split` | 1 |" in summary
        assert "| `dividend` | 1 |" in summary
        assert "| `bonus` | 1 |" in summary

    def test_date_coverage_displayed(self, populated_workspace: Path) -> None:
        """The kind table should show earliest and latest as_of dates per kind."""
        summary = gh_actions_summary.generate_summary()
        # price_close has as_of 2024-09-30 and 2024-10-01
        assert "| `price_close` | 2 | 2024-09-30 | 2024-10-01 |" in summary

    def test_latest_retrieval_timestamps_displayed(self, populated_workspace: Path) -> None:
        summary = gh_actions_summary.generate_summary()
        # Latest retrieval for observations.jsonl is 2024-10-14T18:00:00Z (MOSPI)
        assert "2024-10-14T18:00:00Z" in summary

    def test_missing_files_handled_gracefully(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the data/ dir doesn't exist at all, the summary should still work."""
        monkeypatch.setattr(gh_actions_summary, "ROOT", tmp_path)
        summary = gh_actions_summary.generate_summary()
        assert "# InvestorLens Pipeline Summary" in summary
        assert "| 0 |" in summary  # all counts zero


class TestMain:
    def test_writes_to_output_file(
        self, populated_workspace: Path, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        import sys
        out_file = tmp_path / "summary.md"
        rc = gh_actions_summary.main(["--output", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "# InvestorLens Pipeline Summary" in content
        # stdout should be empty
        assert capsys.readouterr().out == ""

    def test_prints_to_stdout_by_default(
        self, populated_workspace: Path, capsys: pytest.CaptureFixture
    ) -> None:
        rc = gh_actions_summary.main([])
        assert rc == 0
        captured = capsys.readouterr()
        assert "# InvestorLens Pipeline Summary" in captured.out

    def test_write_step_summary_no_env_var_is_warning(
        self,
        populated_workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Ensure GITHUB_STEP_SUMMARY is not set.
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        import logging
        with caplog.at_level(logging.WARNING):
            rc = gh_actions_summary.main(["--write-step-summary"])
        assert rc == 0
        assert any("GITHUB_STEP_SUMMARY is not set" in r.message for r in caplog.records)

    def test_write_step_summary_with_env_var(
        self,
        populated_workspace: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        step_file = tmp_path / "step_summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_file))
        rc = gh_actions_summary.main(["--write-step-summary"])
        assert rc == 0
        assert step_file.exists()
        content = step_file.read_text(encoding="utf-8")
        assert "# InvestorLens Pipeline Summary" in content
