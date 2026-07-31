"""Tests for the MOSPI CPI parser (investorlens.parsers.mospi)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investorlens.parsers import mospi
from investorlens.parsers.mospi import normalize_cpi_row_keys, parse_cpi_csv
from investorlens.models import ObservationKind
from investorlens.ids import make_id

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def csv_text() -> str:
    return (FIXTURES / "mospi_cpi.csv").read_text(encoding="utf-8")


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 10, 14, 18, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# normalize_cpi_row_keys
# ---------------------------------------------------------------------------


class TestNormalizeCpiRowKeys:
    def test_canonical_aliases(self) -> None:
        row = {
            "Year": "2024",
            "Month": "September",
            "Combined Rural+Urban Index": "191.5",
            "Combined YoY %": "5.10",
        }
        out = normalize_cpi_row_keys(row)
        assert out == {
            "year": "2024",
            "month": "September",
            "combined_index": "191.5",
            "combined_yoy": "5.10",
        }

    def test_unknown_keys_preserved_lowercase(self) -> None:
        row = {"Year": "2024", "Some Weird Column": "x"}
        out = normalize_cpi_row_keys(row)
        assert "some weird column" in out
        assert out["year"] == "2024"


# ---------------------------------------------------------------------------
# parse_cpi_csv
# ---------------------------------------------------------------------------


class TestParseCpiCsv:
    def test_parses_all_rows(self, csv_text: str, fixed_ts: datetime) -> None:
        """14 rows × 6 indicators = 84 observations."""
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        assert len(obs) == 84

    def test_observation_fields(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        for o in obs:
            assert o.subject_id.startswith("drv_")
            assert o.data_status.value == "observed"
            assert o.currency is None

    def test_yoy_uses_correct_kind(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        yoy_obs = [o for o in obs if o.kind == ObservationKind.CPI_YOY]
        index_obs = [o for o in obs if o.kind == ObservationKind.OTHER]
        # 14 rows × 3 YoY fields (combined, rural, urban) = 42
        assert len(yoy_obs) == 42
        # 14 rows × 3 index fields = 42
        assert len(index_obs) == 42

    def test_specific_combined_yoy_value(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        combined_subject = make_id("drv", {"slug": "cpi_combined_yoy"})
        # September 2024 value is 5.10
        sep_obs = next(
            o for o in obs
            if o.subject_id == combined_subject and o.period == "2024-09"
        )
        assert sep_obs.value == 5.10
        assert sep_obs.unit == "%"
        assert sep_obs.kind == ObservationKind.CPI_YOY
        assert sep_obs.as_of == date(2024, 9, 1)

    def test_specific_index_value(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        combined_idx_subject = make_id("drv", {"slug": "cpi_combined_index"})
        sep_obs = next(
            o for o in obs
            if o.subject_id == combined_idx_subject and o.period == "2024-09"
        )
        assert sep_obs.value == 191.5
        assert sep_obs.unit == "index"
        assert sep_obs.kind == ObservationKind.OTHER

    def test_period_is_year_month_format(self, csv_text: str, fixed_ts: datetime) -> None:
        """period should be 'YYYY-MM' format."""
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        for o in obs:
            assert len(o.period) == 7  # "2024-09"
            assert o.period[4] == "-"

    def test_as_of_is_first_of_month(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        for o in obs:
            assert o.as_of.day == 1

    def test_provenance_attached(self, csv_text: str, fixed_ts: datetime) -> None:
        url = "https://mospi.gov.in/web/mospi/cpi-publications"
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts, source_url=url)
        prov = obs[0].provenance
        assert prov.source == "mospi"
        assert prov.extraction_method.value == "bulk_download"
        assert prov.confidence.value == "high"
        assert prov.retrieved_at == fixed_ts
        assert str(prov.source_url) == url

    def test_id_deterministic(self, csv_text: str, fixed_ts: datetime) -> None:
        a = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        b = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        assert [o.id for o in a] == [o.id for o in b]

    def test_id_includes_subject_kind_period(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        keys = {(o.subject_id, o.kind.value, o.period) for o in obs}
        assert len(keys) == len(obs)

    def test_output_sorted(self, csv_text: str, fixed_ts: datetime) -> None:
        obs = parse_cpi_csv(csv_text, retrieved_at=fixed_ts)
        keys = [(o.subject_id, o.kind.value, o.as_of.isoformat()) for o in obs]
        assert keys == sorted(keys)

    def test_skips_rows_missing_year_or_month(self) -> None:
        text = (
            "Year,Month,Combined YoY %\n"
            "2024,September,5.10\n"
            ",September,4.50\n"      # missing year
            "2024,,5.10\n"            # missing month
            "2024,October,4.80\n"
        )
        obs = parse_cpi_csv(text, retrieved_at=datetime(2024, 10, 14, tzinfo=timezone.utc))
        assert len(obs) == 2  # only September and October rows

    def test_empty_csv_returns_empty(self, fixed_ts: datetime) -> None:
        text = "Year,Month,Combined YoY %\n"
        obs = parse_cpi_csv(text, retrieved_at=fixed_ts)
        assert obs == []

    def test_handles_numeric_month(self) -> None:
        """Months can be given as numbers (1-12) or names."""
        text = (
            "Year,Month,Combined YoY %\n"
            "2024,9,5.10\n"
            "2024,10,4.80\n"
        )
        obs = parse_cpi_csv(text, retrieved_at=datetime(2024, 10, 14, tzinfo=timezone.utc))
        assert len(obs) == 2
        periods = {o.period for o in obs}
        assert periods == {"2024-09", "2024-10"}

    def test_handles_month_abbreviations(self) -> None:
        """Months like 'Sep' or 'Sept' should be parsed correctly."""
        text = (
            "Year,Month,Combined YoY %\n"
            "2024,Sep,5.10\n"
            "2024,Sept,5.10\n"  # alternate abbreviation
        )
        obs = parse_cpi_csv(text, retrieved_at=datetime(2024, 10, 14, tzinfo=timezone.utc))
        # Both rows map to September → deduplicated by (subject, kind, period)
        assert len(obs) == 1
        assert obs[0].period == "2024-09"
