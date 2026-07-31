"""Tests for the exposure matrix (investorlens.algorithms.exposure_matrix)."""

from __future__ import annotations

import pytest

from investorlens.algorithms.exposure_matrix import (
    ExposureMatrix,
    MatrixCell,
    build_exposure_matrix,
)


@pytest.fixture
def sample_exposures() -> list[dict]:
    return [
        {
            "id": "exp_001", "company_id": "sec_sunpharma", "driver_id": "drv_fx_usd_inr",
            "driver_type": "macro_driver", "direction": "mixed",
            "transmission_mechanism": "raw_material_cost",
            "pricing_power": "medium", "hedge_status": "partially_hedged",
            "pass_through_lag_days": 180, "magnitude_estimate": "1% INR depreciation = ~0.3% margin impact",
            "magnitude_percent": 0.3, "financial_metric_impacted": "ebitda_margin",
            "validation_status": "weakly_supported",
        },
        {
            "id": "exp_002", "company_id": "sec_sunpharma", "driver_id": "rm_api",
            "driver_type": "raw_material", "direction": "negative",
            "transmission_mechanism": "raw_material_cost",
            "pricing_power": "medium", "hedge_status": "unhedged",
            "pass_through_lag_days": 90, "magnitude_estimate": "API is ~50% of cost",
            "magnitude_percent": 0.5, "financial_metric_impacted": "gross_margin",
            "validation_status": "hypothesized",
        },
        {
            "id": "exp_003", "company_id": "sec_asianpaint", "driver_id": "rm_tio2",
            "driver_type": "raw_material", "direction": "negative",
            "transmission_mechanism": "raw_material_cost",
            "pricing_power": "high", "hedge_status": "unhedged",
            "pass_through_lag_days": 90, "magnitude_estimate": "TiO2 is ~22% of RM cost",
            "magnitude_percent": 0.22, "financial_metric_impacted": "gross_margin",
            "validation_status": "weakly_supported",
        },
    ]


@pytest.fixture
def sample_evidence() -> list[dict]:
    return [
        {
            "id": "val_001", "edge_id": "edge_abc",
            "fact": "Sun Pharma derives ~40% revenue from US generics",
            "source_type": "credit_rating_rationale",
            "source_organisation": "CRISIL", "page": 2,
        },
    ]


@pytest.fixture
def driver_labels() -> dict[str, str]:
    return {"drv_fx_usd_inr": "USD/INR", "rm_api": "Active Pharmaceutical Ingredient (API)", "rm_tio2": "Titanium Dioxide"}


@pytest.fixture
def company_labels() -> dict[str, str]:
    return {"sec_sunpharma": "Sun Pharma", "sec_asianpaint": "Asian Paints"}


class TestMatrixCell:
    def test_empty_cell(self) -> None:
        cell = MatrixCell(
            driver_id="drv_x", driver_label="X", driver_type="macro_driver",
            company_id="sec_y", company_label="Y",
        )
        assert cell.is_empty is True
        assert cell.direction == "—"
        assert cell.magnitude_percent is None
        assert cell.validation_status == "—"

    def test_populated_cell_properties(self) -> None:
        exp = {
            "direction": "mixed", "magnitude_percent": 0.3,
            "pricing_power": "medium", "hedge_status": "partially_hedged",
            "validation_status": "weakly_supported",
        }
        cell = MatrixCell(
            driver_id="drv_x", driver_label="X", driver_type="macro_driver",
            company_id="sec_y", company_label="Y",
            exposure=exp,
        )
        assert cell.is_empty is False
        assert cell.direction == "mixed"
        assert cell.magnitude_percent == 0.3
        assert cell.pricing_power == "medium"
        assert cell.hedge_status == "partially_hedged"
        assert cell.validation_status == "weakly_supported"

    def test_decomposition_empty(self) -> None:
        cell = MatrixCell(
            driver_id="drv_x", driver_label="X", driver_type="macro_driver",
            company_id="sec_y", company_label="Y",
        )
        d = cell.decomposition()
        assert "no exposure on record" in d

    def test_decomposition_populated(self) -> None:
        exp = {
            "direction": "negative", "transmission_mechanism": "raw_material_cost",
            "pricing_power": "high", "hedge_status": "unhedged",
            "pass_through_lag_days": 90, "magnitude_estimate": "TiO2 is ~22% of RM cost",
            "magnitude_percent": 0.22, "financial_metric_impacted": "gross_margin",
            "validation_status": "weakly_supported",
        }
        cell = MatrixCell(
            driver_id="rm_tio2", driver_label="Titanium Dioxide", driver_type="raw_material",
            company_id="sec_ap", company_label="Asian Paints",
            exposure=exp,
            evidence=[{"source_organisation": "CRISIL", "page": 3, "fact": "TiO2 is ~22% of RM cost"}],
        )
        d = cell.decomposition()
        assert "Titanium Dioxide" in d
        assert "Asian Paints" in d
        assert "negative" in d
        assert "raw_material_cost" in d
        assert "high" in d
        assert "90 days" in d
        assert "0.22%" in d
        assert "CRISIL" in d

    def test_to_dict(self) -> None:
        cell = MatrixCell(
            driver_id="drv_x", driver_label="X", driver_type="macro_driver",
            company_id="sec_y", company_label="Y",
            exposure={"direction": "negative", "validation_status": "hypothesized"},
        )
        d = cell.to_dict()
        assert d["driver_id"] == "drv_x"
        assert d["company_id"] == "sec_y"
        assert d["is_empty"] is False
        assert d["direction"] == "negative"
        assert d["decomposition"] is not None


