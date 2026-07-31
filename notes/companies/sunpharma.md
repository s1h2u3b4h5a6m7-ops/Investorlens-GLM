---
id: isin_4b938dc3a59d
isin: INE044A01026
nse_symbol: SUNPHARMA
bse_code: 524715
company_name: Sun Pharmaceutical Industries Limited
sector: Pharmaceuticals
exchange: NSE+BSE
security_type: equity
face_value: 1.00
active: true
listing_date: 1994-10-10
observations_count: 7
corporate_actions_count: 1
last_updated: "2024-09-30T18:30:00+00:00"
data_status: researched_partial  # Phase 1 data only; Phase 3+ will fill research sections
---

# Sun Pharmaceutical Industries Limited

**ISIN:** `INE044A01026`  
**Exchange:** NSE+BSE  
**Active:** yes  
**NSE symbol:** `SUNPHARMA`  
**BSE code:** `524715`  
**Sector:** Pharmaceuticals  
**Face value:** ₹1.00  
**Listing date:** 1994-10-10  

## Latest snapshot

- **Last close (raw):** ₹1842.35 on 2024-09-30 (source: nse)
- **Last close (adjusted):** ₹1842.35 on 2024-09-30 (source: investorlens)

## Business

_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_

## Products

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Generic Formulations | `produces` | Primary revenue source | — | hypothesized |
| APIs (Active Pharmaceutical Ingredients) | `produces` | API business for own use + external sale | — | hypothesized |

## Customers

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| US Generic Drug Distributors | `customer_of` | ~40% of revenue (US market) | 40% | weakly_supported |
| Indian Pharmacy Retail Chain | `customer_of` | ~25% of revenue (domestic) | 25% | hypothesized |

## Suppliers

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| China-based KSM Suppliers | `depends_on` | Key KSM supplier | — | hypothesized |

## Raw materials

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| Key Starting Material (KSM) | `depends_on` | Imported from China | 60% | hypothesized |
| Active Pharmaceutical Ingredient (API) | `uses` | Primary input for formulations | 50% | hypothesized |

## Cost drivers

_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_

## Capital structure

_(Not yet researched — to be filled in Phase 3 from annual reports and credit rating rationales.)_

## Management / promoters

_(Not yet researched — to be filled in Phase 3 from DRHPs and annual reports.)_

## Risks

_(Not yet researched — to be filled in Phase 3 from DRHPs and credit rating rationales.)_

## Value chain

_9 value-chain edges on record._

| Target | Type | Magnitude | % | Validation |
|--------|------|-----------|---|------------|
| drv_ae85dd44228f | `benefits_from` | Positive: US export revenue | — | hypothesized |
| US Generic Drug Distributors | `customer_of` | ~40% of revenue (US market) | 40% | weakly_supported |
| Indian Pharmacy Retail Chain | `customer_of` | ~25% of revenue (domestic) | 25% | hypothesized |
| China-based KSM Suppliers | `depends_on` | Key KSM supplier | — | hypothesized |
| Key Starting Material (KSM) | `depends_on` | Imported from China | 60% | hypothesized |
| drv_ae85dd44228f | `hurt_by` | Negative: KSM imports | — | hypothesized |
| Generic Formulations | `produces` | Primary revenue source | — | hypothesized |
| APIs (Active Pharmaceutical Ingredients) | `produces` | API business for own use + external sale | — | hypothesized |
| Active Pharmaceutical Ingredient (API) | `uses` | Primary input for formulations | 50% | hypothesized |

## Evidence

_(No evidence records yet — Phase 3 will populate from source documents.)_

## Hypotheses

_(No hypotheses yet — Phase 3 will record inferred relationships.)_

## Validated relationships

_(No validated relationships yet — Phase 4 will validate via rolling betas, event studies, and shock analysis.)_

## Financials

_7 observations on record._

### Price observations

| Date | Kind | Value | Unit | Currency | Source |
|------|------|------:|------|----------|--------|
| 2024-09-30 | `price_open` | 1840 | INR/share | INR | nse |
| 2024-09-30 | `price_low` | 1835 | INR/share | INR | nse |
| 2024-09-30 | `price_close_adj` | 1842.35 | INR/share | INR | investorlens |
| 2024-09-30 | `price_high` | 1845 | INR/share | INR | nse |
| 2024-09-30 | `price_close` | 1842.35 | INR/share | INR | nse |

### Volume observations

| Date | Kind | Value | Unit | Currency | Source |
|------|------|------:|------|----------|--------|
| 2024-09-30 | `volume` | 1200000 | shares | — | nse |

### Turnover observations

| Date | Kind | Value | Unit | Currency | Source |
|------|------|------:|------|----------|--------|
| 2024-09-30 | `turnover` | 2210400000 | INR | INR | nse |

## Macro exposures

| Driver | Direction | Transmission | Pricing Power | Hedge | Lag (days) | Magnitude | Metric | Validation |
|--------|-----------|-------------|---------------|-------|-----------|-----------|--------|------------|
| drv_ae85dd44228f | mixed | raw_material_cost | medium | partially_hedged | 180 | 1% INR depreciation = ~0.3% margin impact (net of export … | ebitda_margin | weakly_supported |
| Active Pharmaceutical Ingredient (API) | negative | raw_material_cost | medium | unhedged | 90 | API is ~50% of formulation cost; 10% API price increase =… | gross_margin | hypothesized |
| Key Starting Material (KSM) | negative | raw_material_cost | low | unhedged | 120 | KSM is ~60% of API cost; 10% KSM price increase = ~6% API… | gross_margin | weakly_supported |

## Corporate actions

| Ex-Date | Type | Ratio | Amount/Share | New FV | Notes | Source |
|---------|------|-------|-------------|--------|-------|--------|
| 2023-12-20 | `split` | 10 : 1 | — | 1 | Stock Split from Rs.10/- to Rs.1/- | Sub-division of equity shares of face value… | nse |

## Data quality

- **Observations count:** 7
- **Corporate actions count:** 1
- **Price observations count:** 5
- **Earliest observation:** 2024-09-30
- **Latest observation:** 2024-09-30
- **Note last updated:** 2024-09-30T18:30:00+00:00
- **Data status:** Phase 1 (data pipeline) only — research sections are placeholders.
