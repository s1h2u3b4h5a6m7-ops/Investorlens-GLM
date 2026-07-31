"""Tests for the adjusted prices builder (investorlens.builders.adjusted_prices).

The math here is critical — these tests verify the adjustment factors against
hand-computed expected values for known corporate actions.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from investorlens.builders.adjusted_prices import (
    adjust_prices_for_security,
    build_adjusted_prices,
    compute_adjustment_factor,
    AdjustmentDecomposition,
)
from investorlens.models import (
    CorporateAction,
    CorporateActionType,
    Observation,
    ObservationKind,
    Provenance,
)
from investorlens.models.provenance import Confidence, ExtractionMethod

FIXTURES = Path(__file__).parent / "fixtures"


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


def make_close_obs(
    security_id: str,
    as_of: date,
    value: float,
    source: str = "nse",
    prov: Provenance | None = None,
) -> Observation:
    """Helper: build a price_close Observation."""
    p = prov or Provenance(source=source, extraction_method=ExtractionMethod.BULK_DOWNLOAD)
    return Observation(
        subject_id=security_id,
        kind=ObservationKind.PRICE_CLOSE,
        period=as_of.isoformat(),
        as_of=as_of,
        value=value,
        unit="INR/share",
        currency="INR",
        provenance=p,
    )


def make_ca(
    security_id: str,
    action_type: CorporateActionType,
    ex_date: date,
    *,
    ratio_numerator: float | None = None,
    ratio_denominator: float | None = None,
    amount_per_share: Decimal | None = None,
    prov: Provenance | None = None,
) -> CorporateAction:
    """Helper: build a CorporateAction."""
    p = prov or Provenance(source="nse", extraction_method=ExtractionMethod.BULK_DOWNLOAD)
    return CorporateAction(
        security_id=security_id,
        action_type=action_type,
        ex_date=ex_date,
        ratio_numerator=ratio_numerator,
        ratio_denominator=ratio_denominator,
        amount_per_share=amount_per_share,
        provenance=p,
    )


# ---------------------------------------------------------------------------
# compute_adjustment_factor
# ---------------------------------------------------------------------------


class TestComputeAdjustmentFactor:
    def test_split_5_to_1_factor_5(self, prov: Provenance) -> None:
        ca = make_ca("sec_x", CorporateActionType.SPLIT, date(2024, 1, 1),
                     ratio_numerator=5, ratio_denominator=1, prov=prov)
        assert compute_adjustment_factor(ca) == 5.0

    def test_split_2_to_1_factor_2(self, prov: Provenance) -> None:
        ca = make_ca("sec_x", CorporateActionType.SPLIT, date(2024, 1, 1),
                     ratio_numerator=2, ratio_denominator=1, prov=prov)
        assert compute_adjustment_factor(ca) == 2.0

    def test_bonus_1_to_1_factor_2(self, prov: Provenance) -> None:
        """1 bonus share for every 1 held → factor = (1+1)/1 = 2"""
        ca = make_ca("sec_x", CorporateActionType.BONUS, date(2024, 1, 1),
                     ratio_numerator=1, ratio_denominator=1, prov=prov)
        assert compute_adjustment_factor(ca) == 2.0

    def test_bonus_1_to_3_factor_4_over_3(self, prov: Provenance) -> None:
        """1 bonus share for every 3 held → factor = (3+1)/3 = 1.333..."""
        ca = make_ca("sec_x", CorporateActionType.BONUS, date(2024, 1, 1),
                     ratio_numerator=1, ratio_denominator=3, prov=prov)
        assert compute_adjustment_factor(ca) == pytest.approx(4 / 3, rel=1e-6)

    def test_dividend_factor_1(self, prov: Provenance) -> None:
        """Dividends don't have a multiplicative factor."""
        ca = make_ca("sec_x", CorporateActionType.DIVIDEND, date(2024, 1, 1),
                     amount_per_share=Decimal("5"), prov=prov)
        assert compute_adjustment_factor(ca) == 1.0

    def test_missing_ratio_returns_1(self, prov: Provenance) -> None:
        ca = make_ca("sec_x", CorporateActionType.SPLIT, date(2024, 1, 1), prov=prov)
        assert compute_adjustment_factor(ca) == 1.0


