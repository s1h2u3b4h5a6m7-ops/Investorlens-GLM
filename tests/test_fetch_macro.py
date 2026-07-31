"""Integration tests for the macro fetcher scripts (RBI rates, RBI FX, MOSPI CPI).

Uses the fixture-as-cache trick: pre-place the fixture file in the cache
directory so the fetcher skips the network.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from investorlens.io import read_jsonl  # noqa: E402

# Import the fetcher modules by path
import importlib.util

_spec_rates = importlib.util.spec_from_file_location(
    "fetch_rbi_rates", ROOT / "scripts" / "fetchers" / "fetch_rbi_rates.py"
)
assert _spec_rates is not None and _spec_rates.loader is not None
fetch_rbi_rates = importlib.util.module_from_spec(_spec_rates)
_spec_rates.loader.exec_module(fetch_rbi_rates)

_spec_fx = importlib.util.spec_from_file_location(
    "fetch_rbi_fx", ROOT / "scripts" / "fetchers" / "fetch_rbi_fx.py"
)
assert _spec_fx is not None and _spec_fx.loader is not None
fetch_rbi_fx = importlib.util.module_from_spec(_spec_fx)
_spec_fx.loader.exec_module(fetch_rbi_fx)

_spec_cpi = importlib.util.spec_from_file_location(
    "fetch_mospi_cpi", ROOT / "scripts" / "fetchers" / "fetch_mospi_cpi.py"
)
assert _spec_cpi is not None and _spec_cpi.loader is not None
fetch_mospi_cpi = importlib.util.module_from_spec(_spec_cpi)
_spec_cpi.loader.exec_module(fetch_mospi_cpi)

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 10, 9, 13, 30, tzinfo=timezone.utc)


def _prepare_cache(
    fetcher_module,
    cache_subdir: str,
    fixture_name: str,
    date_str: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Pre-place a fixture in the cache directory, return the path to it."""
    cache_dir = tmp_path / "raw" / cache_subdir
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{date_str}.html" if fixture_name.endswith(".html") else cache_dir / f"{date_str}.csv"
    cache_path.write_text((FIXTURES / fixture_name).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(fetcher_module, "RAW_DIR", cache_dir)
    return cache_path


def _setup_output(
    fetcher_module,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    out = tmp_path / "observations.jsonl"
    monkeypatch.setattr(fetcher_module, "OUTPUT_PATH", out)
    return out


# ---------------------------------------------------------------------------
# RBI Policy Rates
# ---------------------------------------------------------------------------


class TestFetchRbiRates:
    def test_fetch_from_cache_produces_observations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_cache(fetch_rbi_rates, "rbi/policy_rates", "rbi_policy_rates.html", "2024-10-09", tmp_path, monkeypatch)
        out = _setup_output(fetch_rbi_rates, tmp_path, monkeypatch)

        rc = fetch_rbi_rates.fetch(date_str="2024-10-09")
        assert rc == 0
        records = read_jsonl(out)
        assert len(records) == 7  # 7 policy rates in the fixture

    def test_provenance(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _prepare_cache(fetch_rbi_rates, "rbi/policy_rates", "rbi_policy_rates.html", "2024-10-09", tmp_path, monkeypatch)
        out = _setup_output(fetch_rbi_rates, tmp_path, monkeypatch)

        rc = fetch_rbi_rates.fetch(date_str="2024-10-09")
        assert rc == 0
        records = read_jsonl(out)
        for r in records:
            assert r["provenance"]["source"] == "rbi"
            assert r["provenance"]["extraction_method"] == "html_scrape"
            assert r["provenance"]["confidence"] == "high"

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _prepare_cache(fetch_rbi_rates, "rbi/policy_rates", "rbi_policy_rates.html", "2024-10-09", tmp_path, monkeypatch)
        out = _setup_output(fetch_rbi_rates, tmp_path, monkeypatch)

        fixed_ts = datetime(2024, 10, 9, 13, 30, tzinfo=timezone.utc)
        original_dt = fetch_rbi_rates.datetime

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_ts if tz is not None else fixed_ts.replace(tzinfo=None)

        try:
            fetch_rbi_rates.datetime = _FrozenDatetime  # type: ignore[assignment]
            rc1 = fetch_rbi_rates.fetch(date_str="2024-10-09")
            assert rc1 == 0
            content1 = out.read_bytes()

            rc2 = fetch_rbi_rates.fetch(date_str="2024-10-09")
            assert rc2 == 0
            content2 = out.read_bytes()

            assert content1 == content2
        finally:
            fetch_rbi_rates.datetime = original_dt  # type: ignore[assignment]

    def test_no_cache_no_network_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_cache = tmp_path / "empty"
        empty_cache.mkdir()
        monkeypatch.setattr(fetch_rbi_rates, "RAW_DIR", empty_cache)
        out = _setup_output(fetch_rbi_rates, tmp_path, monkeypatch)

        from investorlens.io import FetchError

        class _FakeSession:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def get(self, *args, **kwargs): raise FetchError("network unavailable")

        monkeypatch.setattr(fetch_rbi_rates, "CachedSession", _FakeSession)

        rc = fetch_rbi_rates.fetch(date_str="2024-10-09")
        assert rc == 1
        assert not out.exists()


# ---------------------------------------------------------------------------
# RBI FX Reference Rates
# ---------------------------------------------------------------------------


class TestFetchRbiFx:
    def test_fetch_from_cache_produces_observations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_cache(fetch_rbi_fx, "rbi/fx_reference", "rbi_fx_reference.html", "2024-10-09", tmp_path, monkeypatch)
        out = _setup_output(fetch_rbi_fx, tmp_path, monkeypatch)

        rc = fetch_rbi_fx.fetch(date_str="2024-10-09")
        assert rc == 0
        records = read_jsonl(out)
        # 5 dates × 4 currencies = 20 observations
        assert len(records) == 20

    def test_specific_fx_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _prepare_cache(fetch_rbi_fx, "rbi/fx_reference", "rbi_fx_reference.html", "2024-10-09", tmp_path, monkeypatch)
        out = _setup_output(fetch_rbi_fx, tmp_path, monkeypatch)

        rc = fetch_rbi_fx.fetch(date_str="2024-10-09")
        assert rc == 0
        records = read_jsonl(out)
        # Find USD on 04-Oct-2024 = 84.0525
        from investorlens.ids import make_id
        usd_subject = make_id("drv", {"slug": "fx_usd_inr"})
        usd_obs = next(r for r in records if r["subject_id"] == usd_subject and r["as_of"] == "2024-10-04")
        assert usd_obs["value"] == 84.0525


# ---------------------------------------------------------------------------
# MOSPI CPI
# ---------------------------------------------------------------------------


class TestFetchMospiCpi:
    def test_fetch_from_cache_produces_observations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Use the CSV extension for MOSPI
        cache_dir = tmp_path / "raw" / "mospi" / "cpi"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "2024-10-14.csv"
        cache_path.write_text((FIXTURES / "mospi_cpi.csv").read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(fetch_mospi_cpi, "RAW_DIR", cache_dir)
        out = _setup_output(fetch_mospi_cpi, tmp_path, monkeypatch)

        rc = fetch_mospi_cpi.fetch(date_str="2024-10-14")
        assert rc == 0
        records = read_jsonl(out)
        # 14 rows × 6 indicators = 84 observations
        assert len(records) == 84

    def test_provenance(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cache_dir = tmp_path / "raw" / "mospi" / "cpi"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "2024-10-14.csv"
        cache_path.write_text((FIXTURES / "mospi_cpi.csv").read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(fetch_mospi_cpi, "RAW_DIR", cache_dir)
        out = _setup_output(fetch_mospi_cpi, tmp_path, monkeypatch)

        rc = fetch_mospi_cpi.fetch(date_str="2024-10-14")
        assert rc == 0
        records = read_jsonl(out)
        for r in records:
            assert r["provenance"]["source"] == "mospi"
            assert r["provenance"]["extraction_method"] == "bulk_download"
            assert r["provenance"]["confidence"] == "high"

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cache_dir = tmp_path / "raw" / "mospi" / "cpi"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "2024-10-14.csv"
        cache_path.write_text((FIXTURES / "mospi_cpi.csv").read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(fetch_mospi_cpi, "RAW_DIR", cache_dir)
        out = _setup_output(fetch_mospi_cpi, tmp_path, monkeypatch)

        fixed_ts = datetime(2024, 10, 14, 18, 0, tzinfo=timezone.utc)
        original_dt = fetch_mospi_cpi.datetime

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_ts if tz is not None else fixed_ts.replace(tzinfo=None)

        try:
            fetch_mospi_cpi.datetime = _FrozenDatetime  # type: ignore[assignment]
            rc1 = fetch_mospi_cpi.fetch(date_str="2024-10-14")
            assert rc1 == 0
            content1 = out.read_bytes()
            rc2 = fetch_mospi_cpi.fetch(date_str="2024-10-14")
            assert rc2 == 0
            content2 = out.read_bytes()
            assert content1 == content2
        finally:
            fetch_mospi_cpi.datetime = original_dt  # type: ignore[assignment]
