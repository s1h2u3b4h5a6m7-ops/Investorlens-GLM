"""Tests for the graph data builder (investorlens.builders.graph)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from investorlens.builders.graph import build_graph_data, slugify_sector
from investorlens.ids import make_id


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def isin_master() -> list[dict]:
    return [
        {
            "id": make_id("isin", {"isin": "INE002A01018"}),
            "isin": "INE002A01018",
            "nse_symbol": "RELIANCE",
            "bse_code": "500325",
            "company_name": "Reliance Industries Limited",
            "sector": "Refineries",
            "exchange": "NSE+BSE",
        },
        {
            "id": make_id("isin", {"isin": "INE044A01026"}),
            "isin": "INE044A01026",
            "nse_symbol": "SUNPHARMA",
            "bse_code": "524715",
            "company_name": "Sun Pharmaceutical Industries Limited",
            "sector": "Pharmaceuticals",
            "exchange": "NSE+BSE",
        },
        # This company has no observations → should be skipped
        {
            "id": make_id("isin", {"isin": "INE999A99999"}),
            "isin": "INE999A99999",
            "nse_symbol": "NODATA",
            "company_name": "No Data Co",
            "sector": "Test",
            "exchange": "NSE",
        },
    ]


@pytest.fixture
def observations() -> list[dict]:
    reliance_sid = make_id("sec", {"isin": "INE002A01018"})
    sunpharma_sid = make_id("sec", {"isin": "INE044A01026"})
    usd_sid = make_id("drv", {"slug": "fx_usd_inr"})
    return [
        {"subject_id": reliance_sid, "kind": "price_close", "value": 2750.0},
        {"subject_id": sunpharma_sid, "kind": "price_close", "value": 1842.0},
        {"subject_id": usd_sid, "kind": "fx_rate", "value": 84.05},
    ]


@pytest.fixture
def corp_actions() -> list[dict]:
    reliance_sid = make_id("sec", {"isin": "INE002A01018"})
    return [
        {"security_id": reliance_sid, "action_type": "dividend", "amount_per_share": "7"},
    ]


class TestSlugifySector:
    def test_basic(self) -> None:
        assert slugify_sector("Pharmaceuticals") == "pharmaceuticals"

    def test_spaces_replaced(self) -> None:
        assert slugify_sector("Computers - Software") == "computers__software"

    def test_ampersand(self) -> None:
        assert slugify_sector("Food & Beverages") == "food_and_beverages"

    def test_empty_returns_unknown(self) -> None:
        assert slugify_sector("") == "unknown"


class TestBuildGraphData:
    def test_returns_dict_with_required_keys(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        assert "nodes" in result
        assert "edges" in result
        assert "metadata" in result

    def test_skips_companies_with_no_data(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        """The NODATA company (no observations, no corp actions) should be skipped."""
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        company_nodes = [n for n in result["nodes"] if n["data"]["type"] == "company"]
        isins = {n["data"]["isin"] for n in company_nodes}
        assert "INE002A01018" in isins  # RELIANCE
        assert "INE044A01026" in isins  # SUNPHARMA
        assert "INE999A99999" not in isins  # NODATA skipped

    def test_creates_sector_nodes(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        sector_nodes = [n for n in result["nodes"] if n["data"]["type"] == "sector"]
        sector_labels = {n["data"]["label"] for n in sector_nodes}
        assert "Refineries" in sector_labels
        assert "Pharmaceuticals" in sector_labels

    def test_creates_macro_driver_nodes(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        """USD/INR observation should produce a macro_driver node."""
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        macro_nodes = [n for n in result["nodes"] if n["data"]["type"] == "macro_driver"]
        labels = {n["data"]["label"] for n in macro_nodes}
        assert "USD/INR" in labels

    def test_belongs_to_edges(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        """Each company should have a belongs_to edge to its sector."""
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        belongs_to_edges = [e for e in result["edges"] if e["data"]["type"] == "belongs_to"]
        assert len(belongs_to_edges) == 2  # RELIANCE + SUNPHARMA

    def test_exposed_to_edges(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        """Each company should have an exposed_to edge to each macro driver."""
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        exposed_to_edges = [e for e in result["edges"] if e["data"]["type"] == "exposed_to"]
        # 2 companies × 1 macro driver = 2 edges
        assert len(exposed_to_edges) == 2

    def test_company_node_has_observations_count(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        reliance_node = next(
            n for n in result["nodes"]
            if n["data"].get("isin") == "INE002A01018"
        )
        assert reliance_node["data"]["observations_count"] == 1
        assert reliance_node["data"]["corporate_actions_count"] == 1

    def test_metadata_populated(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        meta = result["metadata"]
        assert meta["generated_at"] == "2024-09-30T18:30:00+00:00"
        assert meta["node_count"] == len(result["nodes"])
        assert meta["edge_count"] == len(result["edges"])
        assert meta["company_count"] == 2
        assert meta["sector_count"] == 2
        assert meta["macro_driver_count"] == 1
        assert "Refineries" in meta["sectors"]
        assert "Pharmaceuticals" in meta["sectors"]

    def test_deterministic_output(
        self,
        isin_master: list[dict],
        observations: list[dict],
        corp_actions: list[dict],
        fixed_ts: datetime,
    ) -> None:
        a = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        b = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        assert a == b

    def test_empty_inputs(self, fixed_ts: datetime) -> None:
        result = build_graph_data([], [], [], generated_at=fixed_ts)
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["metadata"]["node_count"] == 0

    def test_company_with_only_corp_actions_included(
        self,
        fixed_ts: datetime,
    ) -> None:
        """A company with corp actions but no observations should still be included."""
        isin = "INE002A01018"
        sid = make_id("sec", {"isin": isin})
        isin_master = [{"id": make_id("isin", {"isin": isin}), "isin": isin, "nse_symbol": "RELIANCE",
                        "company_name": "Reliance", "sector": "Refineries", "exchange": "NSE"}]
        observations = []
        corp_actions = [{"security_id": sid, "action_type": "dividend"}]
        result = build_graph_data(isin_master, observations, corp_actions, generated_at=fixed_ts)
        company_nodes = [n for n in result["nodes"] if n["data"]["type"] == "company"]
        assert len(company_nodes) == 1
        assert company_nodes[0]["data"]["corporate_actions_count"] == 1
        assert company_nodes[0]["data"]["observations_count"] == 0

    def test_unclassified_sector_handled(self, fixed_ts: datetime) -> None:
        """Companies with no sector go into '(Unclassified)'."""
        isin = "INE002A01018"
        sid = make_id("sec", {"isin": isin})
        isin_master = [{"id": make_id("isin", {"isin": isin}), "isin": isin, "nse_symbol": "RELIANCE",
                        "company_name": "Reliance", "sector": None, "exchange": "NSE"}]
        observations = [{"subject_id": sid, "kind": "price_close", "value": 100}]
        result = build_graph_data(isin_master, observations, [], generated_at=fixed_ts)
        sector_nodes = [n for n in result["nodes"] if n["data"]["type"] == "sector"]
        assert len(sector_nodes) == 1
        assert sector_nodes[0]["data"]["label"] == "(Unclassified)"