# ---------------------------------------------------------------------------
# adjust_prices_for_security — split math
# ---------------------------------------------------------------------------


class TestSplitAdjustment:
    def test_2_to_1_split_halves_prior_prices(self, prov: Provenance, fixed_ts: datetime) -> None:
        """A 2:1 split on day 5 should halve prices on days 1-4 and leave day 5+ unchanged."""
        sid = "sec_test"
        # Prices: days 1-4 at 100, days 5-8 at 50 (post-split price halves)
        raw_closes = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 100.0),
            (date(2024, 1, 4), 100.0),
            (date(2024, 1, 5), 50.0),   # split ex-date
            (date(2024, 1, 6), 50.0),
            (date(2024, 1, 7), 50.0),
        ]
        cas = [make_ca(sid, CorporateActionType.SPLIT, date(2024, 1, 5),
                      ratio_numerator=2, ratio_denominator=1, prov=prov)]

        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        # 7 days × 1 observation = 7 adjusted-price observations
        assert len(obs) == 7

        # Verify by date
        by_date = {o.as_of: o.value for o in obs}
        # Days before split: 100 / 2 = 50
        assert by_date[date(2024, 1, 1)] == 50.0
        assert by_date[date(2024, 1, 2)] == 50.0
        assert by_date[date(2024, 1, 3)] == 50.0
        assert by_date[date(2024, 1, 4)] == 50.0
        # Days on/after split: 50 / 1 = 50 (factor at day 5+ is 1.0)
        assert by_date[date(2024, 1, 5)] == 50.0
        assert by_date[date(2024, 1, 6)] == 50.0
        assert by_date[date(2024, 1, 7)] == 50.0

    def test_multiple_splits_compose_multiplicatively(self, prov: Provenance, fixed_ts: datetime) -> None:
        """Two 2:1 splits → 4x cumulative factor for prices before both."""
        sid = "sec_test"
        raw_closes = [
            (date(2024, 1, 1), 200.0),  # before both splits
            (date(2024, 1, 10), 100.0),  # between splits (after first, before second)
            (date(2024, 1, 20), 50.0),   # after both splits
        ]
        cas = [
            make_ca(sid, CorporateActionType.SPLIT, date(2024, 1, 5),
                    ratio_numerator=2, ratio_denominator=1, prov=prov),
            make_ca(sid, CorporateActionType.SPLIT, date(2024, 1, 15),
                    ratio_numerator=2, ratio_denominator=1, prov=prov),
        ]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        by_date = {o.as_of: o.value for o in obs}
        # Day 1: factor = 2*2 = 4 → 200/4 = 50
        assert by_date[date(2024, 1, 1)] == 50.0
        # Day 10: factor = 2 (only the second split applies) → 100/2 = 50
        assert by_date[date(2024, 1, 10)] == 50.0
        # Day 20: factor = 1 (no splits apply) → 50/1 = 50
        assert by_date[date(2024, 1, 20)] == 50.0


# ---------------------------------------------------------------------------
# adjust_prices_for_security — bonus math
# ---------------------------------------------------------------------------


class TestBonusAdjustment:
    def test_1_to_1_bonus_halves_prior_prices(self, prov: Provenance, fixed_ts: datetime) -> None:
        """A 1:1 bonus (1 new share for every 1 held) → factor = 2.0, halves prior prices."""
        sid = "sec_test"
        raw_closes = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 5), 50.0),   # bonus ex-date
            (date(2024, 1, 10), 50.0),
        ]
        cas = [make_ca(sid, CorporateActionType.BONUS, date(2024, 1, 5),
                      ratio_numerator=1, ratio_denominator=1, prov=prov)]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        by_date = {o.as_of: o.value for o in obs}
        assert by_date[date(2024, 1, 1)] == 50.0
        assert by_date[date(2024, 1, 5)] == 50.0
        assert by_date[date(2024, 1, 10)] == 50.0


# ---------------------------------------------------------------------------
# adjust_prices_for_security — dividend math
# ---------------------------------------------------------------------------