class TestBuildExposureMatrix:
    def test_builds_matrix_from_exposures(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        assert matrix.n_drivers == 3  # USD/INR, API, TiO2
        assert matrix.n_companies == 2  # Sun Pharma, Asian Paints
        assert matrix.n_total == 6  # 3 × 2
        assert matrix.n_populated == 3  # 3 exposure records

    def test_empty_exposures_produces_empty_matrix(
        self,
        sample_evidence: list[dict],
    ) -> None:
        matrix = build_exposure_matrix([], sample_evidence)
        assert matrix.n_drivers == 0
        assert matrix.n_companies == 0
        assert matrix.n_total == 0

    def test_cell_lookup(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        # Sun Pharma × USD/INR should be populated
        cell = matrix.get_cell("drv_fx_usd_inr", "sec_sunpharma")
        assert not cell.is_empty
        assert cell.direction == "mixed"
        assert cell.magnitude_percent == 0.3

        # Asian Paints × USD/INR should be empty (no exposure record)
        cell = matrix.get_cell("drv_fx_usd_inr", "sec_asianpaint")
        assert cell.is_empty

    def test_fill_rate(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        # 3 populated out of 6 total = 50% fill rate
        assert matrix.n_populated == 3
        d = matrix.to_dict()
        assert d["metadata"]["fill_rate"] == 0.5

    def test_driver_type_inferred(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
    ) -> None:
        matrix = build_exposure_matrix(sample_exposures, sample_evidence)
        # Check that driver types are correctly inferred from IDs
        drv_types = {did: dtype for did, _, dtype in matrix.drivers}
        assert drv_types["drv_fx_usd_inr"] == "macro_driver"
        assert drv_types["rm_api"] == "raw_material"
        assert drv_types["rm_tio2"] == "raw_material"

    def test_to_dict_serialization(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        d = matrix.to_dict()
        assert "drivers" in d
        assert "companies" in d
        assert "cells" in d
        assert "metadata" in d
        assert len(d["cells"]) == 6  # 3 × 2
        assert d["metadata"]["n_drivers"] == 3
        assert d["metadata"]["n_companies"] == 2
        assert d["metadata"]["n_populated_cells"] == 3

    def test_to_markdown_table(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        md = matrix.to_markdown()
        assert "| Driver |" in md
        assert "Sun Pharma" in md or "Sun Phar" in md  # truncated labels
        assert "Asian Paints" in md or "Asian Paint" in md
        assert "USD/INR" in md
        assert "Titanium Dioxide" in md or "Titanium Di" in md
        assert "fill rate" in md

    def test_every_populated_cell_has_decomposition(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        """Every populated cell must have a non-None decomposition — no black-box scores."""
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        d = matrix.to_dict()
        for cell in d["cells"]:
            if not cell["is_empty"]:
                assert cell["decomposition"] is not None
                assert len(cell["decomposition"]) > 50  # meaningful decomposition
                # Must contain key fields
                dec = cell["decomposition"]
                assert "Direction:" in dec
                assert "Transmission:" in dec
                assert "Pricing power:" in dec
                assert "Validation:" in dec

    def test_empty_cells_have_no_decomposition(
        self,
        sample_exposures: list[dict],
        sample_evidence: list[dict],
        driver_labels: dict,
        company_labels: dict,
    ) -> None:
        matrix = build_exposure_matrix(
            sample_exposures, sample_evidence,
            driver_labels=driver_labels, company_labels=company_labels,
        )
        d = matrix.to_dict()
        for cell in d["cells"]:
            if cell["is_empty"]:
                assert cell["decomposition"] is None
