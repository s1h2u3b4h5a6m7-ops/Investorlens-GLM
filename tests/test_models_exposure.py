"""Tests for the Exposure model (investorlens.models.exposure)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investorlens.models import (
    Exposure,
    ExposureDirection,
    FinancialMetric,
    HedgeStatus,
    PricingPower,
    TransmissionMechanism,
)
from investorlens.models.provenance import Confidence, Provenance
from investorlens.models.valuechain import ValidationStatus


@pytest.fixture
def prov() -> Provenance:
    return Provenance(source="investorlens", confidence=Confidence.HYPOTHESIZED)


class TestExposure:
    def test_id_derived_from_company_and_driver(self, prov: Provenance) -> None:
        e1 = Exposure(
            company_id="sec_abc", driver_id="drv_xyz",
            driver_type="macro_driver",
            direction=ExposureDirection.NEGATIVE,
            transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
            provenance=prov,
        )
        e2 = Exposure(
            company_id="sec_abc", driver_id="drv_xyz",
            driver_type="macro_driver",
            direction=ExposureDirection.NEGATIVE,
            transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
            provenance=prov,
        )
        assert e1.id == e2.id
        assert e1.id.startswith("exp_")

    def test_id_changes_with_different_driver(self, prov: Provenance) -> None:
        e1 = Exposure(company_id="sec_abc", driver_id="drv_xyz", driver_type="macro_driver",
                       direction=ExposureDirection.NEGATIVE,
                       transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        e2 = Exposure(company_id="sec_abc", driver_id="drv_def", driver_type="macro_driver",
                       direction=ExposureDirection.NEGATIVE,
                       transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e1.id != e2.id

    def test_id_changes_with_different_company(self, prov: Provenance) -> None:
        e1 = Exposure(company_id="sec_abc", driver_id="drv_xyz", driver_type="macro_driver",
                       direction=ExposureDirection.NEGATIVE,
                       transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        e2 = Exposure(company_id="sec_def", driver_id="drv_xyz", driver_type="macro_driver",
                       direction=ExposureDirection.NEGATIVE,
                       transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e1.id != e2.id

    def test_required_fields(self, prov: Provenance) -> None:
        with pytest.raises(ValidationError):
            Exposure(company_id="sec_abc", driver_id="drv_xyz", provenance=prov)  # type: ignore[call-arg]

    def test_default_validation_status_is_hypothesized(self, prov: Provenance) -> None:
        e = Exposure(company_id="sec_abc", driver_id="drv_xyz", driver_type="macro_driver",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e.validation_status == ValidationStatus.HYPOTHESIZED

    def test_default_pricing_power_is_medium(self, prov: Provenance) -> None:
        e = Exposure(company_id="sec_abc", driver_id="drv_xyz", driver_type="macro_driver",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e.pricing_power == PricingPower.MEDIUM

    def test_default_hedge_status_is_unhedged(self, prov: Provenance) -> None:
        e = Exposure(company_id="sec_abc", driver_id="drv_xyz", driver_type="macro_driver",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e.hedge_status == HedgeStatus.UNHEDGED

    def test_default_financial_metric_is_gross_margin(self, prov: Provenance) -> None:
        e = Exposure(company_id="sec_abc", driver_id="drv_xyz", driver_type="macro_driver",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e.financial_metric_impacted == FinancialMetric.GROSS_MARGIN

    def test_all_directions_computable(self, prov: Provenance) -> None:
        for d in ExposureDirection:
            e = Exposure(company_id="a", driver_id="b", driver_type="macro_driver",
                         direction=d, transmission_mechanism=TransmissionMechanism.OTHER, provenance=prov)
            assert e.direction == d

    def test_all_transmission_mechanisms_computable(self, prov: Provenance) -> None:
        for tm in TransmissionMechanism:
            e = Exposure(company_id="a", driver_id="b", driver_type="macro_driver",
                         direction=ExposureDirection.NEGATIVE, transmission_mechanism=tm, provenance=prov)
            assert e.transmission_mechanism == tm

    def test_mixed_direction_for_fx_exposure(self, prov: Provenance) -> None:
        """A pharma company with both API imports and US exports has MIXED USD/INR exposure."""
        e = Exposure(
            company_id="sec_sunpharma", driver_id="drv_fx_usd_inr",
            driver_type="macro_driver",
            direction=ExposureDirection.MIXED,
            transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
            pricing_power=PricingPower.MEDIUM,
            hedge_status=HedgeStatus.PARTIALLY_HEDGED,
            pass_through_lag_days=90,
            magnitude_estimate="1% INR depreciation = ~0.3% margin impact (net of export benefit)",
            financial_metric_impacted=FinancialMetric.EBITDA_MARGIN,
            notes="Negative on KSM imports (~60% of API cost); positive on US export revenue (~40% of revenue). Net effect depends on import/export ratio.",
            provenance=prov,
        )
        assert e.direction == ExposureDirection.MIXED
        assert e.pricing_power == PricingPower.MEDIUM
        assert e.hedge_status == HedgeStatus.PARTIALLY_HEDGED
        assert e.pass_through_lag_days == 90
        assert "0.3% margin impact" in e.magnitude_estimate
        assert e.financial_metric_impacted == FinancialMetric.EBITDA_MARGIN

    def test_pass_through_lag_optional(self, prov: Provenance) -> None:
        e = Exposure(company_id="a", driver_id="b", driver_type="macro_driver",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST, provenance=prov)
        assert e.pass_through_lag_days is None

    def test_magnitude_percent_optional(self, prov: Provenance) -> None:
        e = Exposure(company_id="a", driver_id="b", driver_type="macro_driver",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
                     magnitude_percent=0.5, provenance=prov)
        assert e.magnitude_percent == 0.5

    def test_raw_material_driver_type(self, prov: Provenance) -> None:
        """Exposures can be to raw_materials, not just macro_drivers."""
        e = Exposure(company_id="sec_ultratech", driver_id="rm_coal",
                     driver_type="raw_material",
                     direction=ExposureDirection.NEGATIVE,
                     transmission_mechanism=TransmissionMechanism.RAW_MATERIAL_COST,
                     pricing_power=PricingPower.LOW,
                     magnitude_estimate="Coal is ~40% of cost; 10% coal price increase = ~4% cost increase",
                     provenance=prov)
        assert e.driver_type == "raw_material"
        assert e.pricing_power == PricingPower.LOW

    def test_positive_direction_for_exporter(self, prov: Provenance) -> None:
        """An IT services company benefits from INR depreciation (positive exposure)."""
        e = Exposure(company_id="sec_tcs", driver_id="drv_fx_usd_inr",
                     driver_type="macro_driver",
                     direction=ExposureDirection.POSITIVE,
                     transmission_mechanism=TransmissionMechanism.FX_TRANSLATION,
                     magnitude_estimate="1% INR depreciation = ~0.3-0.5% revenue increase",
                     financial_metric_impacted=FinancialMetric.REVENUE,
                     provenance=prov)
        assert e.direction == ExposureDirection.POSITIVE
        assert e.transmission_mechanism == TransmissionMechanism.FX_TRANSLATION
