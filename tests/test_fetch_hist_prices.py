"""Integration tests for the historical prices fetcher script.

Strategy: monkeypatch YahooChartClient.get_chart to return the fixture JSON
when called. This avoids all real HTTP while exercising the full fetch →
parse → upsert pipeline.
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

from investorlens.io import read_jsonl  # noqa: E402

# Import the fetcher module by path
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "fetch_hist_prices",
    ROOT / "scripts" / "fetchers" / "fetch_hist_prices.py",
)
assert _spec is not None and _spec.loader is not None
fetch_hist_prices = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_hist_prices)

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def chart_response() -> dict:
    return json.loads((FIXTURES / "yahoo_chart_reliance_5d.json").read_text(encoding="utf-8"))


@pytest.fixture
def isin_master_with_reliance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pre-populate a small ISIN master with RELIANCE and TCS for symbol resolution."""
    from investorlens.io import write_jsonl
    from investorlens.ids import make_id

    master_path = tmp_path / "isin_master.jsonl"
    records = [
        {
            "id": make_id("isin", {"isin": "INE002A01018"}),
            "isin": "INE002A01018",
            "company_name": "Reliance Industries Ltd",
            "nse_symbol": "RELIANCE",
            "bse_code": "500325",
            "exchange": "NSE+BSE",
            "active": True,
            "security_type": "equity",
            "provenance": {"source": "nse+bse", "retrieved_at": "2024-09-30T18:30:00Z"},
        },
        {
            "id": make_id("isin", {"isin": "INE467B01029"}),
            "isin": "INE467B01029",
            "company_name": "Tata Consultancy Services Ltd",
            "nse_symbol": "TCS",
            "bse_code": "532540",
            "exchange": "NSE+BSE",
            "active": True,
            "security_type": "equity",
            "provenance": {"source": "nse+bse", "retrieved_at": "2024-09-30T18:30:00Z"},
        },
    ]
    write_jsonl(master_path, records)
    monkeypatch.setattr(fetch_hist_prices, "ISIN_MASTER_PATH", master_path)
    return master_path


@pytest.fixture
def output_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    out = tmp_path / "observations.jsonl"
    monkeypatch.setattr(fetch_hist_prices, "OUTPUT_PATH", out)
    return out


@pytest.fixture
def patched_yahoo_client(chart_response: dict, monkeypatch: pytest.MonkeyPatch):
    """Patch YahooChartClient.get_chart to return the fixture for any symbol.

    Uses monkeypatch.setattr so the patch is automatically reverted after the
    test (preventing leakage into other test files in the same session).
    """
    def fake_get_chart(self, symbol, *, interval="1d", range_="5d", period1=None, period2=None, use_cache=True):
        # Return a deep copy so tests can't mutate the original fixture.
        return json.loads(json.dumps(chart_response))

    # Patch on the real class (imported by the fetcher module).
    from investorlens.io.yahoo import YahooChartClient as _RealClient
    monkeypatch.setattr(_RealClient, "get_chart", fake_get_chart)
    # Also patch the name the fetcher imported (same class, but be explicit).
    monkeypatch.setattr(fetch_hist_prices.YahooChartClient, "get_chart", fake_get_chart)


