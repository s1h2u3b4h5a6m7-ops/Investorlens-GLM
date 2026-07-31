# InvestorLens

> **Data → Knowledge Graph → Value Chain → Impact Algorithms**
> A traceable, continuously updating map of how the Indian business ecosystem works,
> and how real-world forces propagate through it to individual companies.

---

## What this project is

InvestorLens is a long-running, incremental research infrastructure for understanding
Indian listed companies and their business ecosystems. It is *not* a trading system,
*not* a backtester, and *not* a tip generator. It is a **research map**: a structured
record of who depends on whom, who supplies what, which macro forces affect which
companies, and what evidence supports each link.

The system is built around four questions every investor should be able to answer
about any holding:

1. **What does this company actually depend on?** (inputs, suppliers, customers, capital)
2. **Which real-world drivers move it?** (commodities, FX, rates, policies, demand)
3. **How strong is each relationship, and is it validated or hypothesized?**
4. **How does a shock propagate through the industry's value chain?**

---

## Architecture (one-page view)

```
  ┌────────────────────────────┐
  │  Official Data Sources     │   NSE / BSE / RBI / MOSPI / data.gov.in
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  DATA PIPELINE (Phase 1)   │   scheduled, cached, idempotent, provenance-tagged
  │  Collect → Validate →      │
  │  Normalize → Cache → JSON  │
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  STRUCTURED DATA           │   data/master/ data/processed/ data/raw/
  │  (JSON, atomic, idempotent)│
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  KNOWLEDGE BASE (Phase 2)  │   Markdown notes + Dataview + Canvas + React graph
  │  Companies / Products /    │
  │  Suppliers / Customers     │
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  VALUE-CHAIN GRAPH (Phase 3)│  company ↔ supplier ↔ customer; driver ↔ company
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  EXPOSURE MATRIX (Phase 4) │   Driver × Company, with decomposition
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  IMPACT MODELS (Phase 4)   │   Leontief, rolling betas, event studies
  │  + VALIDATION              │   VALIDATED / HYPOTHESIZED / WEAKLY_SUPPORTED
  └─────────────┬──────────────┘
                ↓
  ┌────────────────────────────┐
  │  INVESTORLENS UI           │   Search / Graph / Canvas / Drivers / Companies
  └────────────────────────────┘
```

---

## Repository layout

```
investorlens/
├── src/investorlens/         # Python package (core library)
│   ├── ids/                  # deterministic ID generation
│   ├── models/               # Pydantic core domain models + provenance
│   └── io/                   # atomic, idempotent JSON I/O
├── scripts/                  # one-off + scheduled scripts (fetchers, builders)
├── schemas/                  # JSON Schema files for external validation/interop
├── data/
│   ├── raw/                  # untouched downloads (bhavcopy zips, PDFs, ...)
│   ├── master/               # canonical master records (ISIN master, sectors, ...)
│   ├── processed/            # normalized JSON/JSONL (observations, prices)
│   └── provenance/           # provenance-only sidecar logs
├── docs/
│   ├── ARCHITECTURE.md       # detailed architecture
│   ├── ROADMAP.md            # 4-phase plan with milestone status
│   ├── DATA_MODEL.md         # global schema
│   ├── PROVENANCE.md         # provenance spec
│   └── OPERATING_PRINCIPLES.md
├── tests/                    # pytest suite
├── .github/workflows/        # scheduled GitHub Actions
├── worklog.md                # multi-session work log (append-only)
├── pyproject.toml            # package metadata + pinned deps
└── README.md                 # this file
```

---

## Operating principles (summary)

1. **Data before intelligence** — no scoring on top of unreliable data.
2. **Official/free sources first** — NSE/BSE/RBI/MOSPI/data.gov.in before any commercial site.
3. **Provenance on every important fact** — source, URL, retrieved_at, period, page, method, confidence.
4. **Never silently invent data** — mark as `unavailable` / `estimated` / `hypothesized`.
5. **Idempotency** — same input ⇒ same output, same IDs, no duplicates.
6. **Preserve existing work** — inspect before modifying; never rewrite from scratch.
7. **Work incrementally** — small milestones, each Inspect → Plan → Implement → Test → Verify → Document → Commit.

See `docs/OPERATING_PRINCIPLES.md` for the full list.

---

## Quick start

```bash
# 1. Create a virtualenv (system Python is externally managed — PEP 668)
python3 -m venv .venv
. .venv/bin/activate

# 2. Install (editable, with dev dependencies)
pip install -e ".[dev]"

# 3. Run tests
pytest                       # 312 tests, ~1.2s

# 4. Initialize the workspace (creates data/ subdirs, writes empty masters)
python scripts/init_workspace.py

# 5. End-to-end smoke test (verifies the foundation composes correctly)
python scripts/smoke_test_e2e.py

# 6. Seed all data from test fixtures (offline dev — no network needed)
python scripts/seed_isin_master_from_fixtures.py
python scripts/seed_bhavcopy_from_fixtures.py
python scripts/seed_hist_prices_from_fixtures.py
python scripts/seed_corp_actions_from_fixtures.py
python scripts/seed_macro_from_fixtures.py

# 7. See the pipeline summary (what's in the data/ directory)
python scripts/gh_actions_summary.py

# 8. (Production) Deploy to GitHub for daily auto-updates
#    See docs/DEPLOYMENT.md (15-minute walkthrough)
```

---

## Deploying to GitHub Actions (Phase 1.6)

Once you're ready for the data to update automatically every day:

1. Follow the step-by-step guide in **[`docs/GITHUB_ACTIONS_SETUP.md`](docs/GITHUB_ACTIONS_SETUP.md)**.
2. The daily workflow runs at 18:30 IST (13:00 UTC) Mon–Sat.
3. The weekly backfill runs at 07:30 IST (02:00 UTC) Sundays.
4. Pipeline failures auto-create a GitHub issue with the failure context.
5. Each run writes a Markdown summary to the Actions UI (Summary tab).

---

## Current status

See `docs/ROADMAP.md` for the authoritative milestone tracker.
See `worklog.md` for the multi-session work log.

In short: **Phase 1, Milestone 1.0 (Foundation)** is in progress.

---

## License

MIT. See `LICENSE` (to be added). All data sourced from public official sources
retains the original source's license; InvestorLens claims no copyright on raw data.
