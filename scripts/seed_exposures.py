"""
Seed exposure records for Phase 3.4 (Exposure Model).

Creates structured Exposure records for priority-sector companies, capturing
HOW each company is affected by macro drivers and raw materials — not just
THAT it's affected.

Key principle: "Do NOT assume input↑ ⇒ negative; pass-through matters."

For each company-driver pair, the Exposure record captures:
  - Direction (positive/negative/neutral/mixed)
  - Transmission mechanism (raw_material_cost/revenue/fx_translation/etc.)
  - Pricing power (high/medium/low/none)
  - Hedge status (unhedged/partially_hedged/fully_hedged)
  - Pass-through lag (days)
  - Magnitude estimate (qualitative)
  - Financial metric impacted (gross_margin/ebitda_margin/revenue/etc.)

Usage:
    python scripts/seed_exposures.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.ids import make_id  # noqa: E402
from investorlens.io import upsert_records  # noqa: E402
from investorlens.models import Exposure, Provenance  # noqa: E402
from investorlens.models.exposure import (  # noqa: E402
    ExposureDirection,
    FinancialMetric,
    HedgeStatus,
    PricingPower,
    TransmissionMechanism,
)
from investorlens.models.provenance import Confidence, ExtractionMethod  # noqa: E402
from investorlens.models.valuechain import ValidationStatus  # noqa: E402

log = logging.getLogger("seed_exposures")

EXPOSURES_PATH = ROOT / "data" / "processed" / "exposures.jsonl"


def _prov(notes: str) -> Provenance:
    return Provenance(
        source="investorlens",
        extraction_method=ExtractionMethod.DERIVED,
        confidence=Confidence.HYPOTHESIZED,
        notes=notes,
    )


def _sec(isin: str) -> str:
    return make_id("sec", {"isin": isin})


def _rm(name: str) -> str:
    return make_id("rm", {"name": name.lower().strip()})


def _drv(slug: str) -> str:
    return make_id("drv", {"slug": slug})


def _make_exposures() -> list[Exposure]:
    """Create exposure records for priority-sector companies."""
    prov_hyp = _prov("Seed exposure from publicly known industry structure; not yet validated with specific document evidence.")
    prov_ws = _prov("Seed exposure backed by well-known industry facts (CRISIL/ICRA reports).", )

    exposures: list[Exposure] = []

    # ═══════════════════════════════════════════════════════════════════
    # Sun Pharma (Pharmaceuticals)
    # ═══════════════════════════════════════════════════════════════════
    sunpharma = _sec("INE044A01026")

    # USD/INR — MIXED (hurts imports, helps exports)
    exposures.append(Exposure(
        company_id=sunpharma, driver_id=_drv("fx_usd_inr"), driver_type="macro_driver",
        direction=ExposureDirection.MIXED,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.MEDIUM,
        hedge_status=HedgeStatus.PARTIALLY_HEDGED,
        pass_through_lag_days=180,
        magnitude_estimate="1% INR depreciation = ~0.3% margin impact (net of export benefit)",
        magnitude_percent=0.3,
        financial_metric_impacted=FinancialMetric.EBITDA_MARGIN,
        notes="Negative on KSM imports (~60% of API cost); positive on US export revenue (~40% of revenue). Net effect depends on import/export ratio.",
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        provenance=prov_ws,
    ))

    # API/KSM prices — NEGATIVE (input cost)
    exposures.append(Exposure(
        company_id=sunpharma, driver_id=_rm("Active Pharmaceutical Ingredient (API)"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.MEDIUM,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="API is ~50% of formulation cost; 10% API price increase = ~5% cost increase",
        magnitude_percent=0.5,
        financial_metric_impacted=FinancialMetric.GROSS_MARGIN,
        notes="Sun Pharma is partially backward-integrated (makes some APIs in-house), which mitigates the impact.",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    # KSM prices — NEGATIVE (China-dependent input)
    exposures.append(Exposure(
        company_id=sunpharma, driver_id=_rm("Key Starting Material (KSM)"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.LOW,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=120,
        magnitude_estimate="KSM is ~60% of API cost; 10% KSM price increase = ~6% API cost increase",
        financial_metric_impacted=FinancialMetric.GROSS_MARGIN,
        notes="No hedging possible for KSM prices. China supply disruptions can cause sharp price spikes.",
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        provenance=prov_ws,
    ))

    # ═══════════════════════════════════════════════════════════════════
    # UltraTech Cement (Cement)
    # ═══════════════════════════════════════════════════════════════════
    ultratech = _sec("INE123A01024")

    # Coal — NEGATIVE (energy cost)
    exposures.append(Exposure(
        company_id=ultratech, driver_id=_rm("Coal"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.LOW,
        hedge_status=HedgeStatus.PARTIALLY_HEDGED,
        pass_through_lag_days=60,
        magnitude_estimate="Coal is ~40% of cement cost; 10% coal price increase = ~4% cost increase",
        magnitude_percent=0.4,
        financial_metric_impacted=FinancialMetric.EBITDA_MARGIN,
        notes="UltraTech has captive power plants (WHRS) which partially mitigate. Cement is a commodity — limited pricing power in short term.",
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        provenance=prov_ws,
    ))

    # USD/INR — NEGATIVE (coal/pet coke imports)
    exposures.append(Exposure(
        company_id=ultratech, driver_id=_drv("fx_usd_inr"), driver_type="macro_driver",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.LOW,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="1% INR depreciation = ~0.4% cost increase (imported coal/pet coke component)",
        magnitude_percent=0.4,
        financial_metric_impacted=FinancialMetric.EBITDA_MARGIN,
        notes="Impact limited to imported coal/pet coke portion (~30-40% of fuel mix). Domestic coal (Coal India linkage) not affected.",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    # CPI — POSITIVE (demand driver: inflation → construction activity)
    exposures.append(Exposure(
        company_id=ultratech, driver_id=_drv("cpi_combined_yoy"), driver_type="macro_driver",
        direction=ExposureDirection.POSITIVE,
        transmission_mechanism=TransmissionMechanism.DEMAND,
        pricing_power=PricingPower.MEDIUM,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=0,
        magnitude_estimate="Higher inflation often correlates with increased construction/infrastructure spending",
        financial_metric_impacted=FinancialMetric.REVENUE,
        notes="Indirect and lagged relationship. Demand depends more on government infrastructure spending and real estate cycle than on CPI directly.",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    # ═══════════════════════════════════════════════════════════════════
    # Apollo Tyres (Tyres)
    # ═══════════════════════════════════════════════════════════════════
    apollo = _sec("INE438A01025")

    # Natural Rubber — NEGATIVE (primary input cost)
    exposures.append(Exposure(
        company_id=apollo, driver_id=_rm("Natural Rubber"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.MEDIUM,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="NR is ~30% of RM cost; 10% NR price increase = ~3% cost increase. Price hikes typically follow in 2-3 months.",
        magnitude_percent=0.3,
        financial_metric_impacted=FinancialMetric.GROSS_MARGIN,
        notes="Tyre companies have moderate pricing power in replacement market (65% of sales) but limited in OEM contracts (annual rate contracts).",
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        provenance=prov_ws,
    ))

    # Crude Oil — NEGATIVE (indirect: synthetic rubber, carbon black)
    exposures.append(Exposure(
        company_id=apollo, driver_id=_rm("Crude Oil"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.MEDIUM,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=120,
        magnitude_estimate="Crude derivatives (SR, carbon black, process oils) are ~30% of RM cost; 10% crude increase = ~3% cost increase",
        magnitude_percent=0.3,
        financial_metric_impacted=FinancialMetric.GROSS_MARGIN,
        notes="Indirect exposure through synthetic rubber and carbon black. Pass-through is slower than for NR (3-4 months vs 2-3 months).",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    # USD/INR — NEGATIVE (NR imports from SE Asia)
    exposures.append(Exposure(
        company_id=apollo, driver_id=_drv("fx_usd_inr"), driver_type="macro_driver",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.MEDIUM,
        hedge_status=HedgeStatus.PARTIALLY_HEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="1% INR depreciation = ~0.2% cost increase (imported NR component)",
        magnitude_percent=0.2,
        financial_metric_impacted=FinancialMetric.EBITDA_MARGIN,
        notes="Impact limited to imported NR (~40% of total NR consumption). Domestic NR (Kerala) not affected. Apollo partially hedges FX.",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    # ═══════════════════════════════════════════════════════════════════
    # Asian Paints (Paints)
    # ═══════════════════════════════════════════════════════════════════
    asianpaints = _sec("INE210A01027")

    # TiO2 — NEGATIVE (largest RM cost item)
    exposures.append(Exposure(
        company_id=asianpaints, driver_id=_rm("Titanium Dioxide"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.HIGH,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="TiO2 is ~22% of RM cost; 10% TiO2 price increase = ~2.2% cost increase. Asian Paints typically passes through in 2-3 months.",
        magnitude_percent=0.22,
        financial_metric_impacted=FinancialMetric.GROSS_MARGIN,
        notes="Asian Paints has HIGH pricing power due to dominant market share (~50% decorative). Price hikes are industry-leading and followed by competitors.",
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        provenance=prov_ws,
    ))

    # Crude Oil — NEGATIVE (indirect: resins, solvents, TiO2 feedstock)
    exposures.append(Exposure(
        company_id=asianpaints, driver_id=_rm("Crude Oil"), driver_type="raw_material",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.HIGH,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="~50% of RM is crude-derived; 10% crude increase = ~5% cost increase. Pass-through typically in 2-3 months via price hikes.",
        magnitude_percent=0.5,
        financial_metric_impacted=FinancialMetric.GROSS_MARGIN,
        notes="Asian Paints' high pricing power means crude oil impact is mostly temporary (margin dip for 1-2 quarters, then recovery via price hikes).",
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        provenance=prov_ws,
    ))

    # USD/INR — NEGATIVE (TiO2 imports)
    exposures.append(Exposure(
        company_id=asianpaints, driver_id=_drv("fx_usd_inr"), driver_type="macro_driver",
        direction=ExposureDirection.NEGATIVE,
        transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
        pricing_power=PricingPower.HIGH,
        hedge_status=HedgeStatus.PARTIALLY_HEDGED,
        pass_through_lag_days=90,
        magnitude_estimate="1% INR depreciation = ~0.2% cost increase (imported TiO2 and other chemicals)",
        magnitude_percent=0.2,
        financial_metric_impacted=FinancialMetric.EBITDA_MARGIN,
        notes="Impact partially offset by Asian Paints' strong pricing power. Some forward cover on FX.",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    # CPI — POSITIVE (demand driver: real estate activity)
    exposures.append(Exposure(
        company_id=asianpaints, driver_id=_drv("cpi_combined_yoy"), driver_type="macro_driver",
        direction=ExposureDirection.POSITIVE,
        transmission_mechanism=TransmissionMechanism.DEMAND,
        pricing_power=PricingPower.HIGH,
        hedge_status=HedgeStatus.UNHEDGED,
        pass_through_lag_days=0,
        magnitude_estimate="Higher inflation often correlates with real estate activity, driving decorative paint demand",
        financial_metric_impacted=FinancialMetric.REVENUE,
        notes="Indirect and lagged. Paint demand tracks housing starts and renovation activity, not CPI directly.",
        validation_status=ValidationStatus.HYPOTHESIZED,
        provenance=prov_hyp,
    ))

    return exposures


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log.info("Seeding exposure records (Phase 3.4)...")

    exposures = _make_exposures()
    payload = [e.model_dump(mode="json", exclude_none=True) for e in exposures]
    upsert_records(EXPOSURES_PATH, payload, key="id")

    log.info("Wrote %d exposure records to %s", len(exposures), EXPOSURES_PATH)

    # Stats
    from collections import Counter
    by_direction = Counter(e.direction.value for e in exposures)
    by_validation = Counter(e.validation_status.value for e in exposures)
    by_pricing = Counter(e.pricing_power.value for e in exposures)
    log.info("  By direction: %s", dict(by_direction))
    log.info("  By validation: %s", dict(by_validation))
    log.info("  By pricing power: %s", dict(by_pricing))

    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
