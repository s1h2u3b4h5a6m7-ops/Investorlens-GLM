# Data Model

This is the canonical schema reference. Every entity in InvestorLens must
conform to one of the models below. When the schema changes, update this file
*and* the JSON Schema files in `schemas/`.

---

## Entity-type prefixes (used in IDs)

Every entity ID has the form `<prefix>_<12-char-sha256-hex>`. The prefix
identifies the entity type. Adding a new prefix is a schema change.

| Prefix  | Entity              | ID key                                            |
|---------|---------------------|---------------------------------------------------|
| `co`    | Company             | `{isin}` or `{name, nse_symbol}`                  |
| `sec`   | Security            | `{isin}`                                          |
| `isin`  | ISINMaster row      | `{isin}`                                          |
| `ind`   | Industry            | `{name, sector_id}`                               |
| `prod`  | Product             | (TBD)                                             |
| `rm`    | Raw material        | (TBD)                                             |
| `sup`   | Supplier            | (TBD)                                             |
| `cust`  | Customer            | (TBD)                                             |
| `drv`   | Macro driver        | (TBD)                                             |
| `met`   | Metric              | (TBD)                                             |
| `src`   | Source              | `{slug}`                                          |
| `doc`   | Document            | `{source_id, title, url}`                         |
| `edge`  | Value-chain edge    | (TBD)                                             |
| `exp`   | Exposure record     | (TBD)                                             |
| `ca`    | Corporate action    | `{security_id, action_type, ex_date}`             |
| `obs`   | Observation         | `{subject_id, kind, period, as_of, source_id}`    |
| `evt`   | Real-world event    | (TBD)                                             |
| `mdl`   | Model               | (TBD)                                             |
| `scr`   | Score               | (TBD)                                             |
| `val`   | Validation record   | (TBD)                                             |

Note: `Sector` shares the `sec` prefix with `Security`. This is a known overlap;
in practice, sectors are usually referenced by `sector_id` from a Company, so
the collision is not problematic. If it becomes problematic, introduce a
dedicated `sctr` prefix and migrate.

---

## Core entities (Layer 0 — implemented)

### Company

A real-world legal entity listed on Indian exchanges.

| Field             | Type      | Required | Notes                                              |
|-------------------|-----------|----------|----------------------------------------------------|
| `id`              | string    | auto     | `co_<hash>`                                        |
| `name`            | string    | yes      | Legal name                                         |
| `isin`            | string    | no       | 16-char ISIN, the canonical anchor                 |
| `nse_symbol`      | string    | no       |                                                    |
| `bse_code`        | string    | no       |                                                    |
| `sector_id`       | string    | no       |                                                    |
| `industry_id`     | string    | no       |                                                    |
| `incorporated_on` | date      | no       |                                                    |
| `active`          | bool      | yes      | default true                                       |
| `provenance`      | Provenance| yes      |                                                    |

### Security

A tradable instrument. One company can have many securities.

| Field           | Type          | Required | Notes                          |
|-----------------|---------------|----------|--------------------------------|
| `id`            | string        | auto     | `sec_<hash>`                   |
| `isin`          | string        | yes      | canonical security identifier  |
| `company_id`    | string        | yes      | FK → Company                   |
| `exchange`      | enum          | yes      | NSE / BSE / NSE+BSE / OTHER    |
| `symbol`        | string        | yes      |                                |
| `security_type` | enum          | yes      | equity/debt/preference/...     |
| `face_value`    | Decimal       | no       |                                |
| `active`        | bool          | yes      |                                |
| `listed_on`     | date          | no       |                                |
| `delisted_on`   | date          | no       |                                |
| `provenance`    | Provenance    | yes      |                                |

### ISINMaster

Canonical identity row. One per ISIN. Built by merging NSE + BSE listings.

| Field            | Type        | Required | Notes                          |
|------------------|-------------|----------|--------------------------------|
| `id`             | string      | auto     | `isin_<hash>`                  |
| `isin`           | string      | yes      | 12-16 chars                    |
| `company_name`   | string      | yes      |                                |
| `nse_symbol`     | string      | no       |                                |
| `bse_code`       | string      | no       |                                |
| `security_type`  | enum        | yes      |                                |
| `exchange`       | enum        | yes      |                                |
| `sector`         | string      | no       | free-text sector name          |
| `industry`       | string      | no       |                                |
| `active`         | bool        | yes      |                                |
| `face_value`     | Decimal     | no       |                                |
| `effective_from` | date        | no       |                                |
| `effective_to`   | date        | no       |                                |
| `provenance`     | Provenance  | yes      |                                |

### Sector / Industry

| Field        | Type       | Required | Notes              |
|--------------|------------|----------|--------------------|
| `id`         | string     | auto     | `sec_<hash>`       |
| `name`       | string     | yes      |                    |
| `description`| string     | no       |                    |
| `provenance` | Provenance | yes      |                    |

Industry additionally has `sector_id` (FK → Sector).

### Source

A publisher or dataset (NSE, BSE, RBI DBIE, MOSPI, ...).

| Field              | Type       | Required | Notes                              |
|--------------------|------------|----------|------------------------------------|
| `id`               | string     | auto     | `src_<hash>`                       |
| `slug`             | string     | yes      | stable short slug, e.g. `nse`      |
| `name`             | string     | yes      |                                    |
| `kind`             | enum       | yes      | exchange/regulator/government/...  |
| `homepage`         | URL        | no       |                                    |
| `access_policy`    | string     | no       | free / API key / etc.              |
| `rate_limit_per_sec` | float    | no       |                                    |
| `provenance`       | Provenance | yes      |                                    |

