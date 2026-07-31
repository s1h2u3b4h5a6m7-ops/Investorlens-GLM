"""Tests for the workflow YAML validator (scripts/validate_workflows.py).

Verifies the validator catches:
  - Invalid YAML syntax
  - References to non-existent scripts
  - Valid workflows pass cleanly
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "validate_workflows", ROOT / "scripts" / "validate_workflows.py"
)
assert _spec is not None and _spec.loader is not None
validate_workflows = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_workflows)


class TestExtractPythonScriptCalls:
    def test_finds_simple_python_call(self) -> None:
        text = "run: python scripts/foo.py\n"
        assert validate_workflows._extract_python_script_calls(text) == ["scripts/foo.py"]

    def test_finds_call_with_args(self) -> None:
        text = "run: python scripts/foo.py --bar baz\n"
        assert validate_workflows._extract_python_script_calls(text) == ["scripts/foo.py"]

    def test_finds_multiple_calls(self) -> None:
        text = """
        run: |
          python scripts/foo.py
          python scripts/bar.py --x
          python scripts/baz/qux.py
        """
        result = validate_workflows._extract_python_script_calls(text)
        assert result == ["scripts/foo.py", "scripts/bar.py", "scripts/baz/qux.py"]

    def test_finds_indented_call(self) -> None:
        text = "      run: python scripts/init_workspace.py\n"
        assert validate_workflows._extract_python_script_calls(text) == ["scripts/init_workspace.py"]

    def test_ignores_non_scripts_python(self) -> None:
        """`python -c '...'` or `python some_other_path/x.py` should not match."""
        text = "run: python -c 'print(1)'\n"
        assert validate_workflows._extract_python_script_calls(text) == []

    def test_ignores_non_py_extensions(self) -> None:
        text = "run: python scripts/foo.sh\n"
        assert validate_workflows._extract_python_script_calls(text) == []


class TestValidateWorkflow:
    def test_valid_workflow_passes(self, tmp_path: Path) -> None:
        # Create a real script that the workflow will reference.
        (ROOT / "scripts" / "init_workspace.py").exists()  # known to exist
        text = """
        name: Test
        on: [push]
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - run: python scripts/init_workspace.py
        """
        path = tmp_path / "test.yml"
        path.write_text(text, encoding="utf-8")
        errors = validate_workflows.validate_workflow(path)
        assert errors == []

    def test_invalid_yaml_returns_error(self, tmp_path: Path) -> None:
        text = "name: Test\n  bad: : : indentation\n"
        path = tmp_path / "bad.yml"
        path.write_text(text, encoding="utf-8")
        errors = validate_workflows.validate_workflow(path)
        assert len(errors) == 1
        assert "invalid YAML" in errors[0]

    def test_missing_script_returns_error(self, tmp_path: Path) -> None:
        text = """
        name: Test
        on: [push]
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - run: python scripts/this_does_not_exist.py
        """
        path = tmp_path / "missing.yml"
        path.write_text(text, encoding="utf-8")
        errors = validate_workflows.validate_workflow(path)
        assert len(errors) == 1
        assert "this_does_not_exist.py" in errors[0]


class TestValidateWorkflowsMain:
    def test_main_returns_zero_on_valid_workflows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The repo's real workflows should all be valid."""
        rc = validate_workflows.main(["--log-level", "WARNING"])
        assert rc == 0

    def test_main_returns_one_when_no_workflows_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """If the workflows directory doesn't exist, return 1."""
        # Override the WORKFLOWS_DIR module attribute.
        monkeypatch.setattr(validate_workflows, "WORKFLOWS_DIR", tmp_path / "nonexistent")
        rc = validate_workflows.main(["--log-level", "ERROR"])
        assert rc == 1
