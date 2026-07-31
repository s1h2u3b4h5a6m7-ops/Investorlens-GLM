# InvestorLens Exposure Matrix

**Size:** 8 drivers × 4 companies = 32 cells
**Populated:** 13 / 32 (40.6% fill rate)

Every populated cell is fully decomposable into an evidence chain:
Driver → Exposure(direction, transmission, pricing_power, hedge, lag, magnitude, metric) → Evidence → Validation

No black-box scores.

## Matrix

| Driver | APOLLOTYRE | ASIANPAINT | SUNPHARMA | ULTRACEMCO |
|--------|----------------|----------------|----------------|----------------|
| Active Pharmaceutical Ing | — | — | negative 0.5% (hypo) | — |
| Coal | — | — | — | negative 0.4% (weak) |
| CPI Combined YoY | — | positive — (hypo) | — | positive — (hypo) |
| Crude Oil | negative 0.3% (hypo) | negative 0.5% (weak) | — | — |
| Key Starting Material (KS | — | — | negative — (weak) | — |
| Natural Rubber | negative 0.3% (weak) | — | — | — |
| Titanium Dioxide | — | negative 0.2% (weak) | — | — |
| USD/INR | negative 0.2% (hypo) | negative 0.2% (hypo) | mixed 0.3% (weak) | negative 0.4% (hypo) |

**Matrix size:** 8 drivers × 4 companies = 32 cells
**Populated:** 13 / 32 (40.6% fill rate)
**Decomposition:** every populated cell has a full evidence chain (driver → exposure → evidence → validation). No black-box scores.

## Cell decompositions

### Active Pharmaceutical Ingredient (API) → SUNPHARMA

```
Active Pharmaceutical Ingredient (API) → SUNPHARMA:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: medium
  Hedge: unhedged
  Pass-through lag: 90 days
  Magnitude: API is ~50% of formulation cost; 10% API price increase = ~5% cost increase
  Sensitivity: 1% driver change = 0.5% metric change
  Financial metric: gross_margin
  Validation: hypothesized
  Evidence: (none)
```

### Coal → ULTRACEMCO

```
Coal → ULTRACEMCO:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: low
  Hedge: partially_hedged
  Pass-through lag: 60 days
  Magnitude: Coal is ~40% of cement cost; 10% coal price increase = ~4% cost increase
  Sensitivity: 1% driver change = 0.4% metric change
  Financial metric: ebitda_margin
  Validation: weakly_supported
  Evidence: (none)
```

### CPI Combined YoY → ASIANPAINT

```
CPI Combined YoY → ASIANPAINT:
  Direction: positive
  Transmission: demand
  Pricing power: high
  Hedge: unhedged
  Pass-through lag: —
  Magnitude: Higher inflation often correlates with real estate activity, driving decorative paint demand
  Financial metric: revenue
  Validation: hypothesized
  Evidence: (none)
```

### CPI Combined YoY → ULTRACEMCO

```
CPI Combined YoY → ULTRACEMCO:
  Direction: positive
  Transmission: demand
  Pricing power: medium
  Hedge: unhedged
  Pass-through lag: —
  Magnitude: Higher inflation often correlates with increased construction/infrastructure spending
  Financial metric: revenue
  Validation: hypothesized
  Evidence: (none)
```

### Crude Oil → APOLLOTYRE

```
Crude Oil → APOLLOTYRE:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: medium
  Hedge: unhedged
  Pass-through lag: 120 days
  Magnitude: Crude derivatives (SR, carbon black, process oils) are ~30% of RM cost; 10% crude increase = ~3% cost increase
  Sensitivity: 1% driver change = 0.3% metric change
  Financial metric: gross_margin
  Validation: hypothesized
  Evidence: (none)
```

### Crude Oil → ASIANPAINT

```
Crude Oil → ASIANPAINT:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: high
  Hedge: unhedged
  Pass-through lag: 90 days
  Magnitude: ~50% of RM is crude-derived; 10% crude increase = ~5% cost increase. Pass-through typically in 2-3 months via price hikes.
  Sensitivity: 1% driver change = 0.5% metric change
  Financial metric: gross_margin
  Validation: weakly_supported
  Evidence: (none)
```

### Key Starting Material (KSM) → SUNPHARMA

```
Key Starting Material (KSM) → SUNPHARMA:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: low
  Hedge: unhedged
  Pass-through lag: 120 days
  Magnitude: KSM is ~60% of API cost; 10% KSM price increase = ~6% API cost increase
  Financial metric: gross_margin
  Validation: weakly_supported
  Evidence: (none)
```

### Natural Rubber → APOLLOTYRE

```
Natural Rubber → APOLLOTYRE:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: medium
  Hedge: unhedged
  Pass-through lag: 90 days
  Magnitude: NR is ~30% of RM cost; 10% NR price increase = ~3% cost increase. Price hikes typically follow in 2-3 months.
  Sensitivity: 1% driver change = 0.3% metric change
  Financial metric: gross_margin
  Validation: weakly_supported
  Evidence: (none)
```

### Titanium Dioxide → ASIANPAINT

```
Titanium Dioxide → ASIANPAINT:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: high
  Hedge: unhedged
  Pass-through lag: 90 days
  Magnitude: TiO2 is ~22% of RM cost; 10% TiO2 price increase = ~2.2% cost increase. Asian Paints typically passes through in 2-3 months.
  Sensitivity: 1% driver change = 0.22% metric change
  Financial metric: gross_margin
  Validation: weakly_supported
  Evidence: (none)
```

### USD/INR → APOLLOTYRE

```
USD/INR → APOLLOTYRE:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: medium
  Hedge: partially_hedged
  Pass-through lag: 90 days
  Magnitude: 1% INR depreciation = ~0.2% cost increase (imported NR component)
  Sensitivity: 1% driver change = 0.2% metric change
  Financial metric: ebitda_margin
  Validation: hypothesized
  Evidence: (none)
```

### USD/INR → ASIANPAINT

```
USD/INR → ASIANPAINT:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: high
  Hedge: partially_hedged
  Pass-through lag: 90 days
  Magnitude: 1% INR depreciation = ~0.2% cost increase (imported TiO2 and other chemicals)
  Sensitivity: 1% driver change = 0.2% metric change
  Financial metric: ebitda_margin
  Validation: hypothesized
  Evidence: (none)
```

### USD/INR → SUNPHARMA

```
USD/INR → SUNPHARMA:
  Direction: mixed
  Transmission: raw_material_cost
  Pricing power: medium
  Hedge: partially_hedged
  Pass-through lag: 180 days
  Magnitude: 1% INR depreciation = ~0.3% margin impact (net of export benefit)
  Sensitivity: 1% driver change = 0.3% metric change
  Financial metric: ebitda_margin
  Validation: weakly_supported
  Evidence: (none)
```

### USD/INR → ULTRACEMCO

```
USD/INR → ULTRACEMCO:
  Direction: negative
  Transmission: raw_material_cost
  Pricing power: low
  Hedge: unhedged
  Pass-through lag: 90 days
  Magnitude: 1% INR depreciation = ~0.4% cost increase (imported coal/pet coke component)
  Sensitivity: 1% driver change = 0.4% metric change
  Financial metric: ebitda_margin
  Validation: hypothesized
  Evidence: (none)
```