### Document

A specific artifact (annual report PDF, bhavcopy zip, DRHP, ...).

| Field            | Type       | Required | Notes                              |
|------------------|------------|----------|------------------------------------|
| `id`             | string     | auto     | `doc_<hash>`                       |
| `source_id`      | string     | yes      | FK → Source                        |
| `title`          | string     | yes      |                                    |
| `url`            | URL        | no       |                                    |
| `local_path`     | string     | no       |                                    |
| `content_sha256` | string     | no       | for integrity                      |
| `published_on`   | date       | no       |                                    |
| `retrieved_at`   | datetime   | no       |                                    |
| `document_type`  | string     | yes      | annual_report / bhavcopy / drhp / ... |
| `pages`          | int        | no       |                                    |
| `provenance`     | Provenance | yes      |                                    |

### Observation

The atomic unit of fact. A single numeric/string value at a point in time.

| Field          | Type       | Required | Notes                                              |
|----------------|------------|----------|----------------------------------------------------|
| `id`           | string     | auto     | `obs_<hash>`                                       |
| `subject_id`   | string     | yes      | ID of the entity being observed                    |
| `kind`         | enum       | yes      | price_close / revenue / eps / ...                  |
| `period`       | string     | yes      | '2024-09-30', 'FY2024', 'Q1-2025'                  |
| `as_of`        | date       | yes      | the date the observation refers to                 |
| `value`        | num/str/null | yes    | null means "known unavailable"                     |
| `unit`         | string     | no       | INR / INR/share / shares / ratio                   |
| `currency`     | string     | no       | ISO 4217                                           |
| `data_status`  | enum       | yes      | observed/estimated/hypothesized/unavailable        |
| `confidence`   | enum       | yes      | high/medium/low/estimated/hypothesized             |
| `provenance`   | Provenance | yes      |                                                    |

### CorporateAction

A corporate action affecting a security. Used to adjust historical prices.

| Field              | Type       | Required | Notes                                  |
|--------------------|------------|----------|----------------------------------------|
| `id`               | string     | auto     | `ca_<hash>`                            |
| `security_id`      | string     | yes      | FK → Security                          |
| `action_type`      | enum       | yes      | split/bonus/rights/dividend/merger/...  |
| `ex_date`          | date       | yes      |                                        |
| `record_date`      | date       | no       |                                        |
| `announcement_date`| date       | no       |                                        |
| `ratio_numerator`  | float      | no       | for splits/bonus/rights                |
| `ratio_denominator`| float      | no       |                                        |
| `amount_per_share` | Decimal    | no       | for dividends                          |
| `new_symbol`       | string     | no       | for symbol changes                     |
| `new_face_value`   | Decimal    | no       | for face value changes                 |
| `notes`            | string     | no       |                                        |
| `provenance`       | Provenance | yes      |                                        |

---

## Future entities (Layer 3 — Phase 3)

To be defined when Phase 3 starts:

- `Product`, `RawMaterial`, `Supplier`, `Customer`, `MacroDriver`, `Metric`
- `ValueChainEdge` (the relationship entity)
- `Exposure` (Company × Driver × Direction × Magnitude × Period × Confidence)

## Future entities (Layer 4 — Phase 4)

- `Event` (a real-world shock: rate hike, commodity spike, policy change)
- `Model` (a Leontief matrix, a beta regression, an event study)
- `Score` (driver × company impact score, with decomposition)
- `Validation` (validation result for an edge or exposure)

---

## Provenance (embedded in every entity)

See `docs/PROVENANCE.md` for the full spec. Summary:

| Field                | Type     | Required | Notes                                              |
|----------------------|----------|----------|----------------------------------------------------|
| `source`             | string   | yes      | stable slug                                        |
| `retrieved_at`       | datetime | yes      | UTC ISO-8601                                       |
| `source_url`         | URL      | no       |                                                    |
| `document_id`        | string   | no       | FK → Document                                      |
| `reporting_period`   | string   | no       |                                                    |
| `page`               | int      | no       |                                                    |
| `section`            | string   | no       |                                                    |
| `table`              | string   | no       |                                                    |
| `extraction_method`  | enum     | no       | official_api/bulk_download/xlsx_parse/pdf_parse/...|
| `original_value`     | any      | no       | raw value before normalization                     |
| `confidence`         | enum     | yes      | high/medium/low/estimated/hypothesized             |
| `notes`              | string   | no       |                                                    |

---

## ISIN Master merge policy

The canonical ISIN master at `data/master/isin_master.jsonl` is built by
merging per-source records (NSE, BSE) by ISIN. The merge is performed by the
pure function `investorlens.builders.build_isin_master`.

### Inputs

| File                            | Source | Notes                                            |
|---------------------------------|--------|--------------------------------------------------|
| `data/master/nse_equities.jsonl` | NSE    | Output of `fetch_nse_equities_list.py`. One row per NSE equity symbol. |
| `data/master/bse_scrips.jsonl`   | BSE    | Output of `fetch_bse_equities_list.py`. One row per BSE scrip. |

### Output

`data/master/isin_master.jsonl` — one row per unique ISIN, sorted ascending.

### Per-field merge rules

For an ISIN present in **both** NSE and BSE:

