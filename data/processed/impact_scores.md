# InvestorLens Impact Scores

**Driver change:** +0.1%
**Scores computed:** 13

## Scoring formula (fully transparent)

```
Score = driver_change * magnitude_percent * direction_factor
        * pricing_power_factor * hedge_factor * validation_factor
```

| Factor | Values |
|--------|--------|
| direction | positive=+1.0, negative=-1.0, mixed=0.0, neutral=0.0 |
| pricing_power | high=0.3, medium=0.6, low=0.9, none=1.0 |
| hedge | fully_hedged=0.1, partially_hedged=0.5, unhedged=1.0 |
| validation | validated=1.0, weakly_supported=0.7, hypothesized=0.4 |

**Every score is fully decomposable. No black-box.**

## Ranked scores

| Rank | Driver | Company | Score | Direction | Magnitude | Pricing | Hedge | Validation | Metric |
|------|--------|---------|------:|-----------|-----------|---------|-------|------------|--------|
| 1 | USD/INR | ULTRACEMCO | -0.014400 | negative | 0.4% | low | unhedged | hypothesized | ebitda_margin |
| 2 | Coal | ULTRACEMCO | -0.012600 | negative | 0.4% | low | partially_hedged | weakly_supported | ebitda_margin |
| 3 | Natural Rubber | APOLLOTYRE | -0.012600 | negative | 0.3% | medium | unhedged | weakly_supported | gross_margin |
| 4 | Active Pharmaceutica | SUNPHARMA | -0.012000 | negative | 0.5% | medium | unhedged | hypothesized | gross_margin |
| 5 | Crude Oil | ASIANPAINT | -0.010500 | negative | 0.5% | high | unhedged | weakly_supported | gross_margin |
| 6 | Crude Oil | APOLLOTYRE | -0.007200 | negative | 0.3% | medium | unhedged | hypothesized | gross_margin |
| 7 | Titanium Dioxide | ASIANPAINT | -0.004620 | negative | 0.2% | high | unhedged | weakly_supported | gross_margin |
| 8 | USD/INR | APOLLOTYRE | -0.002400 | negative | 0.2% | medium | partially_hedged | hypothesized | ebitda_margin |
| 9 | USD/INR | ASIANPAINT | -0.001200 | negative | 0.2% | high | partially_hedged | hypothesized | ebitda_margin |
| 10 | CPI Combined YoY | ASIANPAINT | +0.000000 | positive | --- | high | unhedged | hypothesized | revenue |
| 11 | Key Starting Materia | SUNPHARMA | +0.000000 | negative | --- | low | unhedged | weakly_supported | gross_margin |
| 12 | CPI Combined YoY | ULTRACEMCO | +0.000000 | positive | --- | medium | unhedged | hypothesized | revenue |
| 13 | USD/INR | SUNPHARMA | +0.000000 | mixed | 0.3% | medium | partially_hedged | weakly_supported | ebitda_margin |

## Score decompositions

### USD/INR -> ULTRACEMCO

```
USD/INR → ULTRACEMCO:
  Driver change: +10.0%
  Magnitude: 0.4% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.9 (low)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.4 (hypothesized)
  Score: -0.014400
  Financial metric: ebitda_margin
  Transmission: raw_material_cost
  Magnitude estimate: 1% INR depreciation = ~0.4% cost increase (imported coal/pet coke component)
  Notes: Impact limited to imported coal/pet coke portion (~30-40% of fuel mix). Domestic coal (Coal India linkage) not affected.
  Interpretation: ebitda_margin decreases by ~1.44 percentage points
```

### Coal -> ULTRACEMCO

