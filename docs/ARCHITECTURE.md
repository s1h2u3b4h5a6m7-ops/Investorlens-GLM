# Architecture

This document describes the *current* architecture of InvestorLens and the
*rules* that any future change must respect. If the code ever disagrees with
this document, **the code wins** — fix the document.

---

## Layered design

The system is intentionally layered. Each layer depends only on the layers
below it, never above. This keeps changes local and the system testable.

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 5 — UI (React, future)                                   │
│  Cytoscape graph, search, driver→company explorer               │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4 — Algorithms (Phase 4, future)                         │
│  Leontief, exposure matrix, driver→company scoring, validation  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3 — Knowledge Graph (Phase 3)                            │
│  Companies, products, suppliers, customers, drivers, edges      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2 — Structured Data (Phase 2)                            │
│  Markdown notes, JSONL observations, sector canvases            │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1 — Data Pipeline (Phase 1)  ← CURRENT FOCUS             │
│  Fetchers, normalizers, validators, atomic I/O, provenance      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 0 — Foundation (Milestone 1.0)  ← JUST BUILT             │
│  IDs, models, provenance, atomic I/O, schemas, docs             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 0 — Foundation

Stable building blocks everything else uses. **Do not break these without a
migration plan.**

### `investorlens.ids` — deterministic IDs

Every entity gets a stable ID of the form `<prefix>_<12-char-sha256-hex>`.

- **prefix**: 2–4 letter entity-type code (`co`, `sec`, `isin`, `obs`, `ca`, ...)
- **hash**: SHA-256 of the canonicalized content (sorted keys, UTF-8, floats rounded to 6 decimals)

Why this matters:
- Re-running a fetcher produces the same IDs → no duplicates.
- Two fetchers extracting the same fact from different sources converge on the same ID
  *only if they share the same content key* — which is intentional. For observations,
  the source is part of the key, so the same fact from two sources creates two
  observations, which can then be cross-validated in Phase 4.

### `investorlens.models` — Pydantic core models

Defined in `src/investorlens/models/core.py`:

| Model              | Purpose                                              | ID key                                            |
|--------------------|------------------------------------------------------|---------------------------------------------------|
| `Company`          | legal entity                                         | `{isin}` or `{name, nse_symbol}`                  |
| `Security`         | tradable instrument                                  | `{isin}`                                          |
| `ISINMaster`       | canonical identity row                               | `{isin}`                                          |
| `Sector`           | top-level sector                                     | `{name}`                                          |
| `Industry`         | sub-sector                                           | `{name, sector_id}`                               |
| `Source`           | publisher/dataset                                    | `{slug}`                                          |
| `Document`         | a specific artifact (PDF, zip, ...)                  | `{source_id, title, url}`                         |
| `Observation`      | one fact at a point in time                          | `{subject_id, kind, period, as_of, source_id}`    |
| `CorporateAction`  | split/bonus/dividend/merger/...                      | `{security_id, action_type, ex_date}`             |

Every model:
- is a Pydantic v2 `BaseModel` (strict validation);
- embeds a `Provenance` record;
- auto-computes its `id` in a `model_validator(mode="after")`.

### `investorlens.models.provenance` — provenance spec

Required fields: `source` (slug), `retrieved_at` (UTC).
Optional fields: `source_url`, `document_id`, `reporting_period`, `page`, `section`,
`table`, `extraction_method`, `original_value`, `confidence`, `notes`.

Confidence buckets: `high`, `medium`, `low`, `estimated`, `hypothesized`.

### `investorlens.io` — atomic, idempotent I/O

- `write_json(path, data)` — atomic write (tmp + `os.replace`), canonical JSON
  (sorted keys, fixed indent). Two writes of the same data produce byte-identical files.
- `write_jsonl(path, records)` — atomic JSONL write, sorted by `id`.
- `upsert_records(path, new_records, key="id")` — read-modify-write JSONL with
  deduplication. Returns `{inserted, updated, total}`. **No rewrite if content is
  byte-identical** — keeps git diffs and mtimes clean.

### `schemas/` — JSON Schema files

External validation/interop. Each Pydantic model has a sibling JSON Schema.
Useful for:
- validating data coming *from* external systems (e.g. a community-contributed CSV);
- generating documentation;
- providing a stable contract for the future React UI.