| Field             | Source chosen                       | Rationale                                              |
|-------------------|-------------------------------------|--------------------------------------------------------|
| `id`              | derived from `{isin}`               | identical across sources                               |
| `isin`            | either (same by construction)       | canonical anchor                                       |
| `exchange`        | always `"NSE+BSE"`                  | indicates dual-listed                                  |
| `nse_symbol`      | NSE                                 | NSE is authoritative for its own symbols               |
| `bse_code`        | BSE                                 | BSE is authoritative for its own scrip codes           |
| `company_name`    | longer of the two                   | BSE usually has full legal name; NSE usually only has symbol |
| `sector`          | BSE if present, else NSE            | NSE's EQUITY_L.csv has no sector info                  |
| `industry`        | BSE if present, else NSE            |                                                        |
| `face_value`      | NSE if present, else BSE            | NSE CSV is usually cleaner                             |
| `effective_from`  | earlier of (NSE listing, BSE listing) | the company's earliest known listing date          |
| `security_type`   | NSE                                 | NSE is always EQUITY in this pipeline; trust it        |
| `active`          | `NSE.active OR BSE.active`          | conservative: if either says active, treat as active   |
| `provenance`      | merged                              | `source="nse+bse"`, `confidence="high"`, notes record both retrieval times |

For an ISIN present in **only one** source, the record is passed through
unchanged except that `provenance` stays as the original (source slug is `"nse"`
or `"bse"`, not `"nse+bse"`).

### Idempotency

- Input records are deduplicated by ISIN within each source (first wins; subsequent duplicates are logged as warnings).
- The merge output is sorted by ISIN — input order does not affect output.
- The merge function is pure — given the same inputs and the same `retrieved_at`, output is byte-identical.
- The `upsert_records()` call in `build_isin_master.py` detects byte-identical content and skips the rewrite, keeping git diffs empty.

---

## Bhavcopy → Observation mapping

The NSE Equity bhavcopy is a daily ZIP file containing a CSV with one row per
(symbol, series) traded that day. The bhavcopy parser
(`investorlens.parsers.bhavcopy.parse_bhavcopy_csv`) converts each row into
**6 `Observation` records**:

| Bhavcopy field(s)                  | Observation kind    | unit      | currency | data_status on no-trade |
|------------------------------------|---------------------|-----------|----------|-------------------------|
| `OpnPric` / `OPEN`                 | `price_open`        | INR/share | INR      | `unavailable`           |
| `HghPric` / `HIGH`                 | `price_high`        | INR/share | INR      | `unavailable`           |
| `LwPric` / `LOW`                   | `price_low`         | INR/share | INR      | `unavailable`           |
| `ClsPric` / `CLOSE`                | `price_close`       | INR/share | INR      | `unavailable`           |
| `TtlTradgVol` / `TOTTRDQTY`        | `volume`            | shares    | (none)   | `observed` (value=0)    |
| `TtlTrfVal` / `TOTTRDVAL`          | `turnover`          | INR       | INR      | `observed` (value=0)    |

### Subject ID resolution

Each observation's `subject_id` is the `Security` ID, which is derived
deterministically from `{isin}`. This means:

- We don't lose price data when the ISIN master is stale.
- The same ISIN appearing in multiple bhavcopy series (e.g. `EQ` and `BE`)
  deduplicates automatically — first occurrence wins per `(subject, kind, period)`.
- Once the ISIN master is rebuilt and a `Security` is formally registered, all
  existing observations immediately link up via the shared ID.

### Format support

NSE switched bhavcopy formats in late 2024. Both are supported:

- **Modern (UDiFF) format**: columns like `TradDt, TckrSymb, Sgmt, OpnPric, ClsPric, ISIN, ...` (27 columns). URL: `https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_YYYYMMDD_F_0000.csv.zip`
- **Legacy format**: columns like `SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, ISIN, ...` (13 columns). URL: `https://archives.nseindia.com/content/equities/cm<DDMMMYYYY>bhav.csv.zip`

Format is auto-detected from the header (3+ telltale columns required).
The two formats are normalized to a single `BhavcopyRow` shape internally,
so downstream code is format-agnostic.

### Illiquid / no-trade days

A row with `volume=0` and `turnover=0` represents a real fact: "this security
did not trade today." The parser preserves this fact:

- `volume` and `turnover` observations have `data_status=observed` and `value=0`.
- Price observations (`price_open`, `price_high`, `price_low`, `price_close`)
  have `data_status=unavailable` (we don't fabricate a 0 price; we explicitly
  mark it as "known missing").

This distinction matters for Phase 4 validation — we don't want a 0-priced
"observation" to contaminate rolling beta calculations.

### Cache layout

```
data/raw/nse/bhavcopy/
├── 2024-09-30.zip     # raw zip, untouched
├── 2024-10-01.zip
└── ...
```