```
Coal → ULTRACEMCO:
  Driver change: +10.0%
  Magnitude: 0.4% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.9 (low)
  Hedge factor: 0.5 (partially_hedged)
  Validation factor: 0.7 (weakly_supported)
  Score: -0.012600
  Financial metric: ebitda_margin
  Transmission: raw_material_cost
  Magnitude estimate: Coal is ~40% of cement cost; 10% coal price increase = ~4% cost increase
  Notes: UltraTech has captive power plants (WHRS) which partially mitigate. Cement is a commodity — limited pricing power in short term.
  Interpretation: ebitda_margin decreases by ~1.26 percentage points
```

### Natural Rubber -> APOLLOTYRE

```
Natural Rubber → APOLLOTYRE:
  Driver change: +10.0%
  Magnitude: 0.3% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.6 (medium)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.7 (weakly_supported)
  Score: -0.012600
  Financial metric: gross_margin
  Transmission: raw_material_cost
  Magnitude estimate: NR is ~30% of RM cost; 10% NR price increase = ~3% cost increase. Price hikes typically follow in 2-3 months.
  Notes: Tyre companies have moderate pricing power in replacement market (65% of sales) but limited in OEM contracts (annual rate contracts).
  Interpretation: gross_margin decreases by ~1.26 percentage points
```

### Active Pharmaceutical Ingredient (API) -> SUNPHARMA

```
Active Pharmaceutical Ingredient (API) → SUNPHARMA:
  Driver change: +10.0%
  Magnitude: 0.5% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.6 (medium)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.4 (hypothesized)
  Score: -0.012000
  Financial metric: gross_margin
  Transmission: raw_material_cost
  Magnitude estimate: API is ~50% of formulation cost; 10% API price increase = ~5% cost increase
  Notes: Sun Pharma is partially backward-integrated (makes some APIs in-house), which mitigates the impact.
  Interpretation: gross_margin decreases by ~1.20 percentage points
```

### Crude Oil -> ASIANPAINT

```
Crude Oil → ASIANPAINT:
  Driver change: +10.0%
  Magnitude: 0.5% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.3 (high)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.7 (weakly_supported)
  Score: -0.010500
  Financial metric: gross_margin
  Transmission: raw_material_cost
  Magnitude estimate: ~50% of RM is crude-derived; 10% crude increase = ~5% cost increase. Pass-through typically in 2-3 months via price hikes.
  Notes: Asian Paints' high pricing power means crude oil impact is mostly temporary (margin dip for 1-2 quarters, then recovery via price hikes).
  Interpretation: gross_margin decreases by ~1.05 percentage points
```

### Crude Oil -> APOLLOTYRE

```
Crude Oil → APOLLOTYRE:
  Driver change: +10.0%
  Magnitude: 0.3% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.6 (medium)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.4 (hypothesized)
  Score: -0.007200
  Financial metric: gross_margin
  Transmission: raw_material_cost
  Magnitude estimate: Crude derivatives (SR, carbon black, process oils) are ~30% of RM cost; 10% crude increase = ~3% cost increase
  Notes: Indirect exposure through synthetic rubber and carbon black. Pass-through is slower than for NR (3-4 months vs 2-3 months).
  Interpretation: gross_margin decreases by ~0.72 percentage points
```

### Titanium Dioxide -> ASIANPAINT

```
Titanium Dioxide → ASIANPAINT:
  Driver change: +10.0%
  Magnitude: 0.22% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.3 (high)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.7 (weakly_supported)
  Score: -0.004620
  Financial metric: gross_margin
  Transmission: raw_material_cost
  Magnitude estimate: TiO2 is ~22% of RM cost; 10% TiO2 price increase = ~2.2% cost increase. Asian Paints typically passes through in 2-3 months.
  Notes: Asian Paints has HIGH pricing power due to dominant market share (~50% decorative). Price hikes are industry-leading and followed by competitors.
  Interpretation: gross_margin decreases by ~0.46 percentage points
```

### USD/INR -> APOLLOTYRE

