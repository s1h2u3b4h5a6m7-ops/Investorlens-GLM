---
sector_name: Pharmaceuticals
slug: pharmaceuticals
priority: 1
edge_count: 8
last_updated: "2024-09-30T18:30:00+00:00"
data_status: researched_partial  # Phase 3 seed data; Milestone 3.2 will validate with document evidence
---

# Pharmaceuticals

**Priority:** 1  
**Slug:** `pharmaceuticals`  
**Value-chain edges:** 8 (4 uses/depends, 2 produces, 2 exposures)  

## Rationale

Clear cost drivers (APIs, KSMs), high import dependence on China, well-disclosed in DRHPs and annual reports.

## Key raw materials

| Raw material | Notes |
|--------------|-------|
| APIs | _(details to be researched in Milestone 3.2)_ |
| KSMs (Key Starting Materials) | _(details to be researched in Milestone 3.2)_ |
| Excipients | _(details to be researched in Milestone 3.2)_ |
| Packaging | _(details to be researched in Milestone 3.2)_ |

## Key cost drivers

| Cost driver | Notes |
|-------------|-------|
| API/KSM prices | _(magnitude to be quantified in Milestone 3.2)_ |
| USD/INR (import dependence) | _(magnitude to be quantified in Milestone 3.2)_ |
| Regulatory compliance (FDA/CDSCO) | _(magnitude to be quantified in Milestone 3.2)_ |

## Key macro exposures

| Macro driver | Direction | Notes |
|---------------|-----------|-------|
| USD/INR | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Crude oil (packaging) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Regulatory policy | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |

## Products

| Product | Magnitude | % | Validation |
|---------|-----------|---|------------|
| Generic Formulations | Primary product | — | hypothesized |
| APIs (Active Pharmaceutical Ingredients) | Some companies are API-focused | — | hypothesized |

## Value-chain edges

| Type | From | To | Magnitude | % | Validation | Evidence |
|------|------|-----|-----------|---|------------|----------|
| `benefits_from` | `sctr_9117dadbe07b` | `drv_ae85dd44228f` | Positive: export revenue (US generics) | — | hypothesized | — |
| `depends_on` | `sctr_9117dadbe07b` | `rm_df202fc5ac8d` | Import dependent on China (~70%) | 70% | weakly_supported | — |
| `exposed_to` | `sctr_9117dadbe07b` | `drv_ae85dd44228f` | Negative: API/KSM imports | — | weakly_supported | — |
| `produces` | `sctr_9117dadbe07b` | `prod_24bcf6878b40` | Primary product | — | hypothesized | — |
| `produces` | `sctr_9117dadbe07b` | `prod_fa7af8a0633f` | Some companies are API-focused | — | hypothesized | — |
| `uses` | `sctr_9117dadbe07b` | `rm_8669250e99a8` | Primary input | 50% | hypothesized | — |
| `uses` | `sctr_9117dadbe07b` | `rm_aa7fa91c877c` | Minor input | — | hypothesized | — |
| `uses` | `sctr_9117dadbe07b` | `rm_cd7777661edc` | Minor input | — | hypothesized | — |

## Data quality

- **Total edges:** 8
- **Validated:** 0
- **Weakly supported:** 2
- **Hypothesized:** 6
- **Note last updated:** 2024-09-30T18:30:00+00:00
- **Data status:** Phase 3 seed data (publicly known industry structure). Milestone 3.2 will validate with evidence from DRHPs, annual reports, and credit rating rationales.
