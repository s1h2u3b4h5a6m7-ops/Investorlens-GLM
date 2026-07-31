"""
Provenance — the metadata that makes a fact trustworthy (or not).

Every important field in InvestorLens should ideally carry provenance:
  - where it came from
  - when it was retrieved
  - what reporting period it refers to
  - how it was extracted
  - how confident we are in it

This module defines the canonical Provenance record. Other modules (models,
io, pipelines) embed it as a nested field.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

__all__ = [
    "Provenance",
    "ExtractionMethod",
    "Confidence",
]


class ExtractionMethod(str, Enum):
    """How a value was obtained from its source."""

    OFFICIAL_API = "official_api"           # documented public API (NSE/BSE/RBI)
    BULK_DOWNLOAD = "bulk_download"          # a daily/monthly bulk file (e.g. bhavcopy)
    XLSX_PARSE = "xlsx_parse"                # parsed from an Excel file
    PDF_PARSE = "pdf_parse"                  # parsed from a PDF
    HTML_SCRAPE = "html_scrape"              # scraped from an HTML page
    MANUAL = "manual"                        # entered by a human
    DERIVED = "derived"                      # computed from other facts (e.g. adjusted price)
    LLM_EXTRACTED = "llm_extracted"          # extracted by an LLM (treat as low-confidence until validated)


class Confidence(str, Enum):
    """Coarse-grained confidence in a fact.

    Keep this small. The exact probability is rarely meaningful;
    these buckets are sufficient for filtering and review.
    """

    HIGH = "high"          # official machine-readable source, recently verified
    MEDIUM = "medium"      # official but stale, or human-entered from a primary doc
    LOW = "low"            # scraped, inferred, or LLM-extracted
    ESTIMATED = "estimated"  # explicitly estimated, not observed
    HYPOTHESIZED = "hypothesized"  # plausible but not yet empirically validated


class Provenance(BaseModel):
    """Canonical provenance record attached to every important fact.

    Required fields:
        - source: a short stable slug identifying the publisher (e.g. "nse", "rbi_dbie", "company_ar")
        - retrieved_at: when we fetched it (UTC ISO-8601)

    Optional fields:
        - source_url: direct link to the artifact
        - document_id: ID of a Document entity in the graph (for cited PDFs, Excel files, etc.)
        - reporting_period: the fiscal/calendar period this fact refers to (e.g. "FY2024", "2024-09-30")
        - page / section / table: locator inside a document
        - extraction_method: how the value was extracted
        - original_value: the raw value as it appeared (before normalization)
        - confidence: HIGH/MEDIUM/LOW/ESTIMATED/HYPOTHESIZED
        - notes: free-text caveats
    """

    source: str = Field(..., description="Stable slug for the publisher/dataset (e.g. 'nse', 'bse', 'rbi_dbie').")
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the fact was fetched/observed.",
    )

    source_url: HttpUrl | None = Field(default=None, description="Direct URL to the artifact, if available.")
    document_id: str | None = Field(default=None, description="ID of a Document entity in the knowledge graph.")
    reporting_period: str | None = Field(
        default=None,
        description="The period the fact refers to, e.g. 'FY2024', '2024-09-30', 'Q1-2025'.",
    )
    page: int | None = None
    section: str | None = None
    table: str | None = None

    extraction_method: ExtractionMethod | None = None
    original_value: str | None = Field(default=None, description="Raw value before normalization, if applicable.")
    confidence: Confidence = Confidence.MEDIUM
    notes: str | None = None

    def to_compact_dict(self) -> dict:
        """Compact, None-stripped representation for embedding in JSON outputs."""
        d = self.model_dump(mode="json", exclude_none=True)
        # retrieved_at stays as ISO string; HttpUrl becomes str
        return d
