"""Tests for the company notes builder (investorlens.builders.notes)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from investorlens.builders.notes import (
    build_company_note,
    format_corporate_actions_table,
    format_date,
    format_decimal,
    format_observations_table,
    slugify_company,
)
from investorlens.models import (
    CorporateAction,
    CorporateActionType,
    Observation,
    ObservationKind,
    Provenance,
)
from investorlens.models.provenance import Confidence, ExtractionMethod


@pytest.fixture
def prov() -> Provenance:
    return Provenance(
        source="nse",
        extraction_method=ExtractionMethod.BULK_DOWNLOAD,
        confidence=Confidence.HIGH,
        reporting_period="current",
    )


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def reliance_company() -> dict:
    """A canonical company record for Reliance Industries."""
    return {
        "id": "isin_4b938dc3a59d",
        "isin": "INE002A01018",
        "nse_symbol": "RELIANCE",
        "bse_code": "500325",
        "company_name": "Reliance Industries Limited",
        "sector": "Refineries",
        "industry": "Oil & Gas",
        "exchange": "NSE+BSE",
        "security_type": "equity",
        "face_value": "10.00",
        "active": True,
        "effective_from": "1995-01-11",
        "provenance": {"source": "nse+bse", "retrieved_at": "2024-09-30T18:30:00Z"},
    }


def _make_close_obs(
    subject_id: str,
    as_of: date,
    value: float,
    *,
    source: str = "nse",
    kind: ObservationKind = ObservationKind.PRICE_CLOSE,
) -> Observation:
    return Observation(
        subject_id=subject_id,
        kind=kind,
        period=as_of.isoformat(),
        as_of=as_of,
        value=value,
        unit="INR/share",
        currency="INR",
        provenance=Provenance(source=source, extraction_method=ExtractionMethod.BULK_DOWNLOAD),
    )


def _make_volume_obs(
    subject_id: str,
    as_of: date,
    value: float,
) -> Observation:
    return Observation(
        subject_id=subject_id,
        kind=ObservationKind.VOLUME,
        period=as_of.isoformat(),
        as_of=as_of,
        value=value,
        unit="shares",
        provenance=Provenance(source="nse", extraction_method=ExtractionMethod.BULK_DOWNLOAD),
    )


def _make_ca(
    security_id: str,
    action_type: CorporateActionType,
    ex_date: date,
    *,
    ratio_numerator: float | None = None,
    ratio_denominator: float | None = None,
    amount_per_share: Decimal | None = None,
) -> CorporateAction:
    return CorporateAction(
        security_id=security_id,
        action_type=action_type,
        ex_date=ex_date,
        ratio_numerator=ratio_numerator,
        ratio_denominator=ratio_denominator,
        amount_per_share=amount_per_share,
        provenance=Provenance(source="nse", extraction_method=ExtractionMethod.BULK_DOWNLOAD),
    )


# ---------------------------------------------------------------------------
# Helpers: slugify, format_decimal, format_date
# ---------------------------------------------------------------------------


class TestSlugifyCompany:
    def test_prefers_nse_symbol(self) -> None:
        assert slugify_company("Reliance Industries Ltd", "RELIANCE", "INE002A01018") == "reliance"

    def test_falls_back_to_name(self) -> None:
        assert slugify_company("Some Co Ltd", None, "INE123A01045") == "some_co"

    def test_strips_ltd_suffix(self) -> None:
        assert slugify_company("Tata Consultancy Services Ltd", None, "INE467B01029") == "tata_consultancy_services"

    def test_handles_ampersand(self) -> None:
        assert slugify_company("AT&T Co", None, "INE999A99999") == "atandt_co"

    def test_falls_back_to_isin_when_no_name_no_symbol(self) -> None:
        assert slugify_company("", None, "INE999A99999") == "ine999a99999"

    def test_handles_special_chars_in_name(self) -> None:
        assert slugify_company("M&M Co Ltd", None, "INE111A11111") == "mandm_co"


class TestFormatDecimal:
    def test_none_returns_em_dash(self) -> None:
        assert format_decimal(None) == "—"

    def test_integer(self) -> None:
        assert format_decimal(100) == "100"

    def test_float_trims_trailing_zeros(self) -> None:
        assert format_decimal(100.5) == "100.5"
        assert format_decimal(100.0) == "100"
        assert format_decimal(1234.5678) == "1234.5678"

    def test_decimal(self) -> None:
        assert format_decimal(Decimal("7.50")) == "7.5"

    def test_string(self) -> None:
        assert format_decimal("10.00") == "10.00"


class TestFormatDate:
    def test_none_returns_em_dash(self) -> None:
        assert format_date(None) == "—"

    def test_date_object(self) -> None:
        assert format_date(date(2024, 9, 30)) == "2024-09-30"

    def test_datetime_object(self) -> None:
        assert format_date(datetime(2024, 9, 30, 18, 30)) == "2024-09-30"

    def test_string_passthrough(self) -> None:
        assert format_date("2024-09-30") == "2024-09-30"


# ---------------------------------------------------------------------------
# format_observations_table
# ---------------------------------------------------------------------------


class TestFormatObservationsTable:
    def test_empty_returns_placeholder(self) -> None:
        assert format_observations_table([]) == "_(no observations)_"

    def test_renders_table_header(self) -> None:
        obs = [_make_close_obs("sec_x", date(2024, 9, 30), 100.0)]
        table = format_observations_table(obs)
        assert "| Date | Kind | Value |" in table
        assert "|------|------|------:" in table

    def test_includes_value_and_source(self) -> None:
        obs = [_make_close_obs("sec_x", date(2024, 9, 30), 100.0, source="yahoo")]
        table = format_observations_table(obs)
        assert "100" in table
        assert "yahoo" in table
        assert "2024-09-30" in table

    def test_sorts_descending_by_date(self) -> None:
        obs = [
            _make_close_obs("sec_x", date(2024, 9, 1), 100.0),
            _make_close_obs("sec_x", date(2024, 9, 30), 110.0),
            _make_close_obs("sec_x", date(2024, 9, 15), 105.0),
        ]
        table = format_observations_table(obs)
        # Most recent (2024-09-30) should appear before 2024-09-15
        idx_30 = table.index("2024-09-30")
        idx_15 = table.index("2024-09-15")
        idx_01 = table.index("2024-09-01")
        assert idx_30 < idx_15 < idx_01

    def test_limits_to_30_rows(self) -> None:
        obs = [
            _make_close_obs("sec_x", date(2024, 1, 1) + __import__("datetime").timedelta(days=i), 100.0 + i)
            for i in range(50)
        ]
        table = format_observations_table(obs)
        assert "showing 30 most recent of 50 total" in table


# ---------------------------------------------------------------------------
# format_corporate_actions_table
# ---------------------------------------------------------------------------


class TestFormatCorporateActionsTable:
    def test_empty_returns_placeholder(self) -> None:
        assert format_corporate_actions_table([]) == "_(no corporate actions on record)_"

    def test_renders_split_action(self) -> None:
        ca = _make_ca("sec_x", CorporateActionType.SPLIT, date(2024, 1, 15),
                      ratio_numerator=5, ratio_denominator=1)
        table = format_corporate_actions_table([ca])
        assert "split" in table
        assert "5 : 1" in table
        assert "2024-01-15" in table

    def test_renders_dividend_action(self) -> None:
        ca = _make_ca("sec_x", CorporateActionType.DIVIDEND, date(2024, 1, 15),
                      amount_per_share=Decimal("7.5"))
        table = format_corporate_actions_table([ca])
        assert "dividend" in table
        assert "7.5" in table

    def test_renders_bonus_action(self) -> None:
        ca = _make_ca("sec_x", CorporateActionType.BONUS, date(2024, 1, 15),
                      ratio_numerator=1, ratio_denominator=1)
        table = format_corporate_actions_table([ca])
        assert "bonus" in table
        assert "1 : 1" in table

    def test_sorts_descending_by_ex_date(self) -> None:
        cas = [
            _make_ca("sec_x", CorporateActionType.DIVIDEND, date(2024, 1, 15)),
            _make_ca("sec_x", CorporateActionType.DIVIDEND, date(2024, 9, 30)),
            _make_ca("sec_x", CorporateActionType.DIVIDEND, date(2024, 5, 1)),
        ]
        table = format_corporate_actions_table(cas)
        idx_sep = table.index("2024-09-30")
        idx_may = table.index("2024-05-01")
        idx_jan = table.index("2024-01-15")
        assert idx_sep < idx_may < idx_jan

    def test_truncates_long_notes(self) -> None:
        ca = _make_ca("sec_x", CorporateActionType.OTHER, date(2024, 1, 15))
        ca.notes = "x" * 200  # very long note
        table = format_corporate_actions_table([ca])
        assert "…" in table


# ---------------------------------------------------------------------------
# build_company_note
# ---------------------------------------------------------------------------


class TestBuildCompanyNote:
    def test_returns_markdown_string(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        assert isinstance(note, str)
        assert len(note) > 0

    def test_includes_yaml_frontmatter(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        assert note.startswith("---\n")
        # Frontmatter should end with --- before the title
        assert "\n---\n" in note

    def test_frontmatter_includes_key_fields(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        # Pull just the frontmatter
        fm = note.split("---\n")[1]
        assert "id:" in fm
        assert "isin: INE002A01018" in fm
        assert "nse_symbol: RELIANCE" in fm
        assert "bse_code: 500325" in fm
        assert "company_name:" in fm
        assert "exchange: NSE+BSE" in fm
        assert "observations_count: 0" in fm
        assert "corporate_actions_count: 0" in fm
        assert "last_updated:" in fm

    def test_title_uses_company_name(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        assert "# Reliance Industries Limited" in note

    def test_header_block_has_exchange_and_active(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        assert "**Exchange:** NSE+BSE" in note
        assert "**Active:** yes" in note
        assert "**ISIN:** `INE002A01018`" in note
        assert "**NSE symbol:** `RELIANCE`" in note

    def test_includes_all_section_headers(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        for header in [
            "## Latest snapshot",
            "## Business",
            "## Products",
            "## Customers",
            "## Suppliers",
            "## Raw materials",
            "## Cost drivers",
            "## Financials",
            "## Capital structure",
            "## Management / promoters",
            "## Risks",
            "## Value chain",
            "## Macro exposures",
            "## Evidence",
            "## Hypotheses",
            "## Validated relationships",
            "## Corporate actions",
            "## Data quality",
        ]:
            assert header in note, f"Missing section: {header}"

    def test_placeholder_sections_have_clear_notes(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        note = build_company_note(reliance_company, [], [], last_updated=fixed_ts)
        # Business section should mention "Phase 3"
        assert "_(Not yet researched — to be filled in Phase 3" in note

    def test_latest_snapshot_shows_close_prices(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        sec_id = "sec_reliance"
        obs = [
            _make_close_obs(sec_id, date(2024, 9, 30), 2750.0),
            _make_close_obs(sec_id, date(2024, 9, 25), 2740.0),
            _make_close_obs(sec_id, date(2024, 9, 30), 2745.0, kind=ObservationKind.PRICE_CLOSE_ADJ, source="investorlens"),
        ]
        note = build_company_note(reliance_company, obs, [], last_updated=fixed_ts)
        assert "Last close (raw):" in note
        assert "2750" in note
        assert "Last close (adjusted):" in note
        assert "2745" in note

    def test_financials_section_includes_observations_count(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        sec_id = "sec_reliance"
        obs = [
            _make_close_obs(sec_id, date(2024, 9, 30), 2750.0),
            _make_volume_obs(sec_id, date(2024, 9, 30), 1000000),
        ]
        note = build_company_note(reliance_company, obs, [], last_updated=fixed_ts)
        assert "2 observations on record" in note

    def test_financials_section_renders_price_table(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        sec_id = "sec_reliance"
        obs = [
            _make_close_obs(sec_id, date(2024, 9, 30), 2750.0),
            _make_close_obs(sec_id, date(2024, 9, 25), 2740.0),
        ]
        note = build_company_note(reliance_company, obs, [], last_updated=fixed_ts)
        assert "### Price observations" in note
        assert "| Date | Kind | Value |" in note

    def test_corporate_actions_section_renders_table(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        sec_id = "sec_reliance"
        cas = [
            _make_ca(sec_id, CorporateActionType.DIVIDEND, date(2024, 9, 10),
                     amount_per_share=Decimal("7")),
            _make_ca(sec_id, CorporateActionType.BONUS, date(2024, 11, 12),
                     ratio_numerator=1, ratio_denominator=1),
        ]
        note = build_company_note(reliance_company, [], cas, last_updated=fixed_ts)
        assert "## Corporate actions" in note
        assert "dividend" in note
        assert "bonus" in note
        assert "7" in note
        assert "1 : 1" in note

    def test_data_quality_section_includes_counts(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        sec_id = "sec_reliance"
        obs = [_make_close_obs(sec_id, date(2024, 9, 30), 2750.0)]
        cas = [_make_ca(sec_id, CorporateActionType.DIVIDEND, date(2024, 9, 10))]
        note = build_company_note(reliance_company, obs, cas, last_updated=fixed_ts)
        assert "Observations count:** 1" in note
        assert "Corporate actions count:** 1" in note
        assert "Earliest observation:** 2024-09-30" in note
        assert "Latest observation:** 2024-09-30" in note

    def test_macro_exposures_section_mentions_drivers(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        sec_id = "sec_reliance"
        obs = [_make_close_obs(sec_id, date(2024, 9, 30), 2750.0)]
        note = build_company_note(reliance_company, obs, [], last_updated=fixed_ts)
        assert "## Macro exposures" in note
        assert "policy_repo_rate" in note
        assert "USD/INR" in note
        assert "CPI Combined YoY" in note

    def test_deterministic_output(
        self,
        reliance_company: dict,
        fixed_ts: datetime,
    ) -> None:
        """Same inputs → byte-identical output."""
        sec_id = "sec_reliance"
        obs = [_make_close_obs(sec_id, date(2024, 9, 30), 2750.0)]
        cas = [_make_ca(sec_id, CorporateActionType.DIVIDEND, date(2024, 9, 10))]
        a = build_company_note(reliance_company, obs, cas, last_updated=fixed_ts)
        b = build_company_note(reliance_company, obs, cas, last_updated=fixed_ts)
        assert a == b

    def test_handles_missing_fields_gracefully(self, fixed_ts: datetime) -> None:
        """A company record with missing fields should not crash the builder."""
        minimal_company = {
            "id": "isin_abc",
            "isin": "INE999A99999",
            "company_name": "Unknown Co",
            "exchange": "NSE",
            "active": True,
        }
        note = build_company_note(minimal_company, [], [], last_updated=fixed_ts)
        assert "# Unknown Co" in note
        assert "INE999A99999" in note

    def test_yaml_escapes_special_chars_in_company_name(self, fixed_ts: datetime) -> None:
        """Company names with colons or other YAML-special chars must be escaped."""
        company = {
            "id": "isin_abc",
            "isin": "INE999A99999",
            "company_name": "Test: Company #1",
            "exchange": "NSE",
            "active": True,
        }
        note = build_company_note(company, [], [], last_updated=fixed_ts)
        # The frontmatter should wrap the value in quotes
        fm = note.split("---\n")[1]
        assert 'company_name: "Test: Company #1"' in fm
