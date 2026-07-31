"""Integration tests for the corp actions fetcher + adjusted-prices builder.

Both scripts are tested via the fixture-as-cache trick: pre-place the fixture
CSV in the cache directory so the fetcher skips the network.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from investorlens.io import read_jsonl  # noqa: E402

# Import the fetcher module by path
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "fetch_corp_actions",
    ROOT / "scripts" / "fetchers" / "fetch_corp_actions.py",
)
assert _spec is not None and _spec.loader is not None
fetch_corp_actions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_corp_actions)

# Import the builder module by path
_spec2 = importlib.util.spec_from_file_location(
    "build_adjusted_prices",
    ROOT / "scripts" / "builders" / "build_adjusted_prices.py",
)
assert _spec2 is not None and _spec2.loader is not None
build_adjusted_prices_script = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(build_adjusted_prices_script)

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def isin_master_records() -> list[dict]:
    return [
        {"isin": "INE002A01018", "nse_symbol": "RELIANCE"},
        {"isin": "INE467B01029", "nse_symbol": "TCS"},
        {"isin": "INE009A01021", "nse_symbol": "INFY"},
        {"isin": "INE044A01026", "nse_symbol": "SUNPHARMA"},
        {"isin": "INE040A01034", "nse_symbol": "HDFCBANK"},
        {"isin": "INE075A01022", "nse_symbol": "WIPRO"},
        {"isin": "INE030A01027", "nse_symbol": "HINDUNILVR"},
        {"isin": "INE000A00001", "nse_symbol": "SYMBOLCHANGE"},
        {"isin": "INE000A00002", "nse_symbol": "MERGERTEST"},
    ]


@pytest.fixture
def prepared_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isin_master_records: list[dict],
) -> Path:
    """Set up an isolated workspace with ISIN master + corp-actions cache pre-populated."""
    # Redirect all paths the fetcher/builder use to a tmp dir.
    cache_dir = tmp_path / "raw" / "nse" / "corpact"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Pre-place the fixture CSV in the cache.
    fixture_csv = (FIXTURES / "nse_corpact.csv").read_text(encoding="utf-8")
    cache_path = cache_dir / "2024-09-30.csv"
    cache_path.write_text(fixture_csv, encoding="utf-8")

    # Write a small ISIN master.
    from investorlens.io import write_jsonl
    from investorlens.ids import make_id
    isin_master_path = tmp_path / "isin_master.jsonl"
    write_jsonl(isin_master_path, [
        {**r, "id": make_id("isin", {"isin": r["isin"]}),
         "company_name": r["nse_symbol"], "exchange": "NSE", "active": True,
         "security_type": "equity",
         "provenance": {"source": "nse", "retrieved_at": "2024-09-30T18:30:00Z"}}
        for r in isin_master_records
    ])

    # Empty observations file (will be populated by the builder test).
    obs_path = tmp_path / "observations.jsonl"
    obs_path.write_text("", encoding="utf-8")

    ca_output_path = tmp_path / "corporate_actions.jsonl"
    ca_output_path.write_text("", encoding="utf-8")

    # Patch the modules' path constants.
    monkeypatch.setattr(fetch_corp_actions, "RAW_DIR", cache_dir)
    monkeypatch.setattr(fetch_corp_actions, "ISIN_MASTER_PATH", isin_master_path)
    monkeypatch.setattr(fetch_corp_actions, "OUTPUT_PATH", ca_output_path)
    monkeypatch.setattr(build_adjusted_prices_script, "OBS_PATH", obs_path)
    monkeypatch.setattr(build_adjusted_prices_script, "CA_PATH", ca_output_path)

    return tmp_path


# ---------------------------------------------------------------------------
# Fetcher tests
# ---------------------------------------------------------------------------


class TestFetchCorpActions:
    def test_fetch_from_cache_produces_records(
        self,
        prepared_workspace: Path,
    ) -> None:
        """End-to-end: cached CSV → parse → upsert → 12 corp actions."""
        rc = fetch_corp_actions.fetch(date_str="2024-09-30")
        assert rc == 0

        ca_path = prepared_workspace / "corporate_actions.jsonl"
        records = read_jsonl(ca_path)
        # Fixture has 13 rows; UNKNOWNCO not in ISIN master → skipped; 12 records.
        assert len(records) == 12

    def test_fetch_idempotent_on_second_run(
        self,
        prepared_workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With frozen datetime, re-running produces byte-identical output."""
        fixed_ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)

        original_dt = fetch_corp_actions.datetime

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_ts if tz is not None else fixed_ts.replace(tzinfo=None)

        try:
            fetch_corp_actions.datetime = _FrozenDatetime  # type: ignore[assignment]
            rc1 = fetch_corp_actions.fetch(date_str="2024-09-30")
            assert rc1 == 0
            ca_path = prepared_workspace / "corporate_actions.jsonl"
            content1 = ca_path.read_bytes()

            rc2 = fetch_corp_actions.fetch(date_str="2024-09-30")
            assert rc2 == 0
            content2 = ca_path.read_bytes()

            assert content1 == content2
        finally:
            fetch_corp_actions.datetime = original_dt  # type: ignore[assignment]

    def test_action_types_present(
        self,
        prepared_workspace: Path,
    ) -> None:
        rc = fetch_corp_actions.fetch(date_str="2024-09-30")
        assert rc == 0
        ca_path = prepared_workspace / "corporate_actions.jsonl"
        records = read_jsonl(ca_path)
        types = {r["action_type"] for r in records}
        assert "dividend" in types
        assert "split" in types
        assert "bonus" in types
        assert "merger" in types
        assert "symbol_change" in types

    def test_provenance_attached(
        self,
        prepared_workspace: Path,
    ) -> None:
        rc = fetch_corp_actions.fetch(date_str="2024-09-30")
        assert rc == 0
        ca_path = prepared_workspace / "corporate_actions.jsonl"
        records = read_jsonl(ca_path)
        for r in records:
            prov = r["provenance"]
            assert prov["source"] == "nse"
            assert prov["extraction_method"] == "bulk_download"
            assert prov["confidence"] == "high"


