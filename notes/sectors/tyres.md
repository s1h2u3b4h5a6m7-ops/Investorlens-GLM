---
sector_name: Tyres
slug: tyres
priority: 3
edge_count: 10
last_updated: "2024-09-30T18:30:00+00:00"
data_status: researched_partial  # Phase 3 seed data; Milestone 3.2 will validate with document evidence
---

# Tyres

**Priority:** 3  
**Slug:** `tyres`  
**Value-chain edges:** 10 (6 uses/depends, 3 produces, 1 exposures)  

## Rationale

Raw material cost is ~65% of revenue. Clear drivers: natural rubber, crude oil (synthetic rubber, carbon black). Well-disclosed in annual reports.

## Key raw materials

| Raw material | Notes |
|--------------|-------|
| Natural rubber | _(details to be researched in Milestone 3.2)_ |
| Synthetic rubber | _(details to be researched in Milestone 3.2)_ |
| Carbon black | _(details to be researched in Milestone 3.2)_ |
| Steel (tyre cord) | _(details to be researched in Milestone 3.2)_ |
| Nylon | _(details to be researched in Milestone 3.2)_ |

## Key cost drivers

| Cost driver | Notes |
|-------------|-------|
| Natural rubber (30-35% of RM) | _(magnitude to be quantified in Milestone 3.2)_ |
| Crude oil (synthetic rubber, carbon black) | _(magnitude to be quantified in Milestone 3.2)_ |
| Steel | _(magnitude to be quantified in Milestone 3.2)_ |

## Key macro exposures

| Macro driver | Direction | Notes |
|---------------|-----------|-------|
| Natural rubber prices | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Crude oil | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| USD/INR (rubber imports) | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |
| Automotive demand cycle | _(TBD)_ | _(evidence to be gathered in Milestone 3.2)_ |

## Products

| Product | Magnitude | % | Validation |
|---------|-----------|---|------------|
| Commercial Vehicle Tyres | — | — | hypothesized |
| Two-Wheeler Tyres | — | — | hypothesized |
| Passenger Car Tyres | — | — | hypothesized |

## Value-chain edges

| Type | From | To | Magnitude | % | Validation | Evidence |
|------|------|-----|-----------|---|------------|----------|
| `depends_on` | `sctr_f88dd224ea63` | `rm_2f96b8c40bd3` | 30-35% of raw material cost | 32% | weakly_supported | — |
| `depends_on` | `sctr_f88dd224ea63` | `rm_b09c577bf2a4` | Indirect: synthetic rubber + carbon black are crude derivatives | — | weakly_supported | — |
| `hurt_by` | `sctr_f88dd224ea63` | `drv_ae85dd44228f` | Negative: natural rubber imports | — | hypothesized | — |
| `produces` | `sctr_f88dd224ea63` | `prod_375cbbec4aa1` | — | — | hypothesized | — |
| `produces` | `sctr_f88dd224ea63` | `prod_59ace7d6c702` | — | — | hypothesized | — |
| `produces` | `sctr_f88dd224ea63` | `prod_6334cde9176d` | — | — | hypothesized | — |
| `uses` | `sctr_f88dd224ea63` | `rm_01b3ddb490cc` | Reinforcing filler; crude oil derivative | — | hypothesized | — |
| `uses` | `sctr_f88dd224ea63` | `rm_4ecdeb046241` | Derived from crude oil | — | hypothesized | — |
| `uses` | `sctr_f88dd224ea63` | `rm_78b2af6f472d` | For bias tyres | — | hypothesized | — |
| `uses` | `sctr_f88dd224ea63` | `rm_80a22a4ad1aa` | For radial tyres | — | hypothesized | — |

## Data quality

- **Total edges:** 10
- **Validated:** 0
- **Weakly supported:** 2
- **Hypothesized:** 8
- **Note last updated:** 2024-09-30T18:30:00+00:00
- **Data status:** Phase 3 seed data (publicly known industry structure). Milestone 3.2 will validate with evidence from DRHPs, annual reports, and credit rating rationales.
