"""Tests for the canvas builders (investorlens.builders.canvas)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from investorlens.builders.canvas import (
    GRID_COLUMNS,
    MAX_NODES_PER_CANVAS,
    NODE_HEIGHT,
    NODE_WIDTH,
    X_SPACING,
    Y_SPACING,
    build_index_canvas,
    build_sector_canvas,
)
from investorlens.ids import make_id

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pharma_companies() -> list[dict]:
    """3 pharmaceutical companies (matching the seeded ISIN master)."""
    return [
        {
            "id": make_id("isin", {"isin": "INE044A01026"}),
            "isin": "INE044A01026",
            "nse_symbol": "SUNPHARMA",
            "company_name": "Sun Pharmaceutical Industries Limited",
            "sector": "Pharmaceuticals",
        },
        {
            "id": make_id("isin", {"isin": "INE999A01001"}),
            "isin": "INE999A01001",
            "nse_symbol": "CIPLA",
            "company_name": "Cipla Limited",
            "sector": "Pharmaceuticals",
        },
        {
            "id": make_id("isin", {"isin": "INE999A01002"}),
            "isin": "INE999A01002",
            "nse_symbol": "DRREDDY",
            "company_name": "Dr. Reddy's Laboratories Limited",
            "sector": "Pharmaceuticals",
        },
    ]


@pytest.fixture
def all_sectors() -> list[tuple[str, list[dict]]]:
    """A small set of sectors for the index canvas test."""
    return [
        ("Pharmaceuticals", [
            {"id": "isin_a", "isin": "INE044A01026", "nse_symbol": "SUNPHARMA", "company_name": "Sun Pharma"},
        ]),
        ("Banks", [
            {"id": "isin_b", "isin": "INE040A01034", "nse_symbol": "HDFCBANK", "company_name": "HDFC Bank"},
        ]),
        ("Computers - Software", [
            {"id": "isin_c", "isin": "INE467B01029", "nse_symbol": "TCS", "company_name": "TCS"},
        ]),
    ]


# ---------------------------------------------------------------------------
# build_sector_canvas
# ---------------------------------------------------------------------------


class TestBuildSectorCanvas:
    def test_returns_canvas_object(self, pharma_companies: list[dict]) -> None:
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        assert canvas is not None

    def test_has_correct_node_count(self, pharma_companies: list[dict]) -> None:
        """3 company nodes + 1 title node = 4 nodes."""
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        assert len(data["nodes"]) == 4  # 1 title + 3 companies

    def test_has_correct_edge_count(self, pharma_companies: list[dict]) -> None:
        """3 edges from sector title to each company."""
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        assert len(data["edges"]) == 3

    def test_title_node_has_sector_name(self, pharma_companies: list[dict]) -> None:
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        # Find the text node (title)
        text_nodes = [n for n in data["nodes"] if n.get("type") == "text"]
        assert len(text_nodes) >= 1
        title_node = text_nodes[0]
        assert "Pharmaceuticals" in title_node["text"]
        assert "3 companies" in title_node["text"]

    def test_company_nodes_are_file_nodes(self, pharma_companies: list[dict]) -> None:
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        file_nodes = [n for n in data["nodes"] if n.get("type") == "file"]
        assert len(file_nodes) == 3
        # Each file node should point to a notes/companies/ path.
        for n in file_nodes:
            assert n["file"].startswith("notes/companies/")
            assert n["file"].endswith(".md")

    def test_file_nodes_use_correct_slugs(self, pharma_companies: list[dict]) -> None:
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        file_paths = {n["file"] for n in data["nodes"] if n.get("type") == "file"}
        # SUNPHARMA → sunpharma.md, CIPLA → cipla.md, DRREDDY → drreddy.md
        assert "notes/companies/sunpharma.md" in file_paths
        assert "notes/companies/cipla.md" in file_paths
        assert "notes/companies/drreddy.md" in file_paths

    def test_edges_labeled_contains(self, pharma_companies: list[dict]) -> None:
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        for edge in data["edges"]:
            assert edge.get("label") == "contains"

    def test_edges_connect_title_to_companies(self, pharma_companies: list[dict]) -> None:
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        # The title node ID should be the fromNode for all edges.
        from_ids = {e["fromNode"] for e in data["edges"]}
        assert len(from_ids) == 1  # all edges come from the same node (title)

    def test_companies_sorted_alphabetically(self) -> None:
        """Companies should appear in alphabetical order in the grid."""
        companies = [
            {"id": "isin_z", "nse_symbol": "ZEBRA", "company_name": "Zebra Co", "isin": "INE001A00001"},
            {"id": "isin_a", "nse_symbol": "APPLE", "company_name": "Apple Co", "isin": "INE002A00002"},
            {"id": "isin_m", "nse_symbol": "MANGO", "company_name": "Mango Co", "isin": "INE003A00003"},
        ]
        canvas = build_sector_canvas("Test", companies)
        data = canvas
        file_nodes = [n for n in data["nodes"] if n.get("type") == "file"]
        # Sort by x position (grid is left-to-right)
        file_nodes.sort(key=lambda n: (n["y"], n["x"]))
        # First file node should be Apple (alphabetically first)
        assert "apple" in file_nodes[0]["file"]
        # Last should be Zebra
        assert "zebra" in file_nodes[-1]["file"]

    def test_deterministic_output(self, pharma_companies: list[dict]) -> None:
        """Same inputs → identical canvas JSON."""
        a = build_sector_canvas("Pharmaceuticals", pharma_companies)
        b = build_sector_canvas("Pharmaceuticals", pharma_companies)
        assert a == b

    def test_empty_sector_produces_title_only(self) -> None:
        """A sector with no companies should still produce a canvas with just the title."""
        canvas = build_sector_canvas("Empty Sector", [])
        data = canvas
        assert len(data["nodes"]) == 1  # just the title
        assert len(data["edges"]) == 0

    def test_truncation_at_max_nodes(self) -> None:
        """If sector has >MAX_NODES_PER_CANVAS companies, truncate and add a note."""
        # Generate 85 companies (5 over the limit of 80).
        companies = [
            {
                "id": f"isin_{i:04d}",
                "nse_symbol": f"SYM{i}",
                "company_name": f"Company {i:04d}",
                "isin": f"INE{i:010d}",
            }
            for i in range(85)
        ]
        canvas = build_sector_canvas("Large Sector", companies)
        data = canvas
        # 80 company file nodes + 1 title + 1 truncation note = 82 nodes
        file_nodes = [n for n in data["nodes"] if n.get("type") == "file"]
        text_nodes = [n for n in data["nodes"] if n.get("type") == "text"]
        assert len(file_nodes) == MAX_NODES_PER_CANVAS  # 80
        assert len(text_nodes) == 2  # title + truncation note
        # The truncation note should mention the truncation.
        trunc_note = text_nodes[1]  # second text node
        assert "Truncated" in trunc_note["text"]
        assert "85" in trunc_note["text"]

    def test_node_positions_are_deterministic(self, pharma_companies: list[dict]) -> None:
        """Same company should always get the same grid position."""
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        data = canvas
        # Cipla is alphabetically first → should be at grid position 0.
        cipla_node = next(n for n in data["nodes"] if n.get("type") == "file" and "cipla" in n["file"])
        assert cipla_node["x"] == 0  # first column
        # y should be below the title (TITLE_HEIGHT + 50 = 170)
        assert cipla_node["y"] == 170  # TITLE_HEIGHT(120) + 50

    def test_grid_positions_progress_correctly(self) -> None:
        """Verify the grid layout: columns fill left-to-right, then wrap to next row."""
        companies = [
            {"id": f"isin_{i}", "nse_symbol": f"S{i}", "company_name": f"Co {i}", "isin": f"INE{i:010d}"}
            for i in range(GRID_COLUMNS + 2)  # 10 companies = 1 full row + 2 in next row
        ]
        canvas = build_sector_canvas("Test", companies)
        data = canvas
        file_nodes = sorted(
            [n for n in data["nodes"] if n.get("type") == "file"],
            key=lambda n: (n["y"], n["x"]),
        )
        # First 8 should be in row 0 (y == 170)
        for i in range(GRID_COLUMNS):
            assert file_nodes[i]["y"] == 170, f"Node {i} should be in row 0"
        # Nodes 8 and 9 should be in row 1 (y == 170 + 300 = 470)
        for i in range(GRID_COLUMNS, len(file_nodes)):
            assert file_nodes[i]["y"] == 470, f"Node {i} should be in row 1"
            assert file_nodes[i]["x"] == (i - GRID_COLUMNS) * X_SPACING


# ---------------------------------------------------------------------------
# build_index_canvas
# ---------------------------------------------------------------------------


class TestBuildIndexCanvas:
    def test_returns_canvas_object(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        canvas = build_index_canvas(all_sectors)
        assert canvas is not None

    def test_has_correct_node_count(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        """1 title + 3 sector nodes = 4 nodes."""
        canvas = build_index_canvas(all_sectors)
        data = canvas
        assert len(data["nodes"]) == 4

    def test_has_correct_edge_count(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        """3 edges from index title to each sector."""
        canvas = build_index_canvas(all_sectors)
        data = canvas
        assert len(data["edges"]) == 3

    def test_title_node_says_investorlens(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        canvas = build_index_canvas(all_sectors)
        data = canvas
        text_nodes = [n for n in data["nodes"] if n.get("type") == "text"]
        # Should have the title text node (and sector text nodes if no canvas paths given)
        title = text_nodes[0]
        assert "InvestorLens" in title["text"]
        assert "3 sectors" in title["text"]

    def test_sector_nodes_without_paths_are_text(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        """Without canvas_paths, sector nodes are text nodes."""
        canvas = build_index_canvas(all_sectors)
        data = canvas
        # Title + 3 sector text nodes = 4 text nodes
        text_nodes = [n for n in data["nodes"] if n.get("type") == "text"]
        assert len(text_nodes) == 4

    def test_sector_nodes_with_paths_are_file_nodes(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        """With canvas_paths, sector nodes link to .canvas files."""
        paths = {
            "Pharmaceuticals": "notes/canvases/sectors/pharmaceuticals.canvas",
            "Banks": "notes/canvases/sectors/banks.canvas",
            "Computers - Software": "notes/canvases/sectors/computers_software.canvas",
        }
        canvas = build_index_canvas(all_sectors, sector_canvas_paths=paths)
        data = canvas
        file_nodes = [n for n in data["nodes"] if n.get("type") == "file"]
        assert len(file_nodes) == 3
        file_paths = {n["file"] for n in file_nodes}
        assert "notes/canvases/sectors/pharmaceuticals.canvas" in file_paths
        assert "notes/canvases/sectors/banks.canvas" in file_paths

    def test_edges_labeled_sector(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        canvas = build_index_canvas(all_sectors)
        data = canvas
        for edge in data["edges"]:
            assert edge.get("label") == "sector"

    def test_sectors_sorted_alphabetically(self) -> None:
        """Sectors should appear in alphabetical order in the grid."""
        sectors = [
            ("Zimbabwe Sector", [{"id": "z", "company_name": "Z Co", "isin": "INE001A00001", "nse_symbol": "Z"}]),
            ("Apple Sector", [{"id": "a", "company_name": "A Co", "isin": "INE002A00002", "nse_symbol": "A"}]),
            ("Mango Sector", [{"id": "m", "company_name": "M Co", "isin": "INE003A00003", "nse_symbol": "M"}]),
        ]
        canvas = build_index_canvas(sectors)
        data = canvas
        # Find sector nodes (non-title text nodes) sorted by position
        text_nodes = [n for n in data["nodes"] if n.get("type") == "text"]
        # The title is first (y=0); sectors start at y=170
        sector_nodes = sorted([n for n in text_nodes if n["y"] > 0], key=lambda n: (n["y"], n["x"]))
        # First sector node should be "Apple Sector"
        assert "Apple Sector" in sector_nodes[0]["text"]
        # Last should be "Zimbabwe Sector"
        assert "Zimbabwe Sector" in sector_nodes[-1]["text"]

    def test_deterministic_output(self, all_sectors: list[tuple[str, list[dict]]]) -> None:
        a = build_index_canvas(all_sectors)
        b = build_index_canvas(all_sectors)
        assert a == b

    def test_empty_sectors_produces_title_only(self) -> None:
        canvas = build_index_canvas([])
        data = canvas
        assert len(data["nodes"]) == 1  # just the title
        assert len(data["edges"]) == 0

    def test_canvas_json_is_valid(self, pharma_companies: list[dict]) -> None:
        """The canvas JSON should be valid JSON with nodes and edges keys."""
        canvas = build_sector_canvas("Pharmaceuticals", pharma_companies)
        json_str = json.dumps(canvas)
        parsed = json.loads(json_str)
        assert "nodes" in parsed
        assert "edges" in parsed
        assert isinstance(parsed["nodes"], list)
        assert isinstance(parsed["edges"], list)
