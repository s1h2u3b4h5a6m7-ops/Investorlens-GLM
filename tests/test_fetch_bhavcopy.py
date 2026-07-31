"""Integration tests for the bhavcopy fetcher script.

These tests verify the full fetch → extract → parse → upsert pipeline
WITHOUT hitting the network. We do this by:

  1. Pre-populating the raw-zip cache directory with a real zip built from
     our fixture CSV.
  2. Calling fetch_bhavcopy.fetch(date) directly — it will see the cached
     zip, skip the network, and run the parser + upsert path.

This gives us end-to-end coverage of:
  - zip extraction (modern format zip → CSV)
  - parser integration (CSV → Observations)
  - upsert idempotency (Observations → observations.jsonl)
  - file outputs (cache layout, processed/observations.jsonl)
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

# Make scripts/ importable
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from investorlens.io import read_jsonl  # noqa: E402

# Import the fetcher module by path
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "fetch_bhavcopy",
    ROOT / "scripts" / "fetchers" / "fetch_bhavcopy.py",
)
assert _spec is not None and _spec.loader is not None
fetch_bhavcopy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_bhavcopy)

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def fixed_trade_date() -> date:
    return date(2024, 9, 30)


@pytest.fixture
def cached_zip(fixed_trade_date: date, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Pre-place a real zip (containing the modern fixture CSV) in the cache dir.

    The fetcher checks `RAW_DIR / f"{trade_date.isoformat()}.zip"` first; if it
    exists, it skips the network. We monkeypatch `RAW_DIR` to a tmp_path so we
    don't pollute the real cache.
    """
    cache_dir = tmp_path / "raw" / "nse" / "bhavcopy"
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / f"{fixed_trade_date.isoformat()}.zip"

    csv_text = (FIXTURES / "bhavcopy_modern.csv").read_text(encoding="utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("BhavCopy_NSE_CM_0_0_20240930_F_0000.csv", csv_text)
    zip_path.write_bytes(buf.getvalue())

    # Redirect the fetcher's RAW_DIR constant to our temp dir.
    monkeypatch.setattr(fetch_bhavcopy, "RAW_DIR", cache_dir)
    return zip_path


@pytest.fixture
def output_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the fetcher's OUTPUT_PATH to a temp file so tests don't pollute the real one."""
    out = tmp_path / "observations.jsonl"
    monkeypatch.setattr(fetch_bhavcopy, "OUTPUT_PATH", out)
    return out


class TestFetchBhavcopy:
    def test_fetch_from_cache_produces_observations(
        self,
        cached_zip: Path,
        output_path: Path,
        fixed_trade_date: date,
    ) -> None:
        """End-to-end: cached zip → parse → upsert → 36 observations in output."""
        rc = fetch_bhavcopy.fetch(fixed_trade_date)
        assert rc == 0

        records = read_jsonl(output_path)
        # 6 ISINs × 6 observations = 36
        assert len(records) == 36

    def test_fetch_idempotent_on_second_run(
        self,
        cached_zip: Path,
        output_path: Path,
        fixed_trade_date: date,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-running fetch on the same date with a fixed `retrieved_at` should
        produce byte-identical output across runs.

        We patch the `datetime` class in BOTH the bhavcopy parser AND the
        fetcher module so that `datetime.now(utc)` returns a fixed timestamp
        on every call. (Without patching the fetcher's `datetime`, its
        `retrieved_at = datetime.now(timezone.utc)` line produces a fresh
        real timestamp on each run, breaking idempotency.)
        """
        fixed_ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)

        import investorlens.parsers.bhavcopy as bp

        original_parser_dt = bp.datetime
        original_fetcher_dt = fetch_bhavcopy.datetime

        class _FrozenDatetime(datetime):
            """A datetime subclass where .now() always returns the fixed timestamp.
            All other classmethods/behavior are inherited from real datetime.
            """
            @classmethod
            def now(cls, tz=None):
                return fixed_ts if tz is not None else fixed_ts.replace(tzinfo=None)

        try:
            bp.datetime = _FrozenDatetime  # type: ignore[assignment]
            fetch_bhavcopy.datetime = _FrozenDatetime  # type: ignore[assignment]

            rc1 = fetch_bhavcopy.fetch(fixed_trade_date)
            assert rc1 == 0
            content1 = output_path.read_bytes()

            rc2 = fetch_bhavcopy.fetch(fixed_trade_date)
            assert rc2 == 0
            content2 = output_path.read_bytes()

            assert content1 == content2
        finally:
            bp.datetime = original_parser_dt  # type: ignore[assignment]
            fetch_bhavcopy.datetime = original_fetcher_dt  # type: ignore[assignment]

    def test_only_isins_filter(
        self,
        cached_zip: Path,
        output_path: Path,
        fixed_trade_date: date,
    ) -> None:
        """Filtering to 2 ISINs should produce 12 observations (2 × 6)."""
        rc = fetch_bhavcopy.fetch(
            fixed_trade_date,
            only_isins={"INE002A01018", "INE467B01029"},
        )
        assert rc == 0
        records = read_jsonl(output_path)
        assert len(records) == 12

    def test_observation_kinds_present_in_output(
        self,
        cached_zip: Path,
        output_path: Path,
        fixed_trade_date: date,
    ) -> None:
        rc = fetch_bhavcopy.fetch(fixed_trade_date)
        assert rc == 0
        records = read_jsonl(output_path)
        kinds = {r["kind"] for r in records}
        assert kinds == {
            "price_open", "price_high", "price_low", "price_close",
            "volume", "turnover",
        }

    def test_provenance_attached_to_observations(
        self,
        cached_zip: Path,
        output_path: Path,
        fixed_trade_date: date,
    ) -> None:
        rc = fetch_bhavcopy.fetch(fixed_trade_date)
        assert rc == 0
        records = read_jsonl(output_path)
        for r in records:
            prov = r["provenance"]
            assert prov["source"] == "nse"
            assert prov["extraction_method"] == "bulk_download"
            assert prov["confidence"] == "high"

    def test_no_cached_zip_returns_error(
        self,
        output_path: Path,
        fixed_trade_date: date,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """If no cached zip AND the network is unreachable, fetch should return 1.

        We simulate this by pointing RAW_DIR at an empty tmp dir and
        monkeypatching CachedSession.get to always raise FetchError.
        """
        empty_cache = tmp_path / "empty"
        empty_cache.mkdir()
        monkeypatch.setattr(fetch_bhavcopy, "RAW_DIR", empty_cache)

        from investorlens.io import FetchError

        class _FakeSession:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def get(self, *args, **kwargs): raise FetchError("network unavailable in test")

        monkeypatch.setattr(fetch_bhavcopy, "CachedSession", _FakeSession)

        rc = fetch_bhavcopy.fetch(fixed_trade_date)
        assert rc == 1
        # Output file should not exist
        assert not output_path.exists()

    def test_real_zip_extraction_works(self, tmp_path: Path) -> None:
        """Verify the zip extraction helper works with a real zip file."""
        csv_text = (FIXTURES / "bhavcopy_modern.csv").read_text(encoding="utf-8")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.csv", csv_text)
        zip_bytes = buf.getvalue()

        extracted = fetch_bhavcopy._extract_csv_from_zip(zip_bytes)
        assert extracted == csv_text

    def test_url_construction(self, fixed_trade_date: date) -> None:
        """Verify URL templates are filled in correctly for a known date."""
        urls = fetch_bhavcopy._build_urls(fixed_trade_date)
        # Modern format
        assert "BhavCopy_NSE_CM_0_0_20240930_F_0000.csv.zip" in urls[0]
        # Legacy format
        assert "cm30SEP2024bhav.csv.zip" in urls[1]
