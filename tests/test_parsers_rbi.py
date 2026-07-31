"""Tests for the RBI parsers (investorlens.parsers.rbi)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investorlens.parsers import rbi
from investorlens.parsers.rbi import (
    POLICY_RATE_SLUGS,
    extract_tables,
    parse_fx_reference_html,
    parse_policy_rates_html,
)
from investorlens.models import ObservationKind
from investorlens.ids import make_id

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def policy_html() -> str:
    return (FIXTURES / "rbi_policy_rates.html").read_text(encoding="utf-8")


@pytest.fixture
def fx_html() -> str:
    return (FIXTURES / "rbi_fx_reference.html").read_text(encoding="utf-8")


@pytest.fixture
def fixed_ts() -> datetime:
    return datetime(2024, 10, 9, 13, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# extract_tables
# ---------------------------------------------------------------------------


class TestExtractTables:
    def test_extracts_a_single_table(self) -> None:
        html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        tables = extract_tables(html)
        assert len(tables) == 1
        assert tables[0].rows == [["A", "B"], ["1", "2"]]

    def test_extracts_multiple_tables(self) -> None:
        html = (
            "<table><tr><td>A</td></tr></table>"
            "<table><tr><td>B</td></tr></table>"
        )
        tables = extract_tables(html)
        assert len(tables) == 2

    def test_handles_nested_tags_in_cells(self) -> None:
        html = "<table><tr><td><b>bold</b> <i>italic</i></td></tr></table>"
        tables = extract_tables(html)
        assert tables[0].rows == [["bold italic"]]

    def test_handles_empty_html(self) -> None:
        assert extract_tables("") == []
        assert extract_tables("<html><body>no tables</body></html>") == []

    def test_strips_whitespace_in_cells(self) -> None:
        html = "<table><tr><td>  hello   world  </td></tr></table>"
        tables = extract_tables(html)
        assert tables[0].rows == [["hello world"]]


# ---------------------------------------------------------------------------
# Policy rate slug canonicalization
# ---------------------------------------------------------------------------


class TestPolicyRateSlugs:
    def test_known_slugs(self) -> None:
        assert rbi._canonical_policy_slug("Policy Repo Rate") == "policy_repo_rate"
        assert rbi._canonical_policy_slug("SDF Rate") == "sdf_rate"
        assert rbi._canonical_policy_slug("MSF Rate") == "msf_rate"
        assert rbi._canonical_policy_slug("Bank Rate") == "bank_rate"
        assert rbi._canonical_policy_slug("CRR") == "crr"
        assert rbi._canonical_policy_slug("SLR") == "slr"
        assert rbi._canonical_policy_slug("Fixed Reverse Repo Rate") == "fixed_reverse_repo_rate"

    def test_case_insensitive(self) -> None:
        assert rbi._canonical_policy_slug("policy repo rate") == "policy_repo_rate"
        assert rbi._canonical_policy_slug("POLICY REPO RATE") == "policy_repo_rate"
        assert rbi._canonical_policy_slug("crr") == "crr"
        assert rbi._canonical_policy_slug("CRR") == "crr"

    def test_prefix_match(self) -> None:
        """A label like 'Policy Repo Rate (as on 09-Oct-2024)' should still match."""
        assert rbi._canonical_policy_slug("Policy Repo Rate (as on 09-Oct-2024)") == "policy_repo_rate"

    def test_unknown_label_returns_none(self) -> None:
        assert rbi._canonical_policy_slug("Some Random Rate") is None
        assert rbi._canonical_policy_slug("") is None
        assert rbi._canonical_policy_slug(None) is None


# ---------------------------------------------------------------------------
# parse_policy_rates_html
# ---------------------------------------------------------------------------


class TestParsePolicyRatesHtml:
    def test_parses_all_known_rates(self, policy_html: str, fixed_ts: datetime) -> None:
        obs = parse_policy_rates_html(
            policy_html,
            retrieved_at=fixed_ts,
            source_url="https://rbi.org.in/Scripts/BS_ViewPolicyRates.aspx",
            as_of=date(2024, 10, 9),
        )
        # 7 rates in the fixture: Repo, SDF, MSF, Bank Rate, CRR, SLR, Reverse Repo
        assert len(obs) == 7

    def test_observation_fields(self, policy_html: str, fixed_ts: datetime) -> None:
        obs = parse_policy_rates_html(policy_html, retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        for o in obs:
            assert o.kind == ObservationKind.POLICY_RATE
            assert o.unit == "%"
            assert o.currency is None  # rates are unitless %
            assert o.data_status.value == "observed"
            assert o.subject_id.startswith("drv_")
            assert o.as_of == date(2024, 10, 9)
            assert o.period == "2024-10-09"

    def test_specific_rate_values(self, policy_html: str, fixed_ts: datetime) -> None:
        obs = parse_policy_rates_html(policy_html, retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        by_subject = {o.subject_id: o.value for o in obs}

        # Verify each known rate has the expected value.
        assert by_subject[make_id("drv", {"slug": "policy_repo_rate"})] == 6.50
        assert by_subject[make_id("drv", {"slug": "sdf_rate"})] == 6.25
        assert by_subject[make_id("drv", {"slug": "msf_rate"})] == 6.75
        assert by_subject[make_id("drv", {"slug": "bank_rate"})] == 6.75
        assert by_subject[make_id("drv", {"slug": "crr"})] == 4.50
        assert by_subject[make_id("drv", {"slug": "slr"})] == 18.00
        assert by_subject[make_id("drv", {"slug": "fixed_reverse_repo_rate"})] == 3.35

    def test_provenance_attached(self, policy_html: str, fixed_ts: datetime) -> None:
        url = "https://rbi.org.in/Scripts/BS_ViewPolicyRates.aspx"
        obs = parse_policy_rates_html(
            policy_html, retrieved_at=fixed_ts, source_url=url, as_of=date(2024, 10, 9),
        )
        prov = obs[0].provenance
        assert prov.source == "rbi"
        assert prov.extraction_method.value == "html_scrape"
        assert prov.confidence.value == "high"
        assert prov.retrieved_at == fixed_ts
        assert str(prov.source_url) == url

    def test_id_deterministic(self, policy_html: str, fixed_ts: datetime) -> None:
        a = parse_policy_rates_html(policy_html, retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        b = parse_policy_rates_html(policy_html, retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        assert [o.id for o in a] == [o.id for o in b]

    def test_id_includes_subject_kind_period(self, policy_html: str, fixed_ts: datetime) -> None:
        """Two observations of the same rate on the same date would collide."""
        obs = parse_policy_rates_html(policy_html, retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        keys = {(o.subject_id, o.kind.value, o.as_of.isoformat()) for o in obs}
        assert len(keys) == len(obs)

    def test_default_as_of_is_today(self, policy_html: str, fixed_ts: datetime) -> None:
        """If as_of is not given, defaults to today's date."""
        from datetime import datetime as dt
        obs = parse_policy_rates_html(policy_html, retrieved_at=fixed_ts)
        expected_today = dt.now().date()
        for o in obs:
            assert o.as_of == expected_today

    def test_empty_html_returns_empty(self, fixed_ts: datetime) -> None:
        obs = parse_policy_rates_html("", retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        assert obs == []

    def test_no_table_returns_empty(self, fixed_ts: datetime) -> None:
        obs = parse_policy_rates_html("<html><body>no tables</body></html>", retrieved_at=fixed_ts, as_of=date(2024, 10, 9))
        assert obs == []


# ---------------------------------------------------------------------------
# parse_fx_reference_html
# ---------------------------------------------------------------------------


class TestParseFxReferenceHtml:
    def test_parses_all_currencies_all_days(self, fx_html: str, fixed_ts: datetime) -> None:
        """5 dates × 4 currencies (USD, EUR, GBP, JPY) = 20 observations."""
        obs = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts)
        assert len(obs) == 20

    def test_observation_fields(self, fx_html: str, fixed_ts: datetime) -> None:
        obs = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts)
        for o in obs:
            assert o.kind == ObservationKind.FX_RATE
            assert o.subject_id.startswith("drv_")
            assert o.data_status.value == "observed"

    def test_specific_fx_value(self, fx_html: str, fixed_ts: datetime) -> None:
        obs = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts)
        # Find USD rate on 04-Oct-2024
        usd_subject = make_id("drv", {"slug": "fx_usd_inr"})
        usd_obs = next(o for o in obs if o.subject_id == usd_subject and o.as_of == date(2024, 10, 4))
        assert usd_obs.value == 84.0525
        assert usd_obs.unit == "INR/USD"
        assert usd_obs.currency == "INR"

    def test_jpy_value_parsed_correctly(self, fx_html: str, fixed_ts: datetime) -> None:
        """JPY is quoted as '100 JPY = X INR' but the rate stored should be that X."""
        obs = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts)
        jpy_subject = make_id("drv", {"slug": "fx_jpy_inr"})
        jpy_obs = next(o for o in obs if o.subject_id == jpy_subject and o.as_of == date(2024, 10, 4))
        assert jpy_obs.value == 56.12
        assert jpy_obs.unit == "INR/JPY"

    def test_provenance_attached(self, fx_html: str, fixed_ts: datetime) -> None:
        url = "https://rbi.org.in/Scripts/ReferenceRate.aspx"
        obs = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts, source_url=url)
        prov = obs[0].provenance
        assert prov.source == "rbi"
        assert prov.extraction_method.value == "html_scrape"
        assert prov.confidence.value == "high"
        assert prov.retrieved_at == fixed_ts
        assert str(prov.source_url) == url

    def test_id_deterministic(self, fx_html: str, fixed_ts: datetime) -> None:
        a = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts)
        b = parse_fx_reference_html(fx_html, retrieved_at=fixed_ts)
        assert [o.id for o in a] == [o.id for o in b]

    def test_empty_html_returns_empty(self, fixed_ts: datetime) -> None:
        obs = parse_fx_reference_html("", retrieved_at=fixed_ts)
        assert obs == []

    def test_skips_invalid_dates(self, fixed_ts: datetime) -> None:
        """Rows with unparseable dates should be skipped."""
        html = """
        <table>
          <tr><th>Date</th><th>1 USD</th></tr>
          <tr><td>NOT-A-DATE</td><td>84.05</td></tr>
          <tr><td>04-Oct-2024</td><td>84.0525</td></tr>
        </table>
        """
        obs = parse_fx_reference_html(html, retrieved_at=fixed_ts)
        assert len(obs) == 1
        assert obs[0].as_of == date(2024, 10, 4)

    def test_skips_zero_or_invalid_values(self, fixed_ts: datetime) -> None:
        """Zero or non-numeric FX values should be skipped."""
        html = """
        <table>
          <tr><th>Date</th><th>1 USD</th></tr>
          <tr><td>04-Oct-2024</td><td>0</td></tr>
          <tr><td>03-Oct-2024</td><td>NA</td></tr>
          <tr><td>02-Oct-2024</td><td>83.91</td></tr>
        </table>
        """
        obs = parse_fx_reference_html(html, retrieved_at=fixed_ts)
        assert len(obs) == 1
        assert obs[0].value == 83.91
