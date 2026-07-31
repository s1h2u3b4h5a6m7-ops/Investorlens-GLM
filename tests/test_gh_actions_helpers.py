"""Tests for the GitHub Actions helper scripts.

These tests verify:
  - gh_actions_summary.py: generates correct Markdown summary from data files
  - gh_create_issue_on_failure.py: formats issue body correctly in dry-run mode

Both scripts are also exercised end-to-end in the integration tests.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Import the helper scripts by path
import importlib.util

_spec_summary = importlib.util.spec_from_file_location(
    "gh_actions_summary", ROOT / "scripts" / "gh_actions_summary.py"
)
assert _spec_summary is not None and _spec_summary.loader is not None
gh_actions_summary = importlib.util.module_from_spec(_spec_summary)
_spec_summary.loader.exec_module(gh_actions_summary)

_spec_issue = importlib.util.spec_from_file_location(
    "gh_create_issue_on_failure", ROOT / "scripts" / "gh_create_issue_on_failure.py"
)
assert _spec_issue is not None and _spec_issue.loader is not None
gh_create_issue_on_failure = importlib.util.module_from_spec(_spec_issue)
_spec_issue.loader.exec_module(gh_create_issue_on_failure)


# ---------------------------------------------------------------------------
# gh_actions_summary
# ---------------------------------------------------------------------------


class TestGhActionsSummary:
    def test_generate_summary_returns_markdown(self) -> None:
        summary = gh_actions_summary.generate_summary()
        assert isinstance(summary, str)
        assert "# InvestorLens Pipeline Summary" in summary
        assert "## File counts" in summary

    def test_summary_includes_all_known_files(self) -> None:
        summary = gh_actions_summary.generate_summary()
        for rel, name, _ in gh_actions_summary.SUMMARY_FILES:
            assert rel in summary, f"Expected {rel} in summary"

    def test_summary_includes_observation_kinds(self) -> None:
        """The current test data has price_close, policy_rate, fx_rate, cpi_yoy observations."""
        summary = gh_actions_summary.generate_summary()
        assert "### Observations by kind" in summary
        assert "price_close" in summary
        assert "policy_rate" in summary
        assert "fx_rate" in summary
        assert "cpi_yoy" in summary

    def test_summary_includes_observation_sources(self) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "### Observations by source" in summary
        assert "nse" in summary
        assert "yahoo" in summary
        assert "rbi" in summary
        assert "mospi" in summary

    def test_summary_includes_corporate_action_types(self) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "### Corporate Actions by type" in summary
        # The fixture has splits, bonuses, dividends, etc.
        assert "split" in summary or "bonus" in summary or "dividend" in summary

    def test_summary_includes_isin_master_by_exchange(self) -> None:
        summary = gh_actions_summary.generate_summary()
        assert "### ISIN Master by exchange" in summary
        assert "NSE+BSE" in summary

    def test_main_writes_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        rc = gh_actions_summary.main(argv=[])
        assert rc == 0
        captured = capsys.readouterr()
        assert "# InvestorLens Pipeline Summary" in captured.out

    def test_main_writes_to_output_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "summary.md"
        rc = gh_actions_summary.main(argv=["--output", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "# InvestorLens Pipeline Summary" in content

    def test_main_writes_to_step_summary_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        step_summary = tmp_path / "step_summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))
        rc = gh_actions_summary.main(argv=["--write-step-summary"])
        assert rc == 0
        assert step_summary.exists()
        content = step_summary.read_text(encoding="utf-8")
        assert "# InvestorLens Pipeline Summary" in content

    def test_main_warns_when_step_summary_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        import logging
        with caplog.at_level(logging.WARNING):
            rc = gh_actions_summary.main(argv=["--write-step-summary"])
        assert rc == 0
        assert any("GITHUB_STEP_SUMMARY is not set" in r.message for r in caplog.records)

    def test_count_records_returns_zero_for_missing_file(self, tmp_path: Path) -> None:
        assert gh_actions_summary._count_records(tmp_path / "nonexistent.jsonl") == 0

    def test_count_records_returns_count_for_existing_file(self, tmp_path: Path) -> None:
        from investorlens.io import write_jsonl
        path = tmp_path / "test.jsonl"
        write_jsonl(path, [{"id": "a"}, {"id": "b"}, {"id": "c"}])
        assert gh_actions_summary._count_records(path) == 3


# ---------------------------------------------------------------------------
# gh_create_issue_on_failure
# ---------------------------------------------------------------------------


class TestGhCreateIssueOnFailure:
    def test_dry_run_prints_title_and_body(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        # Set CI env vars so the script has context to format.
        monkeypatch.setenv("GITHUB_REPOSITORY", "test/repo")
        monkeypatch.setenv("GITHUB_RUN_ID", "12345")
        monkeypatch.setenv("GITHUB_REF_NAME", "main")
        monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
        monkeypatch.setenv("GITHUB_ACTOR", "testuser")

        rc = gh_create_issue_on_failure.main([
            "--workflow", "Daily Pipeline",
            "--failed-step", "Fetch bhavcopy",
            "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "=== DRY RUN ===" in captured.out
        assert "Title: [Pipeline Failure] Daily Pipeline" in captured.out
        assert "Daily Pipeline" in captured.out
        assert "Fetch bhavcopy" in captured.out
        assert "main" in captured.out
        assert "abcdef1" in captured.out  # short SHA
        assert "testuser" in captured.out
        assert "https://github.com/test/repo/actions/runs/12345" in captured.out

    def test_no_ci_no_dry_run_does_nothing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Simulate running outside CI without --dry-run.
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        import logging
        with caplog.at_level(logging.INFO):
            rc = gh_create_issue_on_failure.main([
                "--workflow", "Test",
                "--failed-step", "Step",
            ])
        assert rc == 0
        assert any("Not running inside GitHub Actions" in r.message for r in caplog.records)

    def test_dry_run_works_outside_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--dry-run should work even outside CI (useful for local testing)."""
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.setenv("GITHUB_REPOSITORY", "test/repo")
        monkeypatch.setenv("GITHUB_RUN_ID", "99999")
        rc = gh_create_issue_on_failure.main([
            "--workflow", "Test",
            "--failed-step", "Step",
            "--dry-run",
        ])
        assert rc == 0

    def test_issue_body_contains_required_sections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The issue body should have all the sections a human needs to debug."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test/repo")
        monkeypatch.setenv("GITHUB_RUN_ID", "12345")
        monkeypatch.setenv("GITHUB_REF_NAME", "main")
        monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
        monkeypatch.setenv("GITHUB_ACTOR", "testuser")

        # Capture the body via dry-run output.
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = gh_create_issue_on_failure.main([
                "--workflow", "Daily Pipeline",
                "--failed-step", "Fetch bhavcopy",
                "--dry-run",
            ])
        assert rc == 0
        body = buf.getvalue()
        assert "## InvestorLens Pipeline Failure" in body
        assert "### Run details" in body
        assert "### Next steps" in body
        assert "### Auto-generated" in body
        assert "Re-run the failed job" in body
        assert "Close this issue" in body


# Note: gh_create_issue_on_failure.main() already accepts an argv list,
# so no monkey-patching is needed for testability.