```
USD/INR → APOLLOTYRE:
  Driver change: +10.0%
  Magnitude: 0.2% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.6 (medium)
  Hedge factor: 0.5 (partially_hedged)
  Validation factor: 0.4 (hypothesized)
  Score: -0.002400
  Financial metric: ebitda_margin
  Transmission: raw_material_cost
  Magnitude estimate: 1% INR depreciation = ~0.2% cost increase (imported NR component)
  Notes: Impact limited to imported NR (~40% of total NR consumption). Domestic NR (Kerala) not affected. Apollo partially hedges FX.
  Interpretation: ebitda_margin decreases by ~0.24 percentage points
```

### USD/INR -> ASIANPAINT

```
USD/INR → ASIANPAINT:
  Driver change: +10.0%
  Magnitude: 0.2% per 1% driver change
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.3 (high)
  Hedge factor: 0.5 (partially_hedged)
  Validation factor: 0.4 (hypothesized)
  Score: -0.001200
  Financial metric: ebitda_margin
  Transmission: raw_material_cost
  Magnitude estimate: 1% INR depreciation = ~0.2% cost increase (imported TiO2 and other chemicals)
  Notes: Impact partially offset by Asian Paints' strong pricing power. Some forward cover on FX.
  Interpretation: ebitda_margin decreases by ~0.12 percentage points
```

### CPI Combined YoY -> ASIANPAINT

```
CPI Combined YoY → ASIANPAINT:
  Driver change: +10.0%
  Magnitude: — (not quantified)
  Direction factor: 1.0 (positive)
  Pricing power factor: 0.3 (high)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.4 (hypothesized)
  Score: +0.000000
  Financial metric: revenue
  Transmission: demand
  Magnitude estimate: Higher inflation often correlates with real estate activity, driving decorative paint demand
  Notes: Indirect and lagged. Paint demand tracks housing starts and renovation activity, not CPI directly.
  Interpretation: negligible impact
```

### Key Starting Material (KSM) -> SUNPHARMA

```
Key Starting Material (KSM) → SUNPHARMA:
  Driver change: +10.0%
  Magnitude: — (not quantified)
  Direction factor: -1.0 (negative)
  Pricing power factor: 0.9 (low)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.7 (weakly_supported)
  Score: +0.000000
  Financial metric: gross_margin
  Transmission: raw_material_cost
  Magnitude estimate: KSM is ~60% of API cost; 10% KSM price increase = ~6% API cost increase
  Notes: No hedging possible for KSM prices. China supply disruptions can cause sharp price spikes.
  Interpretation: negligible impact
```

### CPI Combined YoY -> ULTRACEMCO

```
CPI Combined YoY → ULTRACEMCO:
  Driver change: +10.0%
  Magnitude: — (not quantified)
  Direction factor: 1.0 (positive)
  Pricing power factor: 0.6 (medium)
  Hedge factor: 1.0 (unhedged)
  Validation factor: 0.4 (hypothesized)
  Score: +0.000000
  Financial metric: revenue
  Transmission: demand
  Magnitude estimate: Higher inflation often correlates with increased construction/infrastructure spending
  Notes: Indirect and lagged relationship. Demand depends more on government infrastructure spending and real estate cycle than on CPI directly.
  Interpretation: negligible impact
```

### USD/INR -> SUNPHARMA

```
USD/INR → SUNPHARMA:
  Driver change: +10.0%
  Magnitude: 0.3% per 1% driver change
  Direction factor: 0.0 (mixed)
  Pricing power factor: 0.6 (medium)
  Hedge factor: 0.5 (partially_hedged)
  Validation factor: 0.7 (weakly_supported)
  Score: +0.000000
  Financial metric: ebitda_margin
  Transmission: raw_material_cost
  Magnitude estimate: 1% INR depreciation = ~0.3% margin impact (net of export benefit)
  Notes: Negative on KSM imports (~60% of API cost); positive on US export revenue (~40% of revenue). Net effect depends on import/export ratio.
  Interpretation: negligible impact
```