class TestDividendAdjustment:
    def test_dividend_reduces_prior_prices_proportionally(self, prov: Provenance, fixed_ts: datetime) -> None:
        """A Rs.10 dividend on a Rs.100 stock → prior prices reduced by 10%."""
        sid = "sec_test"
        raw_closes = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 5), 100.0),  # ex-date (price unchanged on ex-date in our simple model)
            (date(2024, 1, 10), 100.0),
        ]
        cas = [make_ca(sid, CorporateActionType.DIVIDEND, date(2024, 1, 5),
                       amount_per_share=Decimal("10"), prov=prov)]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        by_date = {o.as_of: o.value for o in obs}
        # Day 1: 100 - 10 * (100/100) = 100 - 10 = 90
        assert by_date[date(2024, 1, 1)] == 90.0
        # Day 5 (ex-date) and after: 100 - 0 = 100 (no adjustment for day >= ex_date)
        assert by_date[date(2024, 1, 5)] == 100.0
        assert by_date[date(2024, 1, 10)] == 100.0

    def test_multiple_dividends_compose(self, prov: Provenance, fixed_ts: datetime) -> None:
        """Two dividends: Rs.10 on day 5, Rs.5 on day 15. Both reduce prior prices.

        CRSP-style total-return adjustment: processing dividends in REVERSE
        chronological order, each dividend's adjustment uses the ALREADY-ADJUSTED
        price on its ex-date (not the raw close). This compounds the adjustments.

        - Rs.5 dividend (day 15): adj_close[day 15] = raw = 100 (no later adj).
          price_adj = 5 * (100/100) = 5. Apply to days < 15: day 1, day 10 → 100-5 = 95.
        - Rs.10 dividend (day 5): adj_close[day 10] = 95 (already adjusted).
          price_adj = 10 * (95/100) = 9.5. Apply to days < 5: day 1 → 95-9.5 = 85.5.
        - Day 10: 95 (only Rs.5 div applied; Rs.10 div ex_date is day 5, day 10 > day 5).
        - Day 20: 100 (no dividends applied).
        """
        sid = "sec_test"
        raw_closes = [
            (date(2024, 1, 1), 100.0),  # before both dividends
            (date(2024, 1, 10), 100.0),  # between dividends
            (date(2024, 1, 20), 100.0),  # after both
        ]
        cas = [
            make_ca(sid, CorporateActionType.DIVIDEND, date(2024, 1, 5),
                    amount_per_share=Decimal("10"), prov=prov),
            make_ca(sid, CorporateActionType.DIVIDEND, date(2024, 1, 15),
                    amount_per_share=Decimal("5"), prov=prov),
        ]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        by_date = {o.as_of: o.value for o in obs}
        # Day 1: 100 - 5 (Rs.5 div) - 9.5 (Rs.10 div, adjusted) = 85.5
        assert by_date[date(2024, 1, 1)] == 85.5
        # Day 10: 100 - 5 (Rs.5 div) = 95 (Rs.10 div ex_date is day 5, day 10 >= day 5)
        assert by_date[date(2024, 1, 10)] == 95.0
        # Day 20: 100 (no dividends applied)
        assert by_date[date(2024, 1, 20)] == 100.0


# ---------------------------------------------------------------------------
# adjust_prices_for_security — combined split + dividend
# ---------------------------------------------------------------------------