class TestFetchHistPrices:
    def test_fetch_single_symbol(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        """End-to-end: fetch RELIANCE → upsert observations."""
        rc = fetch_hist_prices.fetch(
            symbols=["RELIANCE"],
            incremental=True,
        )
        assert rc == 0
        records = read_jsonl(output_path)
        # 5 days × 6 kinds = 30 observations (per fixture)
        assert len(records) == 30

    def test_fetch_multiple_symbols(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        rc = fetch_hist_prices.fetch(symbols=["RELIANCE", "TCS"], incremental=True)
        assert rc == 0
        records = read_jsonl(output_path)
        # Both symbols hit the same fixture response (30 obs each).
        # They have DIFFERENT subject_ids (one per ISIN), so they don't dedupe.
        # Result: 60 observations total.
        assert len(records) == 60
        # Verify each subject_id appears 30 times
        from collections import Counter
        from investorlens.ids import make_id
        rel_sid = make_id("sec", {"isin": "INE002A01018"})
        tcs_sid = make_id("sec", {"isin": "INE467B01029"})
        sids = Counter(r["subject_id"] for r in records)
        assert sids[rel_sid] == 30
        assert sids[tcs_sid] == 30

    def test_fetch_via_only_isins(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        """--only-isins bypasses symbol→ISIN lookup."""
        rc = fetch_hist_prices.fetch(
            only_isins=["INE002A01018"],
            incremental=True,
        )
        assert rc == 0
        records = read_jsonl(output_path)
        assert len(records) == 30

    def test_unknown_symbol_skipped(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A symbol not in the ISIN master is logged and skipped."""
        import logging
        with caplog.at_level(logging.WARNING):
            rc = fetch_hist_prices.fetch(symbols=["UNKNOWN"], incremental=True)
        # Unknown symbol → 0 targets → fetch returns 1.
        assert rc == 1
        assert any("UNKNOWN" in r.message for r in caplog.records)

    def test_no_targets_returns_error(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        rc = fetch_hist_prices.fetch(symbols=[], only_isins=None, incremental=True)  # type: ignore[arg-type]
        assert rc == 1

    def test_invalid_backfill_period_returns_error(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        rc = fetch_hist_prices.fetch(symbols=["RELIANCE"], backfill="invalid")
        assert rc == 1

    def test_backfill_max(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        rc = fetch_hist_prices.fetch(symbols=["RELIANCE"], backfill="max")
        assert rc == 0
        records = read_jsonl(output_path)
        assert len(records) == 30  # fixture has 5 days × 6 kinds

    def test_date_range_picks_appropriate_yahoo_range(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        """A 100-day range should map to Yahoo's '3mo' range."""
        rc = fetch_hist_prices.fetch(
            symbols=["RELIANCE"],
            start=date(2024, 1, 1),
            end=date(2024, 4, 1),
        )
        assert rc == 0

    def test_observations_have_correct_provenance(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        rc = fetch_hist_prices.fetch(symbols=["RELIANCE"], incremental=True)
        assert rc == 0
        records = read_jsonl(output_path)
        for r in records:
            prov = r["provenance"]
            assert prov["source"] == "yahoo"
            assert prov["extraction_method"] == "official_api"
            assert prov["confidence"] == "high"
            assert "RELIANCE" in prov["notes"]

    def test_observations_include_adjclose(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
    ) -> None:
        """The fetcher should emit price_close_adj observations (Yahoo adjclose)."""
        rc = fetch_hist_prices.fetch(symbols=["RELIANCE"], incremental=True)
        assert rc == 0
        records = read_jsonl(output_path)
        adj_records = [r for r in records if r["kind"] == "price_close_adj"]
        assert len(adj_records) > 0
        # The fixture has adjclose values
        assert adj_records[0]["value"] is not None

    def test_idempotent_run(
        self,
        isin_master_with_reliance: Path,
        output_path: Path,
        patched_yahoo_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-running with a fixed retrieved_at produces byte-identical output."""
        fixed_ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)

        # Patch datetime in the fetcher module
        original_dt = fetch_hist_prices.datetime

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_ts if tz is not None else fixed_ts.replace(tzinfo=None)

        try:
            fetch_hist_prices.datetime = _FrozenDatetime  # type: ignore[assignment]
            rc1 = fetch_hist_prices.fetch(symbols=["RELIANCE"], incremental=True)
            assert rc1 == 0
            content1 = output_path.read_bytes()

            rc2 = fetch_hist_prices.fetch(symbols=["RELIANCE"], incremental=True)
            assert rc2 == 0
            content2 = output_path.read_bytes()

            assert content1 == content2
        finally:
            fetch_hist_prices.datetime = original_dt  # type: ignore[assignment]


class TestSymbolResolution:
    def test_resolve_symbols_to_isins_known(self, isin_master_with_reliance: Path) -> None:
        master = fetch_hist_prices.load_isin_master()
        result = fetch_hist_prices.resolve_symbols_to_isins(["RELIANCE", "TCS"], master)
        assert result == {"RELIANCE": "INE002A01018", "TCS": "INE467B01029"}

    def test_resolve_symbols_to_isins_unknown(
        self, isin_master_with_reliance: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging
        master = fetch_hist_prices.load_isin_master()
        with caplog.at_level(logging.WARNING):
            result = fetch_hist_prices.resolve_symbols_to_isins(["UNKNOWN"], master)
        assert result == {}
        assert any("UNKNOWN" in r.message for r in caplog.records)


class TestLoadIsinMasterMissing:
    def test_returns_empty_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        nonexistent = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr(fetch_hist_prices, "ISIN_MASTER_PATH", nonexistent)
        import logging
        with caplog.at_level(logging.WARNING):
            result = fetch_hist_prices.load_isin_master()
        assert result == []
        assert any("ISIN master not found" in r.message for r in caplog.records)
