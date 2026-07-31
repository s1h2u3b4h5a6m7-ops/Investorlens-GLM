# Research Template: Cement

## Source hierarchy

1. **DRHPs** — SEBI filings for cement company IPOs
   - Key: UltraTech, Shree Cement, Dalmia Bharat, Ramco Cements
   - Extract: limestone reserves, plant locations, captive power capacity, coal linkage details

2. **Annual reports** — Company IR pages
   - Extract: power & fuel cost (P&F line item), raw material cost, freight cost, capacity utilisation, clinker/cement ratio

3. **Credit rating rationales** — CRISIL, ICRA
   - Extract: energy cost %, limestone availability, demand-supply balance, realisation per tonne

## Key research questions

### Raw materials
- [ ] Limestone: how many years of reserves do major plants have?
- [ ] Coal: what % is imported vs domestic linkage? What is the coal/pet coke mix?
- [ ] Fly ash: is it sourced from nearby thermal plants? (logistics advantage)
- [ ] Gypsum: imported vs domestic? What % of cost?

### Cost structure
- [ ] Power & fuel as % of total cost (target: ~40%)
- [ ] Raw material as % of total cost (target: ~15-20%)
- [ ] Freight as % of total cost (target: ~15-20%)
- [ ] What is the clinker-to-cement ratio? (lower = more fly ash = cheaper)

### Demand drivers
- [ ] Housing segment (% of demand)
- [ ] Infrastructure segment (% of demand)
- [ ] Real estate cycle sensitivity
- [ ] Seasonal patterns (monsoon impact)

### Competitive dynamics
- [ ] Regional market share (cement is a regional commodity — freight limits radius)
- [ ] Capacity addition pipeline (next 2-3 years)
- [ ] Pricing discipline in each region

## Evidence recording

Same format as the Pharmaceuticals template. Key edges to validate:
- `depends_on` Coal → validate the ~40% energy cost figure
- `uses` Limestone → validate the 1.5:1 ratio
- `depends_on` Pet Coke → validate the coal/pet coke substitution economics