Raw zips are excluded from git via `.gitignore` (they're re-fetchable). The
parsed observations live in `data/processed/observations.jsonl` (committed,
canonical, small).

### Idempotency

The fetcher checks for a cached zip first; if it exists, no HTTP is made.
The parser is a pure function of `(csv_text, retrieved_at, source_url)` —
same inputs produce byte-identical observations.
`upsert_records()` on `observations.jsonl` skips the rewrite if content is
unchanged, so a no-op re-run leaves the file's mtime and SHA-256 untouched.

---

## Yahoo Finance → Observation mapping

Historical prices (with split + dividend adjustment) come from Yahoo Finance's
free Chart API. We use the API directly rather than depending on the `yfinance`
library — lighter deps, more robust against Yahoo's cookie-and-crumb dance.

### Endpoint

```
GET https://query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>
    ?interval=1d&range=5d
```

Returns JSON with: meta (currency, exchange, etc.), timestamps, and
`indicators.quote[0]` (open/high/low/close/volume) plus `indicators.adjclose[0]`
(split + dividend adjusted close).

### Ticker mapping

| Source | Yahoo ticker        |
|--------|---------------------|
| NSE    | `<SYMBOL>.NS`       |
| BSE    | `<BSE_CODE>.BO`     |

The fetcher tries NSE first; if Yahoo returns no data, it falls back to BSE.

### Per-day Observation kinds emitted

| Yahoo field                  | Observation kind    | unit      | currency |
|------------------------------|---------------------|-----------|----------|
| `indicators.quote[0].open`   | `price_open`        | INR/share | INR      |
| `indicators.quote[0].high`   | `price_high`        | INR/share | INR      |
| `indicators.quote[0].low`    | `price_low`         | INR/share | INR      |
| `indicators.quote[0].close`  | `price_close`       | INR/share | INR      |
| `indicators.adjclose[0].adjclose` | `price_close_adj` | INR/share | INR  |
| `indicators.quote[0].volume` | `volume`            | shares    | (none)   |

**Important distinction**: `price_close` from Yahoo is the **raw close**
(unadjusted). `price_close_adj` is the **adjusted close** (splits + dividends).
Both are stored as separate observations so downstream code can choose:
- Phase 4 rolling beta calculations → use `price_close_adj`
- "What did the stock close at on date X?" → use `price_close`

### Subject ID resolution

Same as bhavcopy: `subject_id = make_id("sec", {"isin": isin})`. The fetcher
resolves the NSE symbol → ISIN via the ISIN master, then computes the subject
ID. ISINs not in the master are skipped (with a warning).

### Cross-source deduplication

For the same trade date, both NSE bhavcopy and Yahoo produce `price_close`
observations for the same security. These **do not** collide because the
`Observation` ID includes the source slug:

  obs_id = make_id("obs", {subject_id, kind, period, as_of, source_id})

So we end up with two `price_close` observations for the same security on the
same day — one from NSE, one from Yahoo. This is **intentional**: Phase 4
validation can compare them to detect data quality issues. If they disagree
significantly, the higher-confidence source wins (NSE official bhavcopy >
Yahoo aggregator).

### Modes

| Mode            | Flag                                | Yahoo `range` param |
|-----------------|-------------------------------------|---------------------|
| Incremental     | `--incremental` (default)           | `1mo`               |
| Backfill        | `--backfill 5y`                     | `5y`                |
| Date range      | `--start 2024-01-01 --end 2024-09-30` | picked from delta |

Valid backfill periods: `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`.

### Cache layout

```
data/raw/yahoo/
└── <YYYY-MM-DD>/              # date the fetch ran (UTC)
    └── <hash>_<symbol>        # one file per (URL, query params)
```

Re-running on the same day reads from cache — no HTTP. Different days
re-fetch.

### Idempotency

- HTTP responses cached per (URL, params, date).
- Parser is a pure function of `(response, subject_id, retrieved_at, source_url)`.
- With frozen `retrieved_at`, two consecutive runs produce byte-identical output (verified by test).
- Upsert into `observations.jsonl` skips the rewrite if content is unchanged.

### Provenance

Every Yahoo-sourced observation has:
- `source`: `"yahoo"`
- `extraction_method`: `"official_api"`
- `confidence`: `"high"` (Yahoo is generally reliable for OHLCV; less so for adjustments, but we trust their adjclose until Milestone 1.4 lets us recompute from corporate actions)
- `source_url`: full URL with query params
- `notes`: `"Yahoo Finance symbol: <SYMBOL>.NS"` (or `.BO`)

---

## Corporate Actions → CorporateAction mapping

NSE publishes a bulk CSV at `https://archives.nseindia.com/corporates/CORPACT.csv`
containing ALL corporate actions for ALL listed companies (~5 MB).

### CSV columns

```
Symbol, Series, Industry, Face Value(Rs.), Symbol 2, Company Name,
Subject, Ex-Date, Record-Date, Broadcast-Date, BC Start Date, BC End Date,
ND Start Date, ND End Date, Actual Payment Date, Dividend Type,
Dividend (%), Dividend Amount / Share, Purpose, Details
```

### Classification

The `Subject` / `Purpose` / `Details` fields are free-text. The parser
classifies each row into a `CorporateActionType` by regex-matching against
these telltale patterns (checked in order; first match wins):

| Order | Action type        | Pattern (case-insensitive)                                       |
|-------|--------------------|------------------------------------------------------------------|
| 1     | `BONUS`            | `\bbonus\b`                                                      |
| 2     | `SPLIT`            | `\b(stock\s*split\|sub-?division\|split)\b`                      |
| 3     | `RIGHTS`           | `\brights?\b`                                                    |
| 4     | `MERGER`           | `\b(merger\|amalgamat\w*\|scheme\s+of\s+(arrangement\|amalgamation))` |
| 5     | `DEMERGER`         | `\b(demerger\|spin-?off)`                                        |
| 6     | `SYMBOL_CHANGE`    | `\b(?:symbol\s+change\|change\s+of\s+symbol)\b`                  |
| 7     | `DIVIDEND`         | `\bdividend\b`                                                   |
| 8     | `FACE_VALUE_CHANGE`| `\bface\s+value\b`                                               |
| -     | `OTHER`            | (no match)                                                       |

**Order rationale**:
- Bonus/Split/Rights/Merger/Demerger/SymbolChange before Dividend, because
  some rows mention both (e.g. "Bonus + Dividend") and we want the structural
  action to win.
- Dividend before Face Value Change, because dividend rows often mention
  "face value of Rs.2" as context (the dividend basis), not as a face value change.

### Numeric extraction

| Field             | Source                                                                  |
|-------------------|-------------------------------------------------------------------------|
| `ratio_numerator` | Regex `(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)` on Subject/Purpose/Details |
| `ratio_denominator` | (same as above)                                                       |
| `amount_per_share` | Prefer explicit "Dividend Amount / Share" column; fall back to regex `(?:rs\.?\|inr\|₹)\s*(\d+(?:\.\d+)?)` |
| `new_face_value`  | Regex `to\s*r[es]\.?\s*(\d+(?:\.\d+)?)` (handles both "Rs.10" and "Re.1") |
| `record_date`     | `Record-Date` column                                                    |
| `announcement_date` | `Broadcast-Date` column                                                |

For SPLIT specifically, if no explicit `X:Y` ratio is found, the parser tries
to infer it from the face value change in the Subject (e.g. "Stock Split from
Rs.10/- to Rs.1/-" → ratio = 10/1 = 10).

### Symbol resolution

The parser resolves NSE `Symbol` → ISIN via the ISIN master. Rows whose
symbol isn't in the master are skipped (with an info-level log message).
This is intentional — we don't store corp actions for securities we don't track.

### ID derivation

Each CorporateAction's ID is `ca_<hash>` where the hash is over:
```python
{"security_id": sec_<hash>, "action_type": "split", "ex_date": "2024-09-30"}
```

So if NSE republishes the same corp action with the same ex-date, it
upserts cleanly. If the ex-date changes (rare but possible for rescheduled
actions), a new ID is created — the old record stays (we don't silently delete).

---

## Adjusted price math

The `investorlens.builders.adjusted_prices.build_adjusted_prices` function
takes raw `price_close` observations + `CorporateAction` records and produces
`price_close_adj` observations computed from official NSE corp actions.

This is the **transparent, decomposable** counterpart to Yahoo's adjclose:
- Yahoo: black-box adjustment (we trust their algorithm)
- InvestorLens: explicit adjustment factors derived from official corp actions

Phase 4 can cross-validate the two: if they diverge significantly, either
Yahoo has a bug or our corp-action parser missed an event.

### Setup

For a security, let:
- `P[t]` = raw close price on day `t` (from bhavcopy or Yahoo raw close)
- `CA` = chronological list of corporate actions with ex-dates `d_1 < d_2 < ... < d_n`

### Per-action adjustment factors

| Action type | Factor                                                                         |
|-------------|--------------------------------------------------------------------------------|
| `SPLIT` (n:d, e.g. 5:1) | `split_factor = n / d` (n new shares for every d old)               |
| `BONUS` (n:d, e.g. 1:1) | `bonus_factor = (d + n) / d` (d held → d+n total)                   |
| `DIVIDEND` (amount D)   | No multiplicative factor. Handled separately as subtractive adj.    |
| `MERGER` / `DEMERGER` / `RIGHTS` / `SYMBOL_CHANGE` / `FACE_VALUE_CHANGE` / `OTHER` | Not auto-adjusted. Skipped with warning. |

### Cumulative split+bonus factor (multiplicative)

For day `t`:
```
f[t] = product of (split_factor_i * bonus_factor_i) for all i with d_i > t
```

This is the cumulative dilution factor applied to prices BEFORE day `t`.
Walking forward through time, the factor DECREASES as we cross each ex-date
(we divide by that action's factor).

### Split+bonus adjusted close

```
adj_close_sb[t] = P[t] / f[t]
```

### Dividend adjustment (subtractive, CRSP-style total-return)

Processing dividends in **reverse chronological order** (latest first), for
each dividend `D_i` with ex-date `d_i`:

```
adj_close[t] = adj_close[t] - D_i * (adj_close[d_i] / P[d_i])   for all t < d_i
```

Where `adj_close[d_i]` is the close on the ex-date AFTER all later adjustments
have been applied. This is the standard CRSP-style total-return adjustment.

**Why reverse order?** Because later dividends' adjustments depend on the
already-adjusted price level, not the raw price. Processing in reverse
ensures each dividend's price adjustment uses the correct adjusted reference.

### Final adjusted close

```
adj_close[t] = (P[t] / f[t]) - sum_of_dividend_adjustments
```

### Decomposition (transparency)

Every adjusted-price observation's `provenance.notes` contains a JSON
`AdjustmentDecomposition`:

```json
{
  "raw_close": 100.0,
  "cumulative_split_bonus_factor": 2.0,
  "dividend_adjustments": [
    {"ex_date": "2024-01-15", "dividend_amount": 5.0, "price_adjustment": 2.5}
  ],
  "final_adjusted_close": 47.5
}
```

This makes every adjusted price **fully decomposable**. A user asking
"why did Company X get adj_close 47.5 on date Y?" can be answered:
"raw close 100, split factor 2.0 (5:1 split on date Z), dividend adjustment
2.5 (Rs.5 dividend on date W with reference price 100)."

### Distinct provenance from Yahoo adjclose

| Source         | `provenance.source` | `provenance.extraction_method` |
|----------------|---------------------|--------------------------------|
| Yahoo adjclose | `"yahoo"`           | `"official_api"`               |
| InvestorLens   | `"investorlens"`    | `"derived"`                    |

Both produce `kind=PRICE_CLOSE_ADJ` observations. Because the Observation
ID includes the source slug, the two coexist in `observations.jsonl`
without collision. Phase 4 validation can cross-check them.

### Supported / unsupported action types

The current builder supports:
- `SPLIT` (multiplicative factor)
- `BONUS` (multiplicative factor)
- `DIVIDEND` (subtractive adjustment)

It does NOT yet auto-adjust:
- `MERGER` / `DEMERGER` (require case-by-case handling; shareholders receive
  shares of the new entity at a specific ratio — complex to generalize)
- `RIGHTS` (similar to bonus but with a subscription price — needs more work)
- `SYMBOL_CHANGE` / `FACE_VALUE_CHANGE` / `OTHER` (no price impact by themselves)

When the builder encounters these, it logs an info-level message and treats
them as no-ops. Phase 3+ will add explicit handlers once we have sufficient
data to test against.

### Idempotency

- The builder is a pure function of `(price_observations, corp_actions, retrieved_at)`.
- With frozen `retrieved_at`, two consecutive runs produce byte-identical output.
- Upsert into `observations.jsonl` skips the rewrite if content is unchanged.
- The decomposition JSON in `provenance.notes` is also deterministic (sorted keys).

---

## Macro indicators → Observation mapping

Macro data (RBI rates, FX, CPI) is stored as `Observation` records, just like
equity price data. The `subject_id` is a `drv_*` ID (macro driver), which will
become the `MacroDriver.id` in Phase 3.

### Schema change (Milestone 1.5)

Added 3 new `ObservationKind` values (backward-compatible):

| Kind           | Use                                                                |
|----------------|--------------------------------------------------------------------|
| `policy_rate`  | RBI Repo / SDF / MSF / Bank Rate / CRR / SLR / Reverse Repo (%)    |
| `cpi_yoy`      | CPI year-over-year % (combined, rural, urban)                      |
| `fx_rate`      | Reference exchange rate (USD/INR, EUR/INR, GBP/INR, JPY/INR)       |

### Macro driver ID derivation

Each macro indicator gets a stable `drv_<hash>` ID derived from its slug:

| Slug                         | Indicator                                   |
|------------------------------|---------------------------------------------|
| `policy_repo_rate`           | RBI Policy Repo Rate                        |
| `sdf_rate`                   | Standing Deposit Facility Rate              |
| `msf_rate`                   | Marginal Standing Facility Rate             |
| `bank_rate`                  | Bank Rate                                   |
| `crr`                        | Cash Reserve Ratio                          |
| `slr`                        | Statutory Liquidity Ratio                   |
| `fixed_reverse_repo_rate`    | Fixed Reverse Repo Rate                     |
| `fx_usd_inr`                 | USD/INR reference rate                      |
| `fx_eur_inr`                 | EUR/INR reference rate                      |
| `fx_gbp_inr`                 | GBP/INR reference rate                      |
| `fx_jpy_inr`                 | JPY/INR reference rate (per 100 JPY)        |
| `cpi_combined_yoy`           | CPI Combined YoY % (headline inflation)     |
| `cpi_rural_yoy`              | CPI Rural YoY %                             |
| `cpi_urban_yoy`              | CPI Urban YoY %                             |
| `cpi_combined_index`         | CPI Combined index level                    |
| `cpi_rural_index`            | CPI Rural index level                       |
| `cpi_urban_index`            | CPI Urban index level                       |

Phase 3 will formalize these as `MacroDriver` records (a new Pydantic model)
with name, description, source, frequency, unit. For now, the slug-based IDs
suffice — observations can reference them and Phase 3 can backfill the metadata.

### RBI Policy Rates

**Source**: https://rbi.org.in/Scripts/BS_ViewPolicyRates.aspx (HTML table)
**Fetcher**: `scripts/fetchers/fetch_rbi_rates.py`
**Parser**: `investorlens.parsers.rbi.parse_policy_rates_html`

The page renders a simple HTML `<table>` with rows like `Policy Repo Rate | 6.50`.
The parser:
1. Extracts all `<table>` elements using a stdlib `html.parser` (no BS4 dependency).
2. For each row, matches the first cell against known policy-rate slugs (case-insensitive, prefix-aware).
3. Parses the second cell as a percentage (handles `6.50` and `6.50%`).
4. Emits one Observation per recognized rate.

Each observation has:
- `kind` = `POLICY_RATE`
- `subject_id` = `drv_<slug>` (e.g. `drv_<hash of "policy_repo_rate">`)
- `unit` = `%`
- `currency` = None (rates are unitless)
- `as_of` = the date the rates apply to (defaults to today; pass `as_of=date(2024,10,9)` for historical snapshots)

### RBI FX Reference Rates

**Source**: https://rbi.org.in/Scripts/ReferenceRate.aspx (HTML table)
**Fetcher**: `scripts/fetchers/fetch_rbi_fx.py`
**Parser**: `investorlens.parsers.rbi.parse_fx_reference_html`

The page renders a table with columns `Date | 1 USD | 1 EUR | 1 GBP | 100 JPY`
and one row per business day. The parser:
1. Extracts all tables.
2. For each table, identifies the date column (header contains "date" or "as on") and currency columns (header matches "1 USD", "1 EUR", "1 GBP", or "100 JPY").
3. For each (date, currency) cell, parses the value as a Decimal.
4. Emits one Observation per (date, currency).

Each observation has:
- `kind` = `FX_RATE`
- `subject_id` = `drv_fx_<ccy>_inr`
- `unit` = `INR/<CCY>` (e.g. `INR/USD`, `INR/JPY`)
- `currency` = `INR`
- `as_of` = the trade date (parsed from DD-MMM-YYYY format)

### MOSPI CPI

**Source**: https://mospi.gov.in/web/mospi/cpi-publications (Excel/CSV)
**Fetcher**: `scripts/fetchers/fetch_mospi_cpi.py`
**Parser**: `investorlens.parsers.mospi.parse_cpi_csv`

The MOSPI release is an Excel file with columns like `Year`, `Month`,
`Combined Rural+Urban Index`, `Combined YoY %`, etc. The CSV parser:
1. Reads the CSV with `csv.DictReader`.
2. Normalizes column names (tolerant of variations like "Combined YoY %" vs "Combined YoY(%)").
3. Parses year (int) and month (name or number).
4. For each (year, month, indicator), emits one Observation.

Each observation has:
- `kind` = `CPI_YOY` for YoY % fields, `OTHER` for index level fields
- `subject_id` = `drv_cpi_<scope>_<type>` (e.g. `drv_cpi_combined_yoy`)
- `unit` = `%` for YoY, `index` for index level
- `currency` = None
- `period` = `YYYY-MM` format (e.g. `2024-09`)
- `as_of` = first day of the month (e.g. `2024-09-01`)

### Cross-source data layout

All macro observations live alongside equity observations in
`data/processed/observations.jsonl`. Because the Observation ID includes the
source slug, they never collide with equity observations even when the date
overlaps. Phase 3 will be able to query "give me all observations for driver X"
and get a clean time series regardless of source.

### Idempotency

Same as all other fetchers:
- HTTP responses cached per (URL, params, date) under `data/raw/<source>/<subdir>/<date>.<ext>`.
- Parsers are pure functions of `(text, retrieved_at, source_url, as_of?)`.
- With frozen `retrieved_at`, byte-identical output across runs (verified by test).
- Upsert skips the rewrite if content is unchanged.

### Deferred datasets (Phase 1.6+)

These were on the original roadmap but are deferred:

- **RBI DBIE**: The Database on Indian Economy (https://dbie.rbi.org.in) —
  provides M3 money supply, FX reserves, banking statistics. Requires
  authentication; SSL cert broken from this sandbox. Will revisit in Phase 1.6
  when we test against a real CI environment.
- **MOSPI IIP** (Index of Industrial Production): monthly, similar format to
  CPI. Straightforward extension of the existing MOSPI parser pattern.
- **MOSPI SUT** (Supply and Use Tables): 5-yearly matrix; naturally belongs to
  Phase 4 (Leontief model). Will be fetched there.
- **data.gov.in**: requires free API key registration. Document the key
  requirement and add a fetcher once we have a real key.

---

## Company Knowledge Notes (Phase 2)

Phase 2 introduces per-company Markdown notes generated from the structured
data collected in Phase 1. Each note lives at `notes/companies/<slug>.md`
where `slug` is the NSE symbol lowercased (or the company name, or the ISIN
as a final fallback).

### Note structure

Every note has:

1. **YAML frontmatter** (machine-readable, Dataview-compatible)
2. **Title** + header block (company name, ISIN, exchange, sector, etc.)
3. **Latest snapshot** (last raw close, last adjusted close)
4. **Research sections** (Business, Products, Customers, Suppliers, Raw
   materials, Cost drivers, Capital structure, Management, Risks, Value
   chain, Evidence, Hypotheses, Validated relationships) — these are
   **placeholder sections** in Phase 2, filled in Phase 3.
5. **Financials** (populated from observations: price/volume/turnover tables)
6. **Macro exposures** (lists which macro drivers were tracked during the
   company's observation window)
7. **Corporate actions** (populated from `corporate_actions.jsonl`)
8. **Data quality** (counts, date ranges, last-updated timestamp)

### YAML frontmatter fields

| Field                       | Type    | Source                                     |
|-----------------------------|---------|--------------------------------------------|
| `id`                        | string  | ISIN master record ID (`isin_<hash>`)      |
| `isin`                      | string  | ISIN master                                |
| `nse_symbol`                | string  | ISIN master (optional)                     |
| `bse_code`                  | string  | ISIN master (optional)                     |
| `company_name`              | string  | ISIN master                                |
| `sector`                    | string  | ISIN master (optional)                     |
| `industry`                  | string  | ISIN master (optional)                     |
| `exchange`                  | string  | ISIN master (NSE / BSE / NSE+BSE)          |
| `security_type`             | string  | ISIN master (equity / debt / ...)          |
| `face_value`                | string  | ISIN master (Decimal as string)            |
| `active`                    | bool    | ISIN master                                |
| `listing_date`              | date    | ISIN master `effective_from`               |
| `observations_count`        | int     | Count of this company's observations       |
| `corporate_actions_count`   | int     | Count of this company's corp actions       |
| `last_updated`              | datetime| Build timestamp (UTC ISO-8601)             |
| `data_status`               | string  | `researched_partial` (Phase 1 data only)   |

All values are simple scalars (strings, numbers, dates, booleans) so they
work with Obsidian Dataview queries out of the box. Example Dataview query:

```dataview
TABLE isin, sector, observations_count, corporate_actions_count
FROM "notes/companies"
WHERE active
SORT observations_count DESC
```

### Slug derivation

The slug is derived in this order:
1. NSE symbol, lowercased (e.g. `RELIANCE` → `reliance`)
2. Company name, lowercased, with common suffixes stripped (`Ltd`, `Limited`)
   and special chars replaced (e.g. `Tata Consultancy Services Ltd` → `tata_consultancy_services`)
3. ISIN, lowercased (final fallback)

### Populated vs placeholder sections

| Section                | Phase 2 status | Source                                   |
|------------------------|----------------|------------------------------------------|
| Latest snapshot        | ✅ Populated    | Latest `price_close` + `price_close_adj` |
| Financials             | ✅ Populated    | All price/volume/turnover observations   |
| Macro exposures        | ✅ Partial      | Lists tracked drivers; specific exposures are Phase 3 |
| Corporate actions      | ✅ Populated    | `corporate_actions.jsonl` for this security |
| Data quality           | ✅ Populated    | Counts + date ranges                     |
| Business               | Placeholder    | Phase 3 (DRHPs + annual reports)         |
| Products               | Placeholder    | Phase 3                                  |
| Customers              | Placeholder    | Phase 3                                  |
| Suppliers              | Placeholder    | Phase 3                                  |
| Raw materials          | Placeholder    | Phase 3                                  |
| Cost drivers           | Placeholder    | Phase 3                                  |
| Capital structure      | Placeholder    | Phase 3                                  |
| Management / promoters | Placeholder    | Phase 3                                  |
| Risks                  | Placeholder    | Phase 3                                  |
| Value chain            | Placeholder    | Phase 3                                  |
| Evidence               | Placeholder    | Phase 3                                  |
| Hypotheses             | Placeholder    | Phase 3                                  |
| Validated relationships| Placeholder    | Phase 4 (rolling betas, event studies)   |

The placeholders are **explicit** — they say "Not yet researched — to be
filled in Phase 3" — so users don't mistake an empty section for "no data
exists". This makes the gap visible and actionable.

### Builder architecture

- **Pure function**: `investorlens.builders.notes.build_company_note(company, observations, corp_actions, last_updated)` → Markdown string. No I/O, no time dependency (with fixed `last_updated`).
- **Orchestrator script**: `scripts/builders/build_company_notes.py` — loads ISIN master + observations + corp actions, groups them by subject/security ID, calls the builder per company, writes atomically to `notes/companies/<slug>.md`.
- **Slug helper**: `slugify_company(name, nse_symbol, isin)` — deterministic slug derivation.

### Idempotency

- The builder is a pure function of `(company, observations, corp_actions, last_updated)`.
- With frozen `last_updated`, two consecutive runs produce byte-identical output (verified by test + SHA-256 of `reliance.md`).
- Atomic writes (tmp + rename) ensure no partial files on disk.
- Companies with no observations AND no corp actions are skipped (their notes would be all placeholders).

### File layout

```
notes/
└── companies/
    ├── reliance.md      # RELIANCE — 41 obs, 2 corp actions
    ├── tcs.md           # TCS — 7 obs, 2 corp actions
    ├── infy.md          # INFY — 7 obs, 2 corp actions
    ├── sunpharma.md     # SUNPHARMA — 7 obs, 1 corp action
    └── hdfcbank.md      # HDFCBANK — 7 obs, 1 corp action
```

Notes are committed to the repo (small, canonical, useful for browsing).
Phase 2.2 will add sector canvases and a top-level index.

---

## File layout

```
data/
├── raw/                     # untouched downloads (zip, pdf, csv)
│   ├── nse/<date>/<hash>_<slug>     # CachedSession cache
│   ├── bse/<date>/<hash>_<slug>
│   ├── nse/bhavcopy/                # (future — Milestone 1.2)
│   ├── bse/bhavcopy/
│   ├── rbi/
│   ├── mospi/
│   ├── company_ar/
│   └── company_drhp/
├── master/                  # canonical master records
│   ├── isin_master.jsonl    # ← canonical ISIN master (merged)
│   ├── nse_equities.jsonl   # ← per-source input for ISIN master
│   ├── bse_scrips.jsonl     # ← per-source input for ISIN master
│   ├── companies.jsonl      # (future)
│   ├── sectors.jsonl
│   └── sources.jsonl
├── processed/               # normalized records, partitioned by kind
│   ├── observations.jsonl   # all observations, idempotent upserts
│   ├── corporate_actions.jsonl
│   └── prices/<symbol>/<date>.json
└── provenance/              # run logs (future)
    └── runs/<date>.json
```

---

## Migration policy

Before changing the schema:

1. `grep -r` for every field you intend to change. Note all dependents.
2. If existing data needs rewriting, write a migration script in `scripts/migrations/`.
3. Update `docs/DATA_MODEL.md` (this file).
4. Update the relevant JSON Schema in `schemas/`.
5. Update the Pydantic model in `src/investorlens/models/`.
6. Update tests in `tests/`.
7. Run the full test suite.
8. Run the migration on existing data.
9. Commit all of the above in a single commit with message
   `schema: <one-line description>`.