class TestCombinedAdjustment:
    def test_split_then_dividend(self, prov: Provenance, fixed_ts: datetime) -> None:
        """A 2:1 split on day 5, then a Rs.5 dividend on day 15.

        Day 1 raw=100 → split factor 2 → 50; dividend adj: 5*(50/100) on day 15 close=50.
        Wait — let me think this through carefully:
        - Day 1: raw=100, factor=2 (split), split-adj = 100/2 = 50.
        - Day 15: raw=100 (let's say), factor=1 (post-split, pre-dividend), split-adj=100.
          But we said price halves after split, so day 15 raw should be 50.
        Let me redo with realistic prices.
        """
        sid = "sec_test"
        # Realistic: stock at 100, splits 2:1 → drops to 50, then later pays Rs.5 dividend
        raw_closes = [
            (date(2024, 1, 1), 100.0),   # pre-split
            (date(2024, 1, 5), 50.0),    # split ex-date
            (date(2024, 1, 10), 50.0),   # post-split, pre-dividend
            (date(2024, 1, 15), 50.0),   # dividend ex-date
            (date(2024, 1, 20), 50.0),   # post-dividend
        ]
        cas = [
            make_ca(sid, CorporateActionType.SPLIT, date(2024, 1, 5),
                    ratio_numerator=2, ratio_denominator=1, prov=prov),
            make_ca(sid, CorporateActionType.DIVIDEND, date(2024, 1, 15),
                    amount_per_share=Decimal("5"), prov=prov),
        ]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        by_date = {o.as_of: o.value for o in obs}

        # Day 1: raw=100, split-adj=100/2=50. Dividend adj: 5 * (adj_close[day 15] / raw_close[day 15])
        # = 5 * (50/50) = 5. Final: 50 - 5 = 45.
        assert by_date[date(2024, 1, 1)] == 45.0
        # Day 5 (split ex-date): factor at day 5 = 1 (split already happened).
        # Split-adj = 50/1 = 50. Dividend adj applies (day 5 < day 15): 50 - 5 = 45.
        assert by_date[date(2024, 1, 5)] == 45.0
        # Day 10: same as day 5. 50 - 5 = 45.
        assert by_date[date(2024, 1, 10)] == 45.0
        # Day 15 (dividend ex-date): not adjusted (day >= ex_date). 50.
        assert by_date[date(2024, 1, 15)] == 50.0
        # Day 20: same. 50.
        assert by_date[date(2024, 1, 20)] == 50.0


# ---------------------------------------------------------------------------
# Decomposition transparency
# ---------------------------------------------------------------------------


class TestDecomposition:
    def test_decomposition_in_provenance_notes(self, prov: Provenance, fixed_ts: datetime) -> None:
        """Every adjusted-price observation should carry a JSON decomposition in provenance.notes."""
        sid = "sec_test"
        raw_closes = [(date(2024, 1, 1), 100.0), (date(2024, 1, 5), 50.0)]
        cas = [make_ca(sid, CorporateActionType.SPLIT, date(2024, 1, 5),
                      ratio_numerator=2, ratio_denominator=1, prov=prov)]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        for o in obs:
            assert o.provenance.notes is not None
            decomposition = json.loads(o.provenance.notes)
            assert "raw_close" in decomposition
            assert "cumulative_split_bonus_factor" in decomposition
            assert "dividend_adjustments" in decomposition
            assert "final_adjusted_close" in decomposition

        # Day 1: factor=2, raw=100, final=50.
        day1 = next(o for o in obs if o.as_of == date(2024, 1, 1))
        d1 = json.loads(day1.provenance.notes)
        assert d1["raw_close"] == 100.0
        assert d1["cumulative_split_bonus_factor"] == 2.0
        assert d1["final_adjusted_close"] == 50.0

    def test_provenance_source_is_investorlens(self, prov: Provenance, fixed_ts: datetime) -> None:
        sid = "sec_test"
        raw_closes = [(date(2024, 1, 1), 100.0)]
        cas = []
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        assert obs[0].provenance.source == "investorlens"
        assert obs[0].provenance.extraction_method.value == "derived"

    def test_id_deterministic(self, prov: Provenance, fixed_ts: datetime) -> None:
        sid = "sec_test"
        raw_closes = [(date(2024, 1, 1), 100.0)]
        cas = [make_ca(sid, CorporateActionType.SPLIT, date(2024, 1, 5),
                      ratio_numerator=2, ratio_denominator=1, prov=prov)]
        a = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        b = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        assert [o.id for o in a] == [o.id for o in b]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_corp_actions_returns_split_adjusted_only(self, fixed_ts: datetime) -> None:
        """With no corp actions, adj_close = raw_close (factor=1, no dividends)."""
        sid = "sec_test"
        raw_closes = [(date(2024, 1, 1), 100.0), (date(2024, 1, 2), 101.0)]
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=[], retrieved_at=fixed_ts,
        )
        by_date = {o.as_of: o.value for o in obs}
        assert by_date[date(2024, 1, 1)] == 100.0
        assert by_date[date(2024, 1, 2)] == 101.0

    def test_empty_raw_closes_returns_empty(self, fixed_ts: datetime) -> None:
        obs = adjust_prices_for_security(
            security_id="sec_x", raw_closes=[], corp_actions=[], retrieved_at=fixed_ts,
        )
        assert obs == []

    def test_unsupported_action_types_skipped(self, prov: Provenance, fixed_ts: datetime) -> None:
        """Mergers, demergers, etc. should be skipped (with a warning), not crash."""
        sid = "sec_test"
        raw_closes = [(date(2024, 1, 1), 100.0)]
        cas = [
            make_ca(sid, CorporateActionType.MERGER, date(2024, 1, 5), prov=prov),
            make_ca(sid, CorporateActionType.DEMERGER, date(2024, 1, 6), prov=prov),
        ]
        # Should not raise.
        obs = adjust_prices_for_security(
            security_id=sid, raw_closes=raw_closes, corp_actions=cas, retrieved_at=fixed_ts,
        )
        assert len(obs) == 1
        # No adjustment applied.
        assert obs[0].value == 100.0

    def test_unavailable_observations_skipped_in_build_adjusted_prices(
        self, prov: Provenance, fixed_ts: datetime
    ) -> None:
        """build_adjusted_prices should skip price_close observations marked unavailable."""
        sid = "sec_test"
        obs_input = [
            Observation(
                subject_id=sid,
                kind=ObservationKind.PRICE_CLOSE,
                period="2024-01-01",
                as_of=date(2024, 1, 1),
                value=None,
                data_status="unavailable",
                provenance=prov,
            ),
            Observation(
                subject_id=sid,
                kind=ObservationKind.PRICE_CLOSE,
                period="2024-01-02",
                as_of=date(2024, 1, 2),
                value=100.0,
                data_status="observed",
                provenance=prov,
            ),
        ]
        adj = build_adjusted_prices(price_observations=obs_input, corp_actions=[], retrieved_at=fixed_ts)
        assert len(adj) == 1
        assert adj[0].as_of == date(2024, 1, 2)


