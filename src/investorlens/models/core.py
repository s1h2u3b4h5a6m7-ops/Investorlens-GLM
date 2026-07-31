"""
Core domain models for InvestorLens.

These are the foundational entities the entire system is built on:
  - Company       — a real-world legal entity listed in India
  - Security      — a tradable instrument (equity / debt / etc.)
  - ISINMaster    — canonical identifier record per ISIN
  - Sector / Industry — classification nodes
  - Source        — a publisher / dataset (NSE, BSE, RBI, ...)
  - Document      — a specific file (annual report, bhavcopy zip, ...)
  - Observation   — a single fact at a point in time (price, EPS, revenue, ...)
  - CorporateAction — splits, bonuses, dividends, mergers, ...

Design principles:
  1. Every entity has a deterministic `id` (see investorlens.ids).
  2. Every entity has `provenance` (see investorlens.models.provenance).
  3. Models are Pydantic v2 BaseModel — validation is mandatory.
  4. Fields are typed; optional fields default to None, never silently invented.
  5. `data_status` records whether a fact is OBSERVED / ESTIMATED / HYPOTHESIZED / UNAVAILABLE.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from ..ids import make_id
from .provenance import Confidence, Provenance

__all__ = [
    "DataStatus",
    "Company",
    "SecurityType",
    "Security",
    "ISINMaster",
    "Sector",
    "Industry",
    "SourceKind",
    "Source",
    "Document",
    "ObservationKind",
    "Observation",
    "CorporateActionType",
    "CorporateAction",
]


class DataStatus(str, Enum):
    """Status of a fact — distinguishes facts from inferences from unknowns."""

    OBSERVED = "observed"              # extracted from a primary source
    ESTIMATED = "estimated"            # computed/derived, not directly observed
    HYPOTHESIZED = "hypothesized"      # plausible but not validated
    UNAVAILABLE = "unavailable"        # explicitly known to be missing


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class Company(BaseModel):
    """A real-world legal entity listed on Indian exchanges.

    The canonical anchor is `isin` (preferred) or `name + nse_symbol` (fallback).
    The ID is derived deterministically from the ISIN if present, else from name.
    """

    name: str = Field(..., min_length=1, description="Legal name of the company.")
    isin: str | None = Field(default=None, description="16-character ISIN, e.g. 'INE002A01018'.")
    nse_symbol: str | None = None
    bse_code: str | None = None
    sector_id: str | None = None
    industry_id: str | None = None
    incorporated_on: date | None = None
    active: bool = True

    # Provenance for the company record itself.
    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Company":
        # Stable ID — prefer ISIN, fall back to name+nse_symbol.
        if self.isin:
            object.__setattr__(self, "id", make_id("co", {"isin": self.isin}))
        else:
            object.__setattr__(self, "id", make_id("co", {"name": self.name, "nse_symbol": self.nse_symbol}))
        return self

    id: str = Field(default="", description="Deterministic ID, computed in validator.")


# ---------------------------------------------------------------------------
# Security & ISIN master
# ---------------------------------------------------------------------------


class SecurityType(str, Enum):
    EQUITY = "equity"
    DEBT = "debt"
    PREFERENCE = "preference"
    ETF = "etf"
    INDEX = "index"
    REIT = "reit"
    INVIT = "invit"
    OTHER = "other"


class Security(BaseModel):
    """A tradable instrument issued by a company.

    One company can have multiple securities (e.g. equity + multiple debt ISINs).
    """

    isin: str = Field(..., description="ISIN, the canonical security identifier.")
    company_id: str
    exchange: Literal["NSE", "BSE", "NSE+BSE", "OTHER"] = "NSE+BSE"
    symbol: str = Field(..., description="Trading symbol on the exchange.")
    security_type: SecurityType = SecurityType.EQUITY
    face_value: Decimal | None = None
    active: bool = True
    listed_on: date | None = None
    delisted_on: date | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Security":
        object.__setattr__(self, "id", make_id("sec", {"isin": self.isin}))
        return self

    id: str = Field(default="")


class ISINMaster(BaseModel):
    """One row per ISIN, normalized across NSE/BSE/Debt/ETF.

    This is the canonical identity anchor. Built once, updated incrementally.
    """

    isin: str = Field(..., min_length=12, max_length=16)
    company_name: str
    nse_symbol: str | None = None
    bse_code: str | None = None
    security_type: SecurityType = SecurityType.EQUITY
    exchange: Literal["NSE", "BSE", "NSE+BSE", "OTHER"] = "NSE+BSE"
    sector: str | None = None
    industry: str | None = None
    active: bool = True
    face_value: Decimal | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "ISINMaster":
        object.__setattr__(self, "id", make_id("isin", {"isin": self.isin}))
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Sector & Industry
# ---------------------------------------------------------------------------


class Sector(BaseModel):
    """A top-level economic sector (e.g. 'Pharmaceuticals', 'Cement')."""

    name: str
    description: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Sector":
        object.__setattr__(self, "id", make_id("sec", {"name": self.name.lower().strip()}))
        return self

    id: str = Field(default="")


class Industry(BaseModel):
    """A sub-sector industry classification (e.g. 'APIs' under 'Pharmaceuticals')."""

    name: str
    sector_id: str
    description: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Industry":
        object.__setattr__(
            self, "id", make_id("ind", {"name": self.name.lower().strip(), "sector_id": self.sector_id})
        )
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Source & Document
# ---------------------------------------------------------------------------


class SourceKind(str, Enum):
    EXCHANGE = "exchange"
    REGULATOR = "regulator"
    GOVERNMENT = "government"
    COMPANY = "company"
    RATING_AGENCY = "rating_agency"
    DATA_PROVIDER = "data_provider"
    NEWS = "news"
    OTHER = "other"


class Source(BaseModel):
    """A publisher or dataset (e.g. 'NSE', 'BSE', 'RBI DBIE', 'MOSPI', 'company_annual_report')."""

    slug: str = Field(..., description="Stable short slug, e.g. 'nse', 'rbi_dbie'.")
    name: str
    kind: SourceKind
    homepage: HttpUrl | None = None
    access_policy: str | None = Field(default=None, description="Free / API key required / etc.")
    rate_limit_per_sec: float | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Source":
        object.__setattr__(self, "id", make_id("src", {"slug": self.slug.lower().strip()}))
        return self

    id: str = Field(default="")


class Document(BaseModel):
    """A specific artifact (annual report PDF, bhavcopy zip, DRHP, ...)."""

    source_id: str
    title: str
    url: HttpUrl | None = None
    local_path: str | None = None
    content_sha256: str | None = Field(default=None, description="SHA-256 of the file bytes, for integrity.")
    published_on: date | None = None
    retrieved_at: datetime | None = None
    document_type: str = Field(..., description="e.g. 'annual_report', 'bhavcopy', 'drhp', 'credit_rating_rationale'.")
    pages: int | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Document":
        # Stable ID: source_id + title + (url or local_path); URL preferred.
        key = {"source_id": self.source_id, "title": self.title, "url": str(self.url) if self.url else None}
        object.__setattr__(self, "id", make_id("doc", key))
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Observation — the atomic unit of fact
# ---------------------------------------------------------------------------


class ObservationKind(str, Enum):
    PRICE_CLOSE = "price_close"
    PRICE_CLOSE_ADJ = "price_close_adj"  # split + dividend adjusted close (Yahoo "adjclose")
    PRICE_OPEN = "price_open"
    PRICE_HIGH = "price_high"
    PRICE_LOW = "price_low"
    VOLUME = "volume"
    TURNOVER = "turnover"
    MARKET_CAP = "market_cap"
    REVENUE = "revenue"
    EBITDA = "ebitda"
    NET_INCOME = "net_income"
    EPS = "eps"
    DEBT = "debt"
    RAW_MATERIAL_COST = "raw_material_cost"
    # Macro indicators (Milestone 1.5) — subject_id is a `drv_*` ID
    POLICY_RATE = "policy_rate"          # RBI repo / reverse repo / MSF / bank rate (%)
    CPI_YOY = "cpi_yoy"                  # Consumer Price Index year-over-year (%)
    FX_RATE = "fx_rate"                  # Reference exchange rate (e.g. USD/INR)
    OTHER = "other"


class Observation(BaseModel):
    """A single numeric/string fact at a point in time, with full provenance.

    This is the atomic unit of fact in InvestorLens. Everything else (knowledge
    graph, exposure matrix, scores) is built on top of observations.

    The ID is derived from (subject_id, kind, period, source_id) so that re-running
    the same fetcher upserts the same observation rather than creating a duplicate.
    """

    subject_id: str = Field(..., description="ID of the entity being observed (company, security, sector, ...).")
    kind: ObservationKind
    period: str = Field(..., description="e.g. '2024-09-30', 'FY2024', 'Q1-2025'.")
    as_of: date = Field(..., description="The date the observation refers to (period start or trade date).")
    value: float | int | str | None
    unit: str | None = Field(default=None, description="e.g. 'INR', 'INR/share', 'shares', 'ratio'.")
    currency: str | None = Field(default=None, description="ISO 4217 code, e.g. 'INR', 'USD'.")

    data_status: DataStatus = DataStatus.OBSERVED
    confidence: Confidence = Confidence.MEDIUM

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Observation":
        object.__setattr__(
            self,
            "id",
            make_id(
                "obs",
                {
                    "subject_id": self.subject_id,
                    "kind": self.kind.value,
                    "period": self.period,
                    "as_of": self.as_of.isoformat(),
                    "source_id": self.provenance.source,
                },
            ),
        )
        return self

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Corporate actions
# ---------------------------------------------------------------------------


class CorporateActionType(str, Enum):
    SPLIT = "split"
    BONUS = "bonus"
    RIGHTS = "rights"
    DIVIDEND = "dividend"
    MERGER = "merger"
    DEMERGER = "demerger"
    SYMBOL_CHANGE = "symbol_change"
    FACE_VALUE_CHANGE = "face_value_change"
    LISTING = "listing"
    DELISTING = "delisting"
    OTHER = "other"


class CorporateAction(BaseModel):
    """A corporate action affecting a security.

    Used to adjust historical prices so that price series are comparable over time.
    Every adjustment factor MUST be derivable from these records.
    """

    security_id: str
    action_type: CorporateActionType
    ex_date: date = Field(..., description="Ex-date — the date the action takes effect on prices.")
    record_date: date | None = None
    announcement_date: date | None = None

    # Numeric parameters (any of these may be None if not applicable to the action type).
    ratio_numerator: float | None = Field(default=None, description="e.g. 2 for a 2:1 bonus, 5 for a 5:1 split.")
    ratio_denominator: float | None = Field(default=None, description="e.g. 1 for a 2:1 bonus, 1 for a 5:1 split.")
    amount_per_share: Decimal | None = Field(default=None, description="Dividend amount per share, if applicable.")
    new_symbol: str | None = None
    new_face_value: Decimal | None = None
    notes: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "CorporateAction":
        object.__setattr__(
            self,
            "id",
            make_id(
                "ca",
                {
                    "security_id": self.security_id,
                    "action_type": self.action_type.value,
                    "ex_date": self.ex_date.isoformat(),
                },
            ),
        )
        return self

    id: str = Field(default="")
