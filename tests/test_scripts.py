"""Smoke test: scripts run end-to-end without errors."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_init_workspace_runs(tmp_path, monkeypatch) -> None:
    """init_workspace.py should run successfully and create the expected files."""
    # Use a temp data dir so we don't pollute the real one.
    fake_data = tmp_path / "data"
    fake_data.mkdir()

    # Patch DATA_DIR by changing the script's CWD via env var.
    # The script computes paths from its own __file__, so we just run it and check
    # it exits 0.
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_workspace.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"init_workspace failed:\n{result.stderr}"
    # It should have created the master files.
    assert (ROOT / "data" / "master" / "isin_master.jsonl").exists()


def test_validate_outputs_runs() -> None:
    """validate_outputs.py should run successfully (exit 0) on a freshly initialized workspace."""
    # Ensure workspace is initialized.
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_workspace.py")],
        cwd=ROOT,
        capture_output=True,
        timeout=30,
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_outputs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"validate_outputs failed:\n{result.stderr}"
