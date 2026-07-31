"""
Adjusted price series builder.

Takes raw `price_close` observations + `CorporateAction` records, returns
`price_close_adj` observations computed from official NSE corporate actions.

This is the **transparent, decomposable** counterpart to Yahoo's adjclose:
  - Yahoo: black-box adjustment (we trust their algorithm)
  - InvestorLens: explicit adjustment factors derived from official corp actions

Phase 4 can cross-validate the two: if they diverge significantly, either
Yahoo has a bug or our corp-action parser missed an event.

────────────────────────────────────────────────────────────────────────
ADJUSTMENT MATH (documented for transparency — Operating Principle 11)
────────────────────────────────────────────────────────────────────

Setup:
  - P[t]   = raw close price on day t (from bhavcopy or Yahoo raw close)
  - CA     = chronological list of corporate actions for the security
             with ex-dates d_1 < d_2 < ... < d_n
  - For each action i, we have a per-action adjustment factor:

Action factors:
  - SPLIT (ratio n:d, e.g. 5:1 means 5 new shares for 1 old):
        split_factor_i = n / d
    Each pre-ex-date price is DIVIDED by this factor (the price "dropped" by
    the ratio, so historical prices are scaled down to match the new share count).

  - BONUS (ratio n:d, e.g. 1:1 means 1 bonus share for every 1 held):
        bonus_factor_i = (d + n) / d
    Same math as split — bonus increases share count without changing market cap,
    so historical prices are scaled down.

  - DIVIDEND (amount D per share):
        No multiplicative factor. Handled as a subtractive adjustment below.

  - MERGER / DEMERGER / RIGHTS / SYMBOL_CHANGE / FACE_VALUE_CHANGE / OTHER:
        Not adjusted automatically. These require case-by-case handling;
        we emit a warning and treat them as no-ops for now. (Phase 3+ will
        add explicit handlers for mergers and demergers once we have
        sufficient data.)

Cumulative split+bonus factor (multiplicative):
  For day t, define:
        f[t] = product of split_factor_i * bonus_factor_i for all i with d_i > t

  This is the cumulative dilution factor applied to prices BEFORE day t.

Adjusted close (split+bonus only):
        adj_close_sb[t] = P[t] / f[t]

  This gives a split-adjusted price series. Volume should be MULTIPLIED by f[t]
  for comparability (more shares after split). We don't adjust volume here —
  that's a separate Observation kind.

Dividend adjustment (subtractive, total-return style):
  For each dividend D_i with ex-date d_i (processing in REVERSE chronological
  order, so later dividends are applied first):

        adj_close[t] = adj_close[t] - D_i * (adj_close[d_i] / P[d_i])

  for all t < d_i, where adj_close[d_i] is the close on the ex-date AFTER all
  later adjustments have been applied.

  This is the standard CRSP-style total-return adjustment: it preserves the
  property that if you held the stock through the dividend, your effective
  entry price is reduced by the dividend amount relative to the price you paid.

Final adjusted close:
        adj_close[t] = (P[t] / f[t]) - sum_of_dividend_adjustments

Every adjusted price observation carries:
  - provenance.source = "investorlens"  (so it's distinguishable from Yahoo)
  - provenance.extraction_method = "derived"
  - provenance.notes = JSON dump of the adjustment decomposition
    (which corp actions contributed, with their factors)

This makes every adjusted price DECOMPOSABLE: "why did Company X get adj_close
of 1234.5 on date Y?" → "raw close 1300, split factor 0.5 (5:1 split on date Z),
dividend adjustment 15.5 (Rs.10 dividend on date W)".
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from ..ids import make_id
from ..models import CorporateAction, CorporateActionType, Observation, ObservationKind, Provenance
from ..models.provenance import Confidence, ExtractionMethod

__all__ = [
    "build_adjusted_prices",
    "compute_adjustment_factor",
    "adjust_prices_for_security",
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-action adjustment factor
# ---------------------------------------------------------------------------


def compute_adjustment_factor(ca: CorporateAction) -> float:
    """Compute the multiplicative adjustment factor for a single corp action.

    Returns 1.0 for actions that don't have a multiplicative effect on prices
    (dividends, mergers, symbol changes, etc.). Those are handled separately.

    For SPLIT (ratio n:d): factor = n / d
        e.g. 5:1 split → factor = 5.0 (prices before ex-date are divided by 5)
    For BONUS (ratio n:d, where d shares held → n bonus): factor = (d + n) / d
        e.g. 1:1 bonus → factor = 2.0 (prices before ex-date are divided by 2)
    """
    if ca.action_type == CorporateActionType.SPLIT:
        if ca.ratio_numerator and ca.ratio_denominator and ca.ratio_denominator > 0:
            return ca.ratio_numerator / ca.ratio_denominator
        log.warning("SPLIT corp action %s missing ratio — treating as no-op.", ca.id)
        return 1.0
    if ca.action_type == CorporateActionType.BONUS:
        if ca.ratio_numerator and ca.ratio_denominator and ca.ratio_denominator > 0:
            return (ca.ratio_denominator + ca.ratio_numerator) / ca.ratio_denominator
        log.warning("BONUS corp action %s missing ratio — treating as no-op.", ca.id)
        return 1.0
    # Other action types have no simple multiplicative factor.
    return 1.0


# ---------------------------------------------------------------------------
# Adjustment decomposition (for transparency)
# ---------------------------------------------------------------------------


@dataclass
class AdjustmentDecomposition:
    """A human-readable record of how a single adjusted price was computed.

    Every adjusted-price observation carries one of these (serialized to JSON)
    in its provenance.notes, making the adjustment fully decomposable.
    """

    raw_close: float
    cumulative_split_bonus_factor: float
    dividend_adjustments: list[tuple[str, float, float]]  # (ex_date, dividend_amount, price_adjustment)
    final_adjusted_close: float

    def to_json(self) -> str:
        return json.dumps(
            {
                "raw_close": self.raw_close,
                "cumulative_split_bonus_factor": self.cumulative_split_bonus_factor,
                "dividend_adjustments": [
                    {"ex_date": d, "dividend_amount": amt, "price_adjustment": adj}
                    for d, amt, adj in self.dividend_adjustments
                ],
                "final_adjusted_close": self.final_adjusted_close,
            },
            sort_keys=True,
        )


# ---------------------------------------------------------------------------
# Per-security adjustment
# ---------------------------------------------------------------------------


def adjust_prices_for_security(
    *,
    security_id: str,
    raw_closes: list[tuple[date, float]],  # [(date, close), ...] sorted ascending
    corp_actions: list[CorporateAction],
    retrieved_at: datetime | None = None,
) -> list[Observation]:
    """Compute adjusted close prices for a single security.

    Args:
        security_id: the Security ID (used as subject_id on output observations).
        raw_closes: list of (date, raw_close) sorted ascending by date.
            Only days with a non-None raw close should be included.
        corp_actions: corp actions for this security (any action types).
            Actions with ex_date outside the price range are still applied
            (they affect prices BEFORE the ex_date).
        retrieved_at: UTC timestamp for provenance. Defaults to now().

    Returns:
        List of `Observation` records with kind=PRICE_CLOSE_ADJ, one per
        raw_close input. Each observation's provenance.notes contains the
        AdjustmentDecomposition JSON for full transparency.

    If a corp action is a type we don't auto-adjust (merger, demerger, etc.),
    a warning is logged and the action is skipped.
    """
    if not raw_closes:
        return []

    # Provenance template for derived observations.
    prov_kwargs: dict = {
        "source": "investorlens",
        "extraction_method": ExtractionMethod.DERIVED,
        "confidence": Confidence.HIGH,
    }
    if retrieved_at is not None:
        prov_kwargs["retrieved_at"] = retrieved_at
    base_prov = Provenance(**prov_kwargs)

    # 1. Sort corp actions by ex_date ascending. Filter to ones we know how to handle.
    supported_types = {
        CorporateActionType.SPLIT,
        CorporateActionType.BONUS,
        CorporateActionType.DIVIDEND,
    }
    unsupported = [ca for ca in corp_actions if ca.action_type not in supported_types]
    if unsupported:
        log.info(
            "Security %s: %d corp actions of unsupported types (merger/demerger/etc.) — skipped for now.",
            security_id,
            len(unsupported),
        )

    splits_bonuses = sorted(
        [ca for ca in corp_actions if ca.action_type in (CorporateActionType.SPLIT, CorporateActionType.BONUS)],
        key=lambda c: c.ex_date,
    )
    dividends = sorted(
        [ca for ca in corp_actions if ca.action_type == CorporateActionType.DIVIDEND],
        key=lambda c: c.ex_date,
    )

    # 2. Compute cumulative split+bonus factor for each day.
    # For day t, f[t] = product of factors for all splits/bonuses with ex_date > t.
    # Walking forward through sorted (date, close) pairs:
    #   - As we cross each ex_date going forward, the factor for FUTURE days decreases.
    # Actually it's easier to think of it as:
    #   - The cumulative factor DECREASES as we move FORWARD in time (each split
    #     reduces the factor by its own factor multiplier).
    #   - For day t (the earliest day), factor = product of ALL split/bonus factors.
    #   - For day t (the latest day), factor = 1.0 (no adjustments apply after).
    # So: walking forward, at each ex-date we DIVIDE the running factor by that action's factor.

    # Build a map: ex_date → cumulative factor reduction at that date.
    # Start: factor = product of all split/bonus factors (applies to all days before the earliest ex_date).
    total_factor = 1.0
    for ca in splits_bonuses:
        total_factor *= compute_adjustment_factor(ca)

    # Now walk through sorted days. Whenever we cross an ex_date, divide by that action's factor.
    # We need a pointer into splits_bonuses sorted ascending by ex_date.
    # factor_at[t] = total_factor / (product of factors for actions with ex_date <= t)
    # Equivalently: factor_at[t] = product of factors for actions with ex_date > t

    # Index ex_dates for quick lookup.
    factor_by_ex_date: dict[date, float] = {}  # date → factor at that ex_date (the reduction)
    for ca in splits_bonuses:
        factor_by_ex_date[ca.ex_date] = factor_by_ex_date.get(ca.ex_date, 1.0) * compute_adjustment_factor(ca)

    # 3. Compute the split+bonus-adjusted close for each day.
    adj_close_sb: list[tuple[date, float, float]] = []  # (date, adj_close_sb, factor)
    current_factor = total_factor  # factor that applies to the earliest day
    sb_idx = 0
    sb_dates_sorted = sorted(factor_by_ex_date.keys())

    for d, raw_close in raw_closes:
        # Cross any ex_dates we've passed.
        while sb_idx < len(sb_dates_sorted) and sb_dates_sorted[sb_idx] <= d:
            current_factor /= factor_by_ex_date[sb_dates_sorted[sb_idx]]
            sb_idx += 1
        # current_factor now applies to day d (it's the product of all factors with ex_date > d)
        adj = raw_close / current_factor if current_factor > 0 else raw_close
        adj_close_sb.append((d, adj, current_factor))

    # 4. Apply dividend adjustments (subtractive, total-return style).
    # Walk dividends in REVERSE chronological order. For each dividend D with ex_date d_i,
    # the price adjustment for all t < d_i is: D * (adj_close[d_i] / close[d_i])
    # where adj_close[d_i] is the close on the ex-date AFTER all later adjustments applied.
    # If we don't have a price on d_i itself, we use the closest earlier price.

    # Build a dict: date → (adj_close_sb, raw_close) for quick lookup.
    adj_close_by_date: dict[date, tuple[float, float]] = {d: (adj, raw) for d, adj, raw in zip(
        [x[0] for x in adj_close_sb],
        [x[1] for x in adj_close_sb],
        [raw_closes[i][1] for i in range(len(raw_closes))],
    )}

    # Apply dividends in reverse chronological order.
    dividend_adjustments_per_day: dict[date, list[tuple[str, float, float]]] = {d: [] for d, _, _ in adj_close_sb}
    final_adj_close: dict[date, float] = {d: adj for d, adj, _ in adj_close_sb}

    for div in reversed(dividends):
        if div.amount_per_share is None or div.amount_per_share <= 0:
            continue
        D = float(div.amount_per_share)
        # Find the close on the ex-date (or the closest earlier day).
        ex_d = div.ex_date
        # Look up adj_close on the ex-date (or closest earlier).
        # For simplicity: find the first date >= ex_d. If none, skip this dividend.
        candidate_dates = sorted([d for d in adj_close_by_date if d >= ex_d])
        if not candidate_dates:
            continue
        ref_date = candidate_dates[0]
        ref_adj_close, ref_raw_close = adj_close_by_date[ref_date]
        if ref_raw_close == 0:
            continue
        # Apply to all days BEFORE ex_d.
        for d, (adj_sb, _) in adj_close_by_date.items():
            if d < ex_d:
                price_adj = D * (final_adj_close.get(ref_date, ref_adj_close) / ref_raw_close)
                final_adj_close[d] = final_adj_close.get(d, adj_sb) - price_adj
                dividend_adjustments_per_day[d].append((ex_d.isoformat(), D, price_adj))

    # 5. Build Observation records.
    observations: list[Observation] = []
    for d, raw_close in raw_closes:
        adj_sb = next(adj for dd, adj, _ in adj_close_sb if dd == d)
        factor = next(f for dd, _, f in adj_close_sb if dd == d)
        final = final_adj_close[d]
        decomposition = AdjustmentDecomposition(
            raw_close=raw_close,
            cumulative_split_bonus_factor=factor,
            dividend_adjustments=dividend_adjustments_per_day[d],
            final_adjusted_close=final,
        )
        prov = base_prov.model_copy(update={"notes": decomposition.to_json()})
        observations.append(
            Observation(
                subject_id=security_id,
                kind=ObservationKind.PRICE_CLOSE_ADJ,
                period=d.isoformat(),
                as_of=d,
                value=round(final, 6),
                unit="INR/share",
                currency="INR",
                data_status="observed",
                confidence=base_prov.confidence,
                provenance=prov,
            )
        )

    observations.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return observations


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def build_adjusted_prices(
    *,
    price_observations: list[Observation],
    corp_actions: list[CorporateAction],
    retrieved_at: datetime | None = None,
) -> list[Observation]:
    """Build adjusted-price observations for all securities in the input.

    Args:
        price_observations: list of Observation records with kind=PRICE_CLOSE.
            Only OBSERVED ones with non-None values are used; UNAVAILABLE ones
            are skipped.
        corp_actions: list of CorporateAction records. Will be filtered per-security.

    Returns:
        List of Observation records with kind=PRICE_CLOSE_ADJ.
    """
    # Index corp actions by security_id.
    ca_by_security: dict[str, list[CorporateAction]] = {}
    for ca in corp_actions:
        ca_by_security.setdefault(ca.security_id, []).append(ca)

    # Index price observations by subject_id (== security_id).
    prices_by_security: dict[str, list[tuple[date, float]]] = {}
    for o in price_observations:
        if o.kind != ObservationKind.PRICE_CLOSE:
            continue
        if o.value is None:
            continue
        if o.data_status.value == "unavailable":
            continue
        try:
            v = float(o.value)
        except (TypeError, ValueError):
            continue
        prices_by_security.setdefault(o.subject_id, []).append((o.as_of, v))

    # Sort each security's prices ascending by date.
    for sid in prices_by_security:
        prices_by_security[sid].sort(key=lambda x: x[0])

    # Build adjusted prices per security.
    all_adj: list[Observation] = []
    for sid, raw_closes in prices_by_security.items():
        cas = ca_by_security.get(sid, [])
        adj = adjust_prices_for_security(
            security_id=sid,
            raw_closes=raw_closes,
            corp_actions=cas,
            retrieved_at=retrieved_at,
        )
        all_adj.extend(adj)

    all_adj.sort(key=lambda o: (o.subject_id, o.kind.value, o.as_of.isoformat()))
    return all_adj
