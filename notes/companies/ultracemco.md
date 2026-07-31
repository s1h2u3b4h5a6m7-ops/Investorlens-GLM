---
id: isin_9c54bf5ae110
isin: INE123A01024
nse_symbol: ULTRACEMCO
bse_code: 532538
company_name: UltraTech Cement Limited
sector: Cement
exchange: NSE+BSE
security_type: equity
face_value: 10.00
active: true
observations_count: 0
corporate_actions_count: 0
last_updated: "2024-09-30T18:30:00+00:00"
data_status: researched_partial  # Phase 1 data only; Phase 3+ will fill research sections
---

# UltraTech Cement Limited

**ISIN:** `INE123A01024`  
**Exchange:** NSE+BSE  
**Active:** yes  
**NSE symbol:** `ULTRACEMCO`  
**BSE code:** `532538`  
**Sector:** Cement  
**Face value:** ₹10.00  

## Latest snapshot

_(No price observations on record.)_

## Business

_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_

## Products

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Portland Cement | `produces` | Primary product | — | hypothesized |

## Customers

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Housing & Real Estate | `customer_of` | ~35% of demand | 35% | hypothesized |
| Infrastructure & Construction | `customer_of` | ~55% of demand | 55% | hypothesized |

## Suppliers

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Coal India Limited | `depends_on` | Primary coal supplier | — | hypothesized |

## Raw materials

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Coal | `depends_on` | Energy ~40% of cost | 40% | weakly_supported |
| Pet Coke | `uses` | Alternative fuel for kilns | — | hypothesized |
| Limestone | `uses` | Captive limestone quarries | — | hypothesized |

## Cost drivers

_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_

## Capital structure

_(Not yet researched — to be filled in Phase 3 from annual reports and credit rating rationales.)_

## Management / promoters

_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_

## Risks

_(Not yet researched — to be filled in Phase 3 from DRHPs and credit rating rationales.)_

## Value chain

_8 value-chain edges on record._

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Housing & Real Estate | `customer_of` | ~35% of demand | 35% | hypothesized |
| Infrastructure & Construction | `customer_of` | ~55% of demand | 55% | hypothesized |
| Coal India Limited | `depends_on` | Primary coal supplier | — | hypothesized |
| Coal | `depends_on` | Energy ~40% of cost | 40% | weakly_supported |
| drv_ae85dd44228f | `hurt_by` | Negative: coal/pet coke imports | — | hypothesized |
| Portland Cement | `produces` | Primary product | — | hypothesized |
| Pet Coke | `uses` | Alternative fuel for kilns | — | hypothesized |
| Limestone | `uses` | Captive limestone quarries | — | hypothesized |

## Evidence

_(No evidence records yet — Phase 3 will populate from source documents.)_

## Hypotheses

_(No hypotheses yet — Phase 3 will record inferred relationships.)_

## Validated relationships

_(No validated relationships yet — Phase 4 will validate via rolling betas, event studies, and shock analysis.)_

## Financials

_0 observations on record._

_(No financial observations on record.)_

## Macro exposures

| Driver | Direction | Transmission | Pricing Power | Hedge | Lag (days) | Magnitude | Metric | Validation |
|--------|-----------|-------------|---------------|-------|-----------|-----------|--------|------------|
| drv_ae85dd44228f | negative | raw_material_cost | low | unhedged | 90 | 1% INR depreciation = ~0.4% cost increase (imported coal/… | ebitda_margin | hypothesized |
| Coal | negative | raw_material_cost | low | partially_hedged | 60 | Coal is ~40% of cement cost; 10% coal price increase = ~4… | ebitda_margin | weakly_supported |
| drv_8b1a4ae12885 | positive | demand | medium | unhedged | — | Higher inflation often correlates with increased construc… | revenue | hypothesized |

## Corporate actions

_(no corporate actions on record)_

## Data quality

- **Observations count:** 0
- **Corporate actions count:** 0
- **Price observations count:** 0
- **Earliest observation:** —
- **Latest observation:** —
- **Note last updated:** 2024-09-30T18:30:00+00:00
- **Data status:** Phase 1 (data pipeline) only — research sections are placeholders.
