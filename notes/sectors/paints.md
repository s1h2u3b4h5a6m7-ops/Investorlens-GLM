---
sector_name: Paints
slug: paints
priority: 4
edge_count: 9
last_updated: "2024-09-30T18:30:00+00:00"
data_status: researched_partial  # Phase 3 seed data; Milestone 3.2 will validate with document evidence
---

# Paints

**Priority:** 4  
**Slug:** `paints`  
**Value-chain edges:** 9 (6 uses/depends, 2 produces, 1 exposures)  

## Rationale

Raw material cost is ~55% of revenue. Highly dependent on crude oil derivatives (titanium dioxide, resins, solvents). Concentrated market (Asian Paints ~50% share).

## Key raw materials

| Raw material | Notes |
|--------------|-------|
| Titanium dioxide | _(details to be researched in Milestone 3.2)_ |
| Resins | _(details to be researched in Milestone 3.2)_ |
| Solvents | _(details to be researched in Milestone 3.2)_ |
| Pigments | _(details to be researched in Milestone 3.2)_ |
| Additives | _(details to be researched in Milestone 3.2)_ |

## Key cost drivers

| Cost driver | Notes |
|-------------|-------|
| Crude oil derivatives (TiO2, resins, solvents ~50% of RM) | _(magnitude to be quantified in Milestone 3.2)_ |
| Packaging | _(magnitude to be quantified in Milestone 3.2)_ |
| Freight | _(magnitude to be quantified in Milestone 3.2)_ |

## Key macro exposures

| Macro driver | Direction | Notes |
|---------------|-----------|-------|
| Crude oil | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| USD/INR (TiO2 imports) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Demand (construction/real estate) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |

## Products

| Product | Magnitude | % | Validation |
|---------|-----------|---|------------|
| Industrial Paints | ~30% of industry revenue | 30% | hypothesized |
| Decorative Paints | ~70% of industry revenue | 70% | weakly_supported |

## Value-chain edges

| Type | From | To | Magnitude | % | Validation | Evidence |
|------|------|-----|-----------|---|------------|----------|
| `depends_on` | `sctr_f7ce1287ef90` | `rm_146f08f308ab` | ~20-25% of RM cost; largely imported | 22% | weakly_supported | — |
| `depends_on` | `sctr_f7ce1287ef90` | `rm_b09c577bf2a4` | Indirect: TiO2, resins, solvents are crude derivatives (~50% of RM) | 50% | weakly_supported | — |
| `hurt_by` | `sctr_f7ce1287ef90` | `drv_ae85dd44228f` | Negative: TiO2 imports | — | hypothesized | — |
| `produces` | `sctr_f7ce1287ef90` | `prod_412dfaca6329` | ~70% of industry revenue | 70% | weakly_supported | — |
| `produces` | `sctr_f7ce1287ef90` | `prod_4bf07fa4792a` | ~30% of industry revenue | 30% | hypothesized | — |
| `uses` | `sctr_f7ce1287ef90` | `rm_58a0d068cc5f` | Binder; crude oil derivative | — | hypothesized | — |
| `uses` | `sctr_f7ce1287ef90` | `rm_71666b2f1317` | Minor but specialty | — | hypothesized | — |
| `uses` | `sctr_f7ce1287ef90` | `rm_976ed4c93cb4` | Crude oil derivative | — | hypothesized | — |
| `uses` | `sctr_f7ce1287ef90` | `rm_c39c073ddfae` | — | — | hypothesized | — |

## Data quality

- **Total edges:** 9
- **Validated:** 0
- **Weakly supported:** 3
- **Hypothesized:** 6
- **Note last updated:** 2024-09-30T18:30:00+00:00
- **Data status:** Phase 3 seed data (publicly known industry structure). Milestone 3.2 will validate with evidence from DRHPs, annual reports, and credit rating rationales.
