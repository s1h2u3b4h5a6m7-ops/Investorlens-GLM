"""Tests for the Provenance model."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from investorlens.models import Confidence, ExtractionMethod, Provenance


class TestProvenance:
    def test_required_fields(self) -> None:
        # source + retrieved_at (auto-set) is the minimum.
        p = Provenance(source="nse")
        assert p.source == "nse"
        assert p.retrieved_at.tzinfo is not None  # auto-set to UTC now
        assert p.confidence == Confidence.MEDIUM  # default

    def test_source_required(self) -> None:
        with pytest.raises(ValidationError):
            Provenance()  # type: ignore[call-arg]

    def test_extraction_method_enum(self) -> None:
        p = Provenance(source="nse", extraction_method=ExtractionMethod.BULK_DOWNLOAD)
        assert p.extraction_method == ExtractionMethod.BULK_DOWNLOAD

        # String input also works (Pydantic coerces enum).
        p2 = Provenance(source="nse", extraction_method="html_scrape")
        assert p2.extraction_method == ExtractionMethod.HTML_SCRAPE

    def test_invalid_extraction_method_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Provenance(source="nse", extraction_method="magic")  # type: ignore[arg-type]

    def test_confidence_enum(self) -> None:
        for c in Confidence:
            p = Provenance(source="x", confidence=c)
            assert p.confidence == c

    def test_compact_dict_strips_none(self) -> None:
        p = Provenance(source="nse", confidence=Confidence.HIGH)
        d = p.to_compact_dict()
        # retrieved_at + source + confidence should be present.
        assert "source" in d
        assert "retrieved_at" in d
        assert "confidence" in d
        # Optional fields that were not set should be absent.
        assert "page" not in d
        assert "notes" not in d
        assert "source_url" not in d

    def test_explicit_retrieved_at_preserved(self) -> None:
        ts = datetime(2024, 9, 30, 18, 30, tzinfo=timezone.utc)
        p = Provenance(source="nse", retrieved_at=ts)
        assert p.retrieved_at == ts