---

## Layer 1 — Data Pipeline (Phase 1, current focus)

Not yet built. Planned structure:

```
scripts/
├── init_workspace.py          # creates data/ subdirs, writes empty masters
├── fetchers/
│   ├── fetch_bhavcopy.py      # NSE Equity bhavcopy (daily)
│   ├── fetch_isin_master.py   # NSE + BSE securities list
│   ├── fetch_corp_actions.py  # NSE/BSE corporate actions
│   └── fetch_hist_prices.py   # adjusted historical prices (yfinance fallback)
├── builders/
│   ├── build_isin_master.py   # merges NSE + BSE into canonical master
│   └── build_observations.py  # converts raw bhavcopy → Observation records
└── validate/
    └── validate_outputs.py    # runs JSON Schema validation on data/processed/
```

Every fetcher MUST:
1. use `requests` with a session and a sane rate limiter (≤ 3 req/s);
2. cache raw responses to `data/raw/<source>/<date>/`;
3. emit normalized records as JSONL to `data/processed/<dataset>.jsonl`;
4. attach `Provenance` to every record;
5. be idempotent — re-running on the same date upserts, does not duplicate.

---

## Layer 2 — Knowledge Base (Phase 2, future)

Per-company Markdown notes generated from structured data:
- YAML frontmatter (machine-readable)
- Human-readable sections (Business, Products, Customers, Suppliers, ...)
- Dataview queries for dashboards
- One `.canvas` per sector (≤ 80 nodes)
- Top-level index canvas linking sectors

Large-scale graph (>80 nodes) lives in the React app using Cytoscape.js, not Obsidian Canvas.

---

## Layer 3 — Value-Chain Graph (Phase 3, future)

Nodes: `company`, `sector`, `industry`, `product`, `raw_material`, `supplier`,
`customer`, `macro_driver`, `metric`.

Edges (`value_chain_edge`):
- `supplies`, `customer_of`, `competes_with`, `depends_on`, `uses`, `produces`,
  `benefits_from`, `hurt_by`, `exposed_to`.

Every edge carries: source, evidence, confidence, direction, magnitude (if any),
time period, validation status (`VALIDATED` / `HYPOTHESIZED` / `WEAKLY_SUPPORTED`).

---

## Layer 4 — Algorithms (Phase 4, future)

Sector Leontief (MOSPI SUT + OECD ICIO + pymrio), exposure matrix
(Drivers × Companies), transparent driver→company scoring (with decomposition),
empirical validation (rolling betas, event studies, historical shock analysis).

**Critical rule**: do not start Phase 4 until Phase 1–3 data is sufficient.

---

## Cross-cutting concerns

### Reproducibility

- All scripts deterministic (sorted output, no random IDs).
- Raw downloads cached with date-stamped filenames.
- Each processed file is canonical JSON (sorted keys, fixed indent).

### Caching

- HTTP responses cached to `data/raw/<source>/<date>/`.
- Re-running a fetcher for the same date reads from cache, no HTTP.

### Rate limiting

- Default: ≤ 3 requests/sec, configurable per source.
- Use `time.sleep` between calls; do not parallelize aggressively.

### Error handling

- Fetchers must fail gracefully: log the error, skip the record, continue.
- Never crash the whole pipeline because one record failed.
- Atomic writes ensure no partial outputs.

### Logging

- Use Python `logging`, not `print`.
- Log: start/end of fetch, record counts, errors with context.
- Future: structured JSON logs to `data/provenance/runs/<date>.log`.

### GitHub Actions

- Daily job: bhavcopy + corp actions + ISIN master refresh.
- Weekly job: historical price backfill, macro dataset refresh.
- Monthly job: full re-validation of all outputs.
- Each job commits results back to the repo (or pushes to a data branch).
- Retry logic: up to 3 retries with exponential backoff.

---

## Migration policy

Before changing any schema (Layer 0):
1. inspect all dependents (`grep -r` for the field name);
2. write a migration script if existing data needs rewriting;
3. update `docs/DATA_MODEL.md` and the relevant JSON Schema;
4. update tests;
5. run tests;
6. only then merge.
