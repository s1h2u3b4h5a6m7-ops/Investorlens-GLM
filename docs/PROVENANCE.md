# Provenance Spec

Provenance is the metadata that makes a fact trustworthy. In InvestorLens,
every important field carries provenance — without it, the fact is treated
as unverified.

> A number without provenance is not considered fully trustworthy.
> — Operating Principle 3

---

## The Provenance record

Defined in `src/investorlens/models/provenance.py` as a Pydantic v2 model.
Embedded as a nested field in every core entity (Company, Security, Observation,
CorporateAction, ...).

### Required fields

| Field          | Type     | Notes                                          |
|----------------|----------|------------------------------------------------|
| `source`       | string   | Stable slug for the publisher (e.g. `nse`).    |
| `retrieved_at` | datetime | UTC ISO-8601 timestamp when we fetched it.     |

### Optional fields

| Field                | Type     | Notes                                                              |
|----------------------|----------|--------------------------------------------------------------------|
| `source_url`         | URL      | Direct link to the artifact.                                       |
| `document_id`        | string   | ID of a `Document` entity in the graph.                            |
| `reporting_period`   | string   | Period the fact refers to: `FY2024`, `2024-09-30`, `Q1-2025`.      |
| `page`               | int      | Page number in a document.                                         |
| `section`            | string   | Section heading.                                                   |
| `table`              | string   | Table identifier.                                                  |
| `extraction_method`  | enum     | See below.                                                         |
| `original_value`     | any      | Raw value before normalization (e.g. `"1,234.56 Cr"` before parsing to float). |
| `confidence`         | enum     | See below. Default `medium`.                                       |
| `notes`              | string   | Free-text caveats.                                                 |

### `extraction_method` enum

| Value             | When to use                                              |
|-------------------|----------------------------------------------------------|
| `official_api`    | Documented public API (NSE/BSE/RBI).                     |
| `bulk_download`   | A daily/monthly bulk file (bhavcopy zip, master CSV).    |
| `xlsx_parse`      | Parsed from an Excel file.                               |
| `pdf_parse`       | Parsed from a PDF.                                       |
| `html_scrape`     | Scraped from an HTML page (use only when no API exists). |
| `manual`          | Entered by a human.                                      |
| `derived`         | Computed from other facts (e.g. adjusted price).         |
| `llm_extracted`   | Extracted by an LLM. **Always set confidence=low** until validated. |

### `confidence` enum

Coarse-grained. The exact probability is rarely meaningful; these buckets are
sufficient for filtering and review.

| Value           | Meaning                                                          |
|-----------------|------------------------------------------------------------------|
| `high`          | Official machine-readable source, recently verified.             |
| `medium`        | Official but stale, or human-entered from a primary document.    |
| `low`           | Scraped, inferred, or LLM-extracted.                             |
| `estimated`     | Explicitly estimated (e.g. interpolated), not directly observed. |
| `hypothesized`  | Plausible but not yet empirically validated.                     |

---

## Example: a price observation

```json
{
  "id": "obs_a3f1b9c2d4e5",
  "subject_id": "sec_9f8e7d6c5b4a",
  "kind": "price_close",
  "period": "2024-09-30",
  "as_of": "2024-09-30",
  "value": 1842.35,
  "unit": "INR",
  "currency": "INR",
  "data_status": "observed",
  "confidence": "high",
  "provenance": {
    "source": "nse",
    "retrieved_at": "2026-07-30T18:30:00Z",
    "source_url": "https://nseindia.com/api/reports?archives=%5B%7B%22name%22%3A%22CM%20Bhavcopy%22%2C%22type%22%3A%22archives%22%2C%22category%22%3A%22capital-market%22%2C%22section%22%3A%22equities%22%7D%5D&date=30-SEP-2024",
    "extraction_method": "bulk_download",
    "confidence": "high",
    "reporting_period": "2024-09-30"
  }
}
```

## Example: an LLM-extracted supplier relationship (low confidence)

```json
{
  "provenance": {
    "source": "company_ar",
    "retrieved_at": "2026-07-30T18:45:00Z",
    "document_id": "doc_abc123def456",
    "page": 42,
    "section": "Raw Materials",
    "extraction_method": "llm_extracted",
    "confidence": "low",
    "notes": "Extracted from annual report PDF page 42 by LLM. Needs human verification."
  }
}
```

## Example: a derived (adjusted) price

```json
{
  "provenance": {
    "source": "investorlens",
    "retrieved_at": "2026-07-30T19:00:00Z",
    "extraction_method": "derived",
    "confidence": "high",
    "notes": "Adjusted close = raw close × adjustment_factor(security_id, ex_date). See CorporateAction records ca_xxx, ca_yyy."
  }
}
```

---

## Source slug registry

A non-exhaustive list of stable slugs. Add new ones as needed; never reuse a slug
for a different source.

| Slug              | Publisher                                         | URL                                       |
|-------------------|---------------------------------------------------|-------------------------------------------|
| `nse`             | National Stock Exchange of India                  | https://nseindia.com                      |
| `bse`             | BSE (formerly Bombay Stock Exchange)              | https://bseindia.com                      |
| `rbi_dbie`        | Reserve Bank of India — DBIE                       | https://dbie.rbi.org.in                   |
| `mospi`           | Ministry of Statistics and Programme Implementation | https://mospi.gov.in                    |
| `tradestat`       | Directorate General of Commercial Intelligence & Statistics | https://tradestat.commerce.gov.in |
| `data_gov_in`     | data.gov.in                                       | https://data.gov.in                       |
| `company_ar`      | A company's annual report                         | (varies)                                  |
| `company_drhp`    | A company's DRHP filed with SEBI                  | (varies)                                  |
| `rating_agency`   | A credit rating agency rationale                  | (varies)                                  |
| `yfinance`        | Yahoo Finance (fallback only)                     | https://finance.yahoo.com                 |
| `investorlens`    | Derived/computed by InvestorLens itself           | (internal)                                |

---

## Rules of thumb

1. **When in doubt, attach provenance.** A field without provenance cannot be
   distinguished from a fabricated value.
2. **Prefer `official_api` or `bulk_download` over `html_scrape`.** Scrapes break
   when the website layout changes; APIs and bulk files are stable.
3. **LLM-extracted facts start at `confidence=low`.** Promote to `medium` only
   after human review; promote to `high` only after cross-validation against
   a second source.
4. **`retrieved_at` is when *we* fetched it**, not when the source published it.
   The source's publication date goes in `Document.published_on`.
5. **`reporting_period` is when the fact *applies***, not when we fetched it.
   A FY2024 annual result fetched in 2026 still has `reporting_period="FY2024"`.
6. **Never silently fabricate.** If a value is unavailable, set `data_status=unavailable`
   and `value=null`. If estimated, set `data_status=estimated` and `confidence=estimated`.
   If hypothesized, set `data_status=hypothesized` and `confidence=hypothesized`.
