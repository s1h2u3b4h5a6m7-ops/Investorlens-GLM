"""Tests for the core domain models (investorlens.models.core)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from investorlens.models import (
    Company,
    CorporateAction,
    CorporateActionType,
    DataStatus,
    Document,
    ISINMaster,
    Industry,
    Observation,
    ObservationKind,
    Provenance,
    Sector,
    Security,
    SecurityType,
    Source,
    SourceKind,
)


@pytest.fixture
def prov() -> Provenance:
    return Provenance(source="nse")


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class TestCompany:
    def test_id_derived_from_isin(self, prov: Provenance) -> None:
        c1 = Company(name="Reliance Industries Ltd", isin="INE002A01018", provenance=prov)
        c2 = Company(name="Reliance Industries Ltd", isin="INE002A01018", provenance=prov)
        assert c1.id == c2.id
        assert c1.id.startswith("co_")

    def test_id_changes_with_isin(self, prov: Provenance) -> None:
        c1 = Company(name="X", isin="INE002A01018", provenance=prov)
        c2 = Company(name="X", isin="INE002A01019", provenance=prov)
        assert c1.id != c2.id

    def test_id_falls_back_to_name_when_no_isin(self, prov: Provenance) -> None:
        c1 = Company(name="X Private", nse_symbol="XPRIV", provenance=prov)
        c2 = Company(name="X Private", nse_symbol="XPRIV", provenance=prov)
        assert c1.id == c2.id
        assert c1.id.startswith("co_")

    def test_name_required(self, prov: Provenance) -> None:
        with pytest.raises(ValidationError):
            Company(name="", provenance=prov)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Security & ISINMaster
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_id_derived_from_isin(self, prov: Provenance) -> None:
        s1 = Security(isin="INE002A01018", company_id="co_x", symbol="RELIANCE", provenance=prov)
        s2 = Security(isin="INE002A01018", company_id="co_x", symbol="RELIANCE", provenance=prov)
        assert s1.id == s2.id
        assert s1.id.startswith("sec_")

    def test_security_type_default_equity(self, prov: Provenance) -> None:
        s = Security(isin="INE002A01018", company_id="co_x", symbol="RELIANCE", provenance=prov)
        assert s.security_type == SecurityType.EQUITY


class TestISINMaster:
    def test_id_and_isin_independent(self, prov: Provenance) -> None:
        m = ISINMaster(isin="INE002A01018", company_name="Reliance Industries Ltd", provenance=prov)
        assert m.id.startswith("isin_")
        assert m.isin == "INE002A01018"

    def test_isin_length_validated(self, prov: Provenance) -> None:
        with pytest.raises(ValidationError):
            ISINMaster(isin="INE", company_name="X", provenance=prov)


# ---------------------------------------------------------------------------
# Sector / Industry
# ---------------------------------------------------------------------------


class TestSectorIndustry:
    def test_sector_id_stable(self, prov: Provenance) -> None:
        s1 = Sector(name="Pharmaceuticals", provenance=prov)
        s2 = Sector(name="pharmaceuticals", provenance=prov)  # case-insensitive
        assert s1.id == s2.id

    def test_industry_tied_to_sector(self, prov: Provenance) -> None:
        sector = Sector(name="Pharmaceuticals", provenance=prov)
        ind = Industry(name="APIs", sector_id=sector.id, provenance=prov)
        assert ind.id.startswith("ind_")
        assert ind.sector_id == sector.id


# ---------------------------------------------------------------------------
# Source / Document
# ---------------------------------------------------------------------------


class TestSourceDocument:
    def test_source_id_stable_by_slug(self, prov: Provenance) -> None:
        s1 = Source(slug="nse", name="National Stock Exchange", kind=SourceKind.EXCHANGE, provenance=prov)
        s2 = Source(slug="NSE", name="National Stock Exchange of India", kind=SourceKind.EXCHANGE, provenance=prov)
        assert s1.id == s2.id  # slug case-insensitive

    def test_document_id_stable_by_url(self, prov: Provenance) -> None:
        d1 = Document(
            source_id="src_nse",
            title="Bhavcopy 2024-09-30",
            url="https://nseindia.com/api/reports?date=30-SEP-2024",
            document_type="bhavcopy",
            provenance=prov,
        )
        d2 = Document(
            source_id="src_nse",
            title="Bhavcopy 2024-09-30",
            url="https://nseindia.com/api/reports?date=30-SEP-2024",
            document_type="bhavcopy",
            provenance=prov,
        )
        assert d1.id == d2.id


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


class TestObservation:
    def test_id_includes_source(self, prov: Provenance) -> None:
        # Same fact from two different sources must produce two different observation IDs.
        o_nse = Observation(
            subject_id="sec_abc",
            kind=ObservationKind.PRICE_CLOSE,
            period="2024-09-30",
            as_of=date(2024, 9, 30),
            value=1842.35,
            unit="INR",
            currency="INR",
            provenance=Provenance(source="nse"),
        )
        o_bse = Observation(
            subject_id="sec_abc",
            kind=ObservationKind.PRICE_CLOSE,
            period="2024-09-30",
            as_of=date(2024, 9, 30),
            value=1842.30,
            unit="INR",
            currency="INR",
            provenance=Provenance(source="bse"),
        )
        assert o_nse.id != o_bse.id
        assert o_nse.id.startswith("obs_")

    def test_id_stable_for_same_input(self, prov: Provenance) -> None:
        kwargs = dict(
            subject_id="sec_abc",
            kind=ObservationKind.PRICE_CLOSE,
            period="2024-09-30",
            as_of=date(2024, 9, 30),
            value=1842.35,
            unit="INR",
            currency="INR",
            provenance=prov,
        )
        a = Observation(**kwargs)
        b = Observation(**kwargs)
        assert a.id == b.id

    def test_value_can_be_null(self, prov: Provenance) -> None:
        # "Known unavailable" is a valid observation.
        o = Observation(
            subject_id="sec_abc",
            kind=ObservationKind.REVENUE,
            period="FY2024",
            as_of=date(2024, 3, 31),
            value=None,
            data_status=DataStatus.UNAVAILABLE,
            provenance=prov,
        )
        assert o.value is None
        assert o.data_status == DataStatus.UNAVAILABLE

    def test_data_status_enum(self, prov: Provenance) -> None:
        o = Observation(
            subject_id="sec_abc",
            kind=ObservationKind.OTHER,
            period="FY2024",
            as_of=date(2024, 3, 31),
            value=42.0,
            data_status="estimated",
            provenance=prov,
        )
        assert o.data_status == DataStatus.ESTIMATED


# ---------------------------------------------------------------------------
# CorporateAction
# ---------------------------------------------------------------------------


class TestCorporateAction:
    def test_id_stable(self, prov: Provenance) -> None:
        a = CorporateAction(
            security_id="sec_abc",
            action_type=CorporateActionType.SPLIT,
            ex_date=date(2024, 9, 30),
            ratio_numerator=5,
            ratio_denominator=1,
            provenance=prov,
        )
        b = CorporateAction(
            security_id="sec_abc",
            action_type=CorporateActionType.SPLIT,
            ex_date=date(2024, 9, 30),
            ratio_numerator=5,
            ratio_denominator=1,
            provenance=prov,
        )
        assert a.id == b.id
        assert a.id.startswith("ca_")

    def test_dividend_amount_preserved_as_decimal(self, prov: Provenance) -> None:
        # Decimal precision must be preserved (not silently cast to float).
        a = CorporateAction(
            security_id="sec_abc",
            action_type=CorporateActionType.DIVIDEND,
            ex_date=date(2024, 9, 30),
            amount_per_share=Decimal("12.50"),
            provenance=prov,
        )
        assert a.amount_per_share == Decimal("12.50")