# ---------------------------------------------------------------------------
# build_adjusted_prices — top-level orchestration
# ---------------------------------------------------------------------------


class TestBuildAdjustedPrices:
    def test_processes_multiple_securities(self, prov: Provenance, fixed_ts: datetime) -> None:
        """Should process each security independently."""
        sid_a = "sec_a"
        sid_b = "sec_b"
        obs_input = [
            make_close_obs(sid_a, date(2024, 1, 1), 100.0, prov=prov),
            make_close_obs(sid_a, date(2024, 1, 5), 50.0, prov=prov),
            make_close_obs(sid_b, date(2024, 1, 1), 200.0, prov=prov),
            make_close_obs(sid_b, date(2024, 1, 5), 100.0, prov=prov),
        ]
        cas = [
            make_ca(sid_a, CorporateActionType.SPLIT, date(2024, 1, 5),
                    ratio_numerator=2, ratio_denominator=1, prov=prov),
            make_ca(sid_b, CorporateActionType.SPLIT, date(2024, 1, 5),
                    ratio_numerator=2, ratio_denominator=1, prov=prov),
        ]
        adj = build_adjusted_prices(price_observations=obs_input, corp_actions=cas, retrieved_at=fixed_ts)
        # 2 securities × 2 days = 4 adjusted observations
        assert len(adj) == 4
        # All should be price_close_adj
        for o in adj:
            assert o.kind == ObservationKind.PRICE_CLOSE_ADJ
        # Day 1 prices should be halved (split factor 2)
        day1_a = next(o for o in adj if o.subject_id == sid_a and o.as_of == date(2024, 1, 1))
        assert day1_a.value == 50.0
        day1_b = next(o for o in adj if o.subject_id == sid_b and o.as_of == date(2024, 1, 1))
        assert day1_b.value == 100.0

    def test_skips_non_price_close_observations(self, prov: Provenance, fixed_ts: datetime) -> None:
        """Only PRICE_CLOSE observations feed into the adjustment."""
        sid = "sec_test"
        obs_input = [
            make_close_obs(sid, date(2024, 1, 1), 100.0, prov=prov),
            Observation(
                subject_id=sid,
                kind=ObservationKind.VOLUME,
                period="2024-01-01",
                as_of=date(2024, 1, 1),
                value=1000,
                unit="shares",
                provenance=prov,
            ),
        ]
        adj = build_adjusted_prices(price_observations=obs_input, corp_actions=[], retrieved_at=fixed_ts)
        assert len(adj) == 1
        assert adj[0].kind == ObservationKind.PRICE_CLOSE_ADJ
