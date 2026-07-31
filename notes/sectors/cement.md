---
sector_name: Cement
slug: cement
priority: 2
edge_count: 8
last_updated: "2024-09-30T18:30:00+00:00"
data_status: researched_partial  # Phase 3 seed data; Milestone 3.2 will validate with document evidence
---

# Cement

**Priority:** 2  
**Slug:** `cement`  
**Value-chain edges:** 8 (5 uses/depends, 2 produces, 1 exposures)  

## Rationale

Commodity product with clear input structure (limestone, coal/power, gypsum). High energy cost (~40% of cost). Well-covered by rating agencies.

## Key raw materials

| Raw material | Notes |
|--------------|-------|
| Limestone | _(details to be researched in Milestone 3.2)_ |
| Coal | _(details to be researched in Milestone 3.2)_ |
| Fly ash | _(details to be researched in Milestone 3.2)_ |
| Gypsum | _(details to be researched in Milestone 3.2)_ |
| Clinker | _(details to be researched in Milestone 3.2)_ |

## Key cost drivers

| Cost driver | Notes |
|-------------|-------|
| Coal/power (energy ~40%) | _(magnitude to be quantified in Milestone 3.2)_ |
| Limestone (raw material) | _(magnitude to be quantified in Milestone 3.2)_ |
| Freight/logistics | _(magnitude to be quantified in Milestone 3.2)_ |
| Pet coke | _(magnitude to be quantified in Milestone 3.2)_ |

## Key macro exposures

| Macro driver | Direction | Notes |
|---------------|-----------|-------|
| Coal prices | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| USD/INR (coal/pet coke imports) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Diesel (freight) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Demand (construction cycle) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |

## Products

| Product | Magnitude | % | Validation |
|---------|-----------|---|------------|
| Portland Cement | Primary product | — | hypothesized |
| Ready-Mix Concrete | Value-added product | — | hypothesized |

## Value-chain edges

| Type | From | To | Magnitude | % | Validation | Evidence |
|------|------|-----|-----------|---|------------|----------|
| `depends_on` | `sctr_239d06c7d3e0` | `rm_bc9bdfec595f` | Energy ~40% of cost | 40% | weakly_supported | — |
| `hurt_by` | `sctr_239d06c7d3e0` | `drv_ae85dd44228f` | Negative: coal/pet coke imports | — | hypothesized | — |
| `produces` | `sctr_239d06c7d3e0` | `prod_b5f0fce095c6` | Value-added product | — | hypothesized | — |
| `produces` | `sctr_239d06c7d3e0` | `prod_bb58dfdc102e` | Primary product | — | hypothesized | — |
| `uses` | `sctr_239d06c7d3e0` | `rm_4479b44520fe` | 3-5% of input | — | hypothesized | — |
| `uses` | `sctr_239d06c7d3e0` | `rm_4bef8459616e` | Primary raw material (~1.5t per t cement) | — | weakly_supported | — |
| `uses` | `sctr_239d06c7d3e0` | `rm_55fdddaa4c42` | Supplementary cementitious material | — | hypothesized | — |
| `uses` | `sctr_239d06c7d3e0` | `rm_ec0e2b1936e8` | Alternative fuel; cheaper than coal | — | hypothesized | — |

## Data quality

- **Total edges:** 8
- **Validated:** 0
- **Weakly supported:** 2
- **Hypothesized:** 6
- **Note last updated:** 2024-09-30T18:30:00+00:00
- **Data status:** Phase 3 seed data (publicly known industry structure). Milestone 3.2 will validate with evidence from DRHPs, annual reports, and credit rating rationales.
