"""
Evidence model for Phase 3.2 (Source Hierarchy).

An Evidence record links a specific fact (extracted from a source document)
to the value-chain edges it supports. When evidence is added, the corresponding
edges can be upgraded from HYPOTHESIZED → WEAKLY_SUPPORTED → VALIDATED.

Fields:
  - edge_id: the ValueChainEdge ID this evidence supports
  - fact: the specific claim (e.g. "Raw material cost is 65% of revenue")
  - source_document_id: ID of the Document record
  - source_type: drhp | annual_report | credit_rating_rationale | other
  - page: page number in the document
  - section: section heading
  - table: table identifier (if applicable)
  - confidence: how confident we are in this evidence (high/medium/low)
  - extraction_method: manual | pdf_parse | llm_extracted
  - notes: free-text caveats

The Evidence ID is derived from (edge_id, source_document_id, page) so
re-running the research pipeline upserts rather than duplicates.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..ids import make_id
from .provenance import Confidence, Provenance

__all__ = [
    "Evidence",
    "SourceType",
]


class SourceType(str, Enum):
    """Type of research source document."""

    DRHP = "drhp"                          # Draft Red Herring Prospectus
    ANNUAL_REPORT = "annual_report"        # Company annual report
    CREDIT_RATING_RATIONALE = "credit_rating_rationale"  # CRISIL/ICRA/India Ratings
    CONCALL_TRANSCRIPT = "concall_transcript"  # Earnings call transcript
    INVESTOR_PRESENTATION = "investor_presentation"
    REGULATORY_FILING = "regulatory_filing"  # SEBI, RBI, MCA filings
    TRADE_STATISTICS = "trade_statistics"    # DGCI&S,Tradestat
    INDUSTRY_REPORT = "industry_report"      # Industry association reports
    OTHER = "other"


class Evidence(BaseModel):
    """A specific fact extracted from a source document that supports a value-chain edge.

    When evidence is added for an edge, the edge's validation_status can be
    upgraded:
      - No evidence → HYPOTHESIZED
      - 1 evidence → WEAKLY_SUPPORTED
      - 2+ evidence from independent sources → VALIDATED
    """

    edge_id: str = Field(..., description="ID of the ValueChainEdge this evidence supports")
    fact: str = Field(..., min_length=1, description="The specific claim, e.g. 'Raw material cost is 65% of revenue'")

    source_type: SourceType
    source_document_id: str | None = Field(default=None, description="ID of the Document record (if registered)")
    source_title: str | None = Field(default=None, description="Human-readable title of the source")
    source_url: str | None = None
    source_organisation: str | None = Field(default=None, description="e.g. 'CRISIL', 'Sun Pharma AR FY2024', 'SEBI DRHP'")

    page: int | None = None
    section: str | None = None
    table: str | None = None

    confidence: Confidence = Confidence.MEDIUM
    extraction_method: Literal["manual", "pdf_parse", "llm_extracted", "derived"] = "manual"
    notes: str | None = None

    provenance: Provenance

    @model_validator(mode="after")
    def _compute_id(self) -> "Evidence":
        object.__setattr__(
            self,
            "id",
            make_id(
                "val",
                {
                    "edge_id": self.edge_id,
                    "source_document_id": self.source_document_id or self.source_title or "",
                    "page": self.page,
                },
            ),
        )
        return self

    id: str = Field(default="")
