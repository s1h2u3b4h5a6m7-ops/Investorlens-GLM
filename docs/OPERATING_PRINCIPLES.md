# Operating Principles

These principles govern the entire InvestorLens project. They are non-negotiable
unless explicitly overridden by the user.

---

## Principle 1 — Data before intelligence

Never build an advanced scoring or prediction system on top of incomplete or
unreliable data.

**Correct sequence:**

```
Data → Structure → Knowledge → Relationships → Algorithms → Validation
```

If you are tempted to write a "smart" algorithm and the underlying data is
sparse or unverified, **stop**. Go back and fix the data first.

---

## Principle 2 — Official / free sources first

Always look for free official datasets before scraping commercial websites.

**Priority order:**

1. data.gov.in
2. RBI DBIE
3. MOSPI datasets
4. Tradestat
5. NSE / BSE official datasets
6. Company filings
7. DRHPs
8. Annual reports
9. Credit-rating reports
10. Other freely accessible sources
11. Commercial websites — only when necessary and legally/technically appropriate

Do not scrape a commercial website when the same information is available from
an official source. The official source is more reliable, more stable, and
typically comes with better provenance.

---

## Principle 3 — Every important fact needs provenance

Every structured fact should ideally carry:

- `source` (slug)
- `source_url`
- `document_id` (for cited PDFs, Excel files, ...)
- `retrieved_at`
- `reporting_period`
- `page` / `section` / `table`
- `extraction_method`
- `confidence`
- `original_value` (before normalization)
- `normalized value` (the actual field value)

See `docs/PROVENANCE.md` for the canonical record format.

> A number without provenance is not considered fully trustworthy.

---

## Principle 4 — Never silently invent data

If information is unavailable, choose one of:

- `data_status = "unavailable"`, `value = null`
- `data_status = "estimated"`, `confidence = "estimated"` — if genuinely estimated
- `data_status = "hypothesized"`, `confidence = "hypothesized"` — if inferred

**Never fabricate a value merely to complete a dataset.** A null with provenance
is far more valuable than a fabricated number that looks complete.

---

## Principle 5 — Idempotency

Running the same pipeline twice should not create duplicate records or corrupt
existing data.

The system uses:

- stable IDs (content-hash based — see `investorlens.ids`)
- deterministic filenames (date-based, slug-based)
- deterministic node IDs
- timestamps where appropriate (in `provenance.retrieved_at`, not in IDs)
- content hashes where useful (for files)
- upsert/update behavior (see `investorlens.io.upsert_records`)

A re-run that produces zero changes should leave the repository in a byte-identical
state. This keeps git diffs clean and makes regressions obvious.

---

## Principle 6 — Preserve existing work

Before modifying anything:

1. inspect the existing repository,
2. understand its architecture,
3. identify what already works,
4. avoid unnecessary rewrites,
5. preserve compatible existing functionality.

**Never destroy working functionality merely to introduce a new architecture.**
If a refactor is needed, do it incrementally: add the new path, migrate callers
one at a time, remove the old path only when nothing depends on it.

---

## Principle 7 — Work incrementally

Do not attempt to build all four phases simultaneously.

Complete work in small milestones. For every milestone:

```
Inspect → Plan → Implement → Test → Verify → Document → Commit
```

A good milestone:
- can be completed in one work session;
- has clear exit criteria;
- unlocks the next milestone;
- leaves the repository in a working state.

---

## Principle 8 — Reproducibility

Anyone, at any time, given the same inputs, should be able to produce the same
outputs. This means:

- All scripts deterministic (no random IDs, no random ordering).
- Raw inputs cached (re-running on the same date reads from cache, not HTTP).
- Outputs canonical (sorted keys, fixed indent — see `investorlens.io.write_json`).
- Dependencies pinned in `pyproject.toml`.
- Tests run on every commit.

---

## Principle 9 — Zero / near-zero operating cost

The project targets ₹0 operating cost wherever reasonably possible.

Prefer:
- GitHub (free for public repos)
- GitHub Actions within legitimate free allowances
- public datasets
- open-source Python libraries
- free APIs
- static hosting
- local computation
- free research sources (DRHPs, annual reports, rating rationales)

Do not introduce paid infrastructure unless:
1. it provides a meaningful capability,
2. there is no reasonable free alternative,
3. the user explicitly approves it.

Never design the architecture around an assumed paid service without approval.

---

## Principle 10 — Clear separation of facts, hypotheses, and validated relationships

Every relationship in the knowledge graph must eventually have an explicit status:

| Status             | Meaning                                                    |
|--------------------|------------------------------------------------------------|
| `VALIDATED`        | Supported by empirical evidence (rolling beta, event study, shock analysis). |
| `WEAKLY_SUPPORTED` | Some evidence exists but validation is incomplete.         |
| `HYPOTHESIZED`     | Economically plausible but not validated.                  |

**Never present a hypothesis as an established fact.** The UI must always
display the validation status next to the relationship.

---

## Principle 11 — Transparency over accuracy

A transparent, decomposable, slightly-wrong score is more valuable than a
black-box score that happens to be right.

Every score in Phase 4 must be decomposable:
"Company X received a +0.62 impact score from Driver Y because:
  - exposure: +0.8 (high sensitivity to crude oil, per FY2024 AR raw-material table)
  - transmission: ×0.9 (some pass-through, per Q3 concall)
  - magnitude: ×0.95 (medium inventory hedge)
  - direction: negative
  → +0.8 × 0.9 × 0.95 × (-1) = -0.684, normalized to +0.62 on a -1..+1 scale
  because we negate for 'negative impact' display."

If a score cannot be decomposed this way, do not produce it.