# ---------------------------------------------------------------------------
# Builder tests (full pipeline: observations + corp actions → adjusted prices)
# ---------------------------------------------------------------------------


class TestBuildAdjustedPricesScript:
    def test_build_with_no_observations_returns_error(
        self,
        prepared_workspace: Path,
    ) -> None:
        """No price_close observations → builder returns 1."""
        # First, fetch corp actions so the file exists.
        rc = fetch_corp_actions.fetch(date_str="2024-09-30")
        assert rc == 0
        # observations.jsonl is empty.
        rc = build_adjusted_prices_script.build()
        assert rc == 1

    def test_build_with_prices_and_corp_actions(
        self,
        prepared_workspace: Path,
    ) -> None:
        """End-to-end: corp actions + price_close observations → adjusted prices upserted."""
        # 1. Fetch corp actions.
        rc = fetch_corp_actions.fetch(date_str="2024-09-30")
        assert rc == 0

        # 2. Write some price_close observations to observations.jsonl.
        # Use SUNPHARMA which has a split (Rs.10 → Rs.1, i.e. 10:1) on 20-DEC-2023.
        # Pre-split price ~ 1000; post-split price ~ 100.
        from investorlens.ids import make_id
        from investorlens.io import write_jsonl
        sunpharma_sid = make_id("sec", {"isin": "INE044A01026"})
        obs_path = prepared_workspace / "observations.jsonl"
        write_jsonl(obs_path, [
            {
                "id": make_id("obs", {"subject_id": sunpharma_sid, "kind": "price_close",
                                       "period": "2023-12-15", "as_of": "2023-12-15",
                                       "source_id": "nse"}),
                "subject_id": sunpharma_sid,
                "kind": "price_close",
                "period": "2023-12-15",
                "as_of": "2023-12-15",
                "value": 1000.0,
                "unit": "INR/share",
                "currency": "INR",
                "data_status": "observed",
                "confidence": "high",
                "provenance": {"source": "nse", "extraction_method": "bulk_download",
                               "retrieved_at": "2024-09-30T18:30:00Z"},
            },
            {
                "id": make_id("obs", {"subject_id": sunpharma_sid, "kind": "price_close",
                                       "period": "2024-01-15", "as_of": "2024-01-15",
                                       "source_id": "nse"}),
                "subject_id": sunpharma_sid,
                "kind": "price_close",
                "period": "2024-01-15",
                "as_of": "2024-01-15",
                "value": 100.0,
                "unit": "INR/share",
                "currency": "INR",
                "data_status": "observed",
                "confidence": "high",
                "provenance": {"source": "nse", "extraction_method": "bulk_download",
                               "retrieved_at": "2024-09-30T18:30:00Z"},
            },
        ])

        # 3. Run the builder.
        rc = build_adjusted_prices_script.build(
            retrieved_at=datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc),
        )
        assert rc == 0

        # 4. Verify adjusted prices were upserted.
        records = read_jsonl(obs_path)
        # 2 raw + 2 adjusted = 4
        assert len(records) == 4

        adj_records = [r for r in records if r["kind"] == "price_close_adj"]
        assert len(adj_records) == 2

        # Check provenance: source="investorlens", extraction_method="derived"
        for r in adj_records:
            assert r["provenance"]["source"] == "investorlens"
            assert r["provenance"]["extraction_method"] == "derived"
            # Decomposition should be in notes
            assert r["provenance"]["notes"] is not None

        # Check the actual adjusted values:
        # SUNPHARMA split was 10:1 on 20-DEC-2023.
        # Day 2023-12-15 (before split): raw=1000, factor=10 → adj=100
        # Day 2024-01-15 (after split): raw=100, factor=1 → adj=100
        by_date = {r["as_of"]: r["value"] for r in adj_records}
        assert by_date["2023-12-15"] == 100.0
        assert by_date["2024-01-15"] == 100.0

    def test_build_idempotent(
        self,
        prepared_workspace: Path,
    ) -> None:
        """Re-running the builder with fixed retrieved_at produces byte-identical output."""
        # Setup same as above
        rc = fetch_corp_actions.fetch(date_str="2024-09-30")
        assert rc == 0

        from investorlens.ids import make_id
        from investorlens.io import write_jsonl
        sunpharma_sid = make_id("sec", {"isin": "INE044A01026"})
        obs_path = prepared_workspace / "observations.jsonl"
        write_jsonl(obs_path, [
            {
                "id": make_id("obs", {"subject_id": sunpharma_sid, "kind": "price_close",
                                       "period": "2023-12-15", "as_of": "2023-12-15",
                                       "source_id": "nse"}),
                "subject_id": sunpharma_sid,
                "kind": "price_close",
                "period": "2023-12-15",
                "as_of": "2023-12-15",
                "value": 1000.0,
                "unit": "INR/share",
                "currency": "INR",
                "data_status": "observed",
                "confidence": "high",
                "provenance": {"source": "nse", "extraction_method": "bulk_download",
                               "retrieved_at": "2024-09-30T18:30:00Z"},
            },
        ])

        fixed_ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)

        rc1 = build_adjusted_prices_script.build(retrieved_at=fixed_ts)
        assert rc1 == 0
        content1 = obs_path.read_bytes()

        rc2 = build_adjusted_prices_script.build(retrieved_at=fixed_ts)
        assert rc2 == 0
        content2 = obs_path.read_bytes()

        assert content1 == content2
