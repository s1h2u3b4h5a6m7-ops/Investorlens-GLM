"""Tests for the Evidence model (investorlens.models.evidence)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investorlens.models import Evidence, SourceType
from investorlens.models.provenance import Confidence, Provenance


@pytest.fixture
def prov() -> Provenance:
    return Provenance(source="investorlens", confidence=Confidence.MEDIUM)


class TestEvidence:
    def test_id_derived_from_edge_and_source(self, prov: Provenance) -> None:
        e1 = Evidence(
            edge_id="edge_abc",
            fact="Raw material cost is 65% of revenue",
            source_type=SourceType.ANNUAL_REPORT,
            source_document_id="doc_xyz",
            page=42,
            provenance=prov,
        )
        e2 = Evidence(
            edge_id="edge_abc",
            fact="Raw material cost is 65% of revenue",
            source_type=SourceType.ANNUAL_REPORT,
            source_document_id="doc_xyz",
            page=42,
            provenance=prov,
        )
        assert e1.id == e2.id
        assert e1.id.startswith("val_")

    def test_id_changes_with_different_edge(self, prov: Provenance) -> None:
        e1 = Evidence(edge_id="edge_abc", fact="fact 1", source_type=SourceType.DRHP, provenance=prov)
        e2 = Evidence(edge_id="edge_def", fact="fact 1", source_type=SourceType.DRHP, provenance=prov)
        assert e1.id != e2.id

    def test_id_changes_with_different_page(self, prov: Provenance) -> None:
        e1 = Evidence(edge_id="edge_abc", fact="fact", source_type=SourceType.DRHP,
                      source_document_id="doc_1", page=10, provenance=prov)
        e2 = Evidence(edge_id="edge_abc", fact="fact", source_type=SourceType.DRHP,
                      source_document_id="doc_1", page=20, provenance=prov)
        assert e1.id != e2.id

    def test_fact_required(self, prov: Provenance) -> None:
        with pytest.raises(ValidationError):
            Evidence(edge_id="edge_abc", fact="", source_type=SourceType.DRHP, provenance=prov)

    def test_edge_id_required(self, prov: Provenance) -> None:
        with pytest.raises(ValidationError):
            Evidence(fact="some fact", source_type=SourceType.DRHP, provenance=prov)  # type: ignore[call-arg]

    def test_source_type_enum(self, prov: Provenance) -> None:
        for st in SourceType:
            e = Evidence(edge_id="e", fact="f", source_type=st, provenance=prov)
            assert e.source_type == st

    def test_default_confidence_is_medium(self, prov: Provenance) -> None:
        e = Evidence(edge_id="e", fact="f", source_type=SourceType.DRHP, provenance=prov)
        assert e.confidence == Confidence.MEDIUM

    def test_default_extraction_method_is_manual(self, prov: Provenance) -> None:
        e = Evidence(edge_id="e", fact="f", source_type=SourceType.DRHP, provenance=prov)
        assert e.extraction_method == "manual"

    def test_optional_fields(self, prov: Provenance) -> None:
        e = Evidence(
            edge_id="edge_abc",
            fact="API imports from China are ~70% of total API consumption",
            source_type=SourceType.CREDIT_RATING_RATIONALE,
            source_title="CRISIL Rating Rationale: Sun Pharma, Sep 2024",
            source_organisation="CRISIL",
            source_url="https://crisil.com/...",
            page=3,
            section="Key Rating Drivers",
            table="table_2",
            confidence=Confidence.HIGH,
            extraction_method="pdf_parse",
            notes="Specifically refers to KSM imports",
            provenance=prov,
        )
        assert e.source_organisation == "CRISIL"
        assert e.section == "Key Rating Drivers"
        assert e.confidence == Confidence.HIGH
        assert e.extraction_method == "pdf_parse"
        assert "KSM" in e.notes

    def test_source_title_used_when_no_document_id(self, prov: Provenance) -> None:
        """When source_document_id is None, the ID should still be deterministic
        using source_title as a fallback."""
        e1 = Evidence(edge_id="edge_abc", fact="f", source_type=SourceType.ANNUAL_REPORT,
                      source_title="Sun Pharma AR FY2024", page=42, provenance=prov)
        e2 = Evidence(edge_id="edge_abc", fact="f", source_type=SourceType.ANNUAL_REPORT,
                      source_title="Sun Pharma AR FY2024", page=42, provenance=prov)
        assert e1.id == e2.id
