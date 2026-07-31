"""Integration tests for the build_canvases.py script."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from investorlens.io import write_jsonl  # noqa: E402

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "build_canvases", ROOT / "scripts" / "builders" / "build_canvases.py"
)
assert _spec is not None and _spec.loader is not None
build_canvases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_canvases)


@pytest.fixture
def fake_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fake workspace with a small ISIN master spanning 3 sectors."""
    from investorlens.ids import make_id

    data_dir = tmp_path / "data"
    master_dir = data_dir / "master"
    master_dir.mkdir(parents=True)
    canvases_dir = tmp_path / "notes" / "canvases"
    sectors_dir = canvases_dir / "sectors"

    isin_records = [
        # Pharmaceuticals (2 companies)
        {"id": make_id("isin", {"isin": "INE044A01026"}), "isin": "INE044A01026",
         "nse_symbol": "SUNPHARMA", "company_name": "Sun Pharma", "sector": "Pharmaceuticals"},
        {"id": make_id("isin", {"isin": "INE999A01001"}), "isin": "INE999A01001",
         "nse_symbol": "CIPLA", "company_name": "Cipla", "sector": "Pharmaceuticals"},
        # Banks (1 company)
        {"id": make_id("isin", {"isin": "INE040A01034"}), "isin": "INE040A01034",
         "nse_symbol": "HDFCBANK", "company_name": "HDFC Bank", "sector": "Banks"},
        # No sector (Unclassified)
        {"id": make_id("isin", {"isin": "INE002A01018"}), "isin": "INE002A01018",
         "nse_symbol": "RELIANCE", "company_name": "Reliance", "sector": None},
    ]
    write_jsonl(master_dir / "isin_master.jsonl", isin_records)

    monkeypatch.setattr(build_canvases, "ISIN_MASTER_PATH", master_dir / "isin_master.jsonl")
    monkeypatch.setattr(build_canvases, "CANVASES_DIR", canvases_dir)
    monkeypatch.setattr(build_canvases, "SECTORS_DIR", sectors_dir)
    monkeypatch.setattr(build_canvases, "ROOT", tmp_path)

    return tmp_path


class TestBuildCanvases:
    def test_writes_sector_canvases_and_index(self, fake_workspace: Path) -> None:
        """Should write 3 sector canvases + 1 index canvas = 4 files."""
        count = build_canvases.build()
        assert count == 4

        sectors_dir = fake_workspace / "notes" / "canvases" / "sectors"
        sector_files = list(sectors_dir.glob("*.canvas"))
        assert len(sector_files) == 3  # Pharmaceuticals, Banks, (Unclassified)

        index_file = fake_workspace / "notes" / "canvases" / "index.canvas"
        assert index_file.exists()

    def test_sector_canvas_contains_correct_companies(self, fake_workspace: Path) -> None:
        build_canvases.build()
        pharma_canvas = fake_workspace / "notes" / "canvases" / "sectors" / "pharmaceuticals.canvas"
        assert pharma_canvas.exists()

        data = json.loads(pharma_canvas.read_text(encoding="utf-8"))
        file_nodes = [n for n in data["nodes"] if n.get("type") == "file"]
        assert len(file_nodes) == 2  # SUNPHARMA + CIPLA

        file_paths = {n["file"] for n in file_nodes}
        assert "notes/companies/sunpharma.md" in file_paths
        assert "notes/companies/cipla.md" in file_paths

    def test_index_canvas_links_to_sector_canvases(self, fake_workspace: Path) -> None:
        build_canvases.build()
        index_data = json.loads(
            (fake_workspace / "notes" / "canvases" / "index.canvas").read_text(encoding="utf-8")
        )
        file_nodes = [n for n in index_data["nodes"] if n.get("type") == "file"]
        # All 3 sectors should have file nodes linking to their canvas files.
        assert len(file_nodes) == 3
        file_paths = {n["file"] for n in file_nodes}
        assert "notes/canvases/sectors/pharmaceuticals.canvas" in file_paths
        assert "notes/canvases/sectors/banks.canvas" in file_paths
        assert "notes/canvases/sectors/unclassified.canvas" in file_paths

    def test_unclassified_sector_handled(self, fake_workspace: Path) -> None:
        """Companies with no sector go into '(Unclassified)'."""
        build_canvases.build()
        unclassified = fake_workspace / "notes" / "canvases" / "sectors" / "unclassified.canvas"
        assert unclassified.exists()
        data = json.loads(unclassified.read_text(encoding="utf-8"))
        file_nodes = [n for n in data["nodes"] if n.get("type") == "file"]
        assert len(file_nodes) == 1  # RELIANCE

    def test_idempotent_output(self, fake_workspace: Path) -> None:
        """Re-running produces byte-identical canvas files."""
        build_canvases.build()
        pharma_path = fake_workspace / "notes" / "canvases" / "sectors" / "pharmaceuticals.canvas"
        content1 = pharma_path.read_bytes()

        build_canvases.build()
        content2 = pharma_path.read_bytes()

        assert content1 == content2

    def test_returns_zero_when_no_isin_master(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(build_canvases, "ISIN_MASTER_PATH", tmp_path / "nonexistent.jsonl")
        count = build_canvases.build()
        assert count == 0

    def test_main_cli_returns_zero(self, fake_workspace: Path) -> None:
        rc = build_canvases.main(["--log-level", "WARNING"])
        assert rc == 0

    def test_canvas_json_is_valid(self, fake_workspace: Path) -> None:
        """The output .canvas files should be valid JSON with nodes and edges."""
        build_canvases.build()
        for canvas_file in (fake_workspace / "notes" / "canvases").rglob("*.canvas"):
            data = json.loads(canvas_file.read_text(encoding="utf-8"))
            assert "nodes" in data
            assert "edges" in data
            assert isinstance(data["nodes"], list)
            assert isinstance(data["edges"], list)
            # Every node should have an id, type, x, y, width, height
            for node in data["nodes"]:
                assert "id" in node
                assert "type" in node
                assert "x" in node
                assert "y" in node
                assert "width" in node
                assert "height" in node
            # Every edge should have an id, fromNode, toNode
            for edge in data["edges"]:
                assert "id" in edge
                assert "fromNode" in edge
                assert "toNode" in edge
