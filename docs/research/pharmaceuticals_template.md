# Research Template: Pharmaceuticals

This template guides research for the Pharmaceuticals / API sector.
Fill in each section with evidence from the listed source types.

## Source hierarchy (priority order)

1. **DRHPs** — IPO prospectuses filed with SEBI. Search at https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=5&ssid=14
   - Key DRHPs to find: Sun Pharma (1994), Cipla, Dr. Reddy's, Aurobindo, Lupin
   - What to extract: supplier names, raw material breakdown, customer concentration, manufacturing process description, risk factors

2. **Annual reports** — Company websites → Investor Relations → Annual Reports
   - What to extract: raw material cost table (usually in "Cost of Materials Consumed"), segment revenue, geographical breakdown, management discussion of input costs

3. **Credit rating rationales** — CRISIL, ICRA, India Ratings
   - What to extract: cost structure commentary, input price sensitivity, competitive position, demand outlook
   - Access: free summaries on rating agency websites; detailed reports require login

## Key research questions

### Raw materials
- [ ] What % of total cost is API/KSM procurement?
- [ ] What % of APIs/KSMs are imported from China?
- [ ] Which specific KSMs are most dependent on China?
- [ ] Are there Indian API manufacturers who are backward-integrated into KSMs?
- [ ] What is the typical inventory cycle (how many months of KSM stock)?

### Customers
- [ ] Who are the top 5 US generic distributors? (McKesson, Cardinal Health, AmerisourceBergen, etc.)
- [ ] What % of revenue comes from the US market vs domestic vs other exports?
- [ ] Are there customer concentration risks (single distributor >10% of revenue)?

### Cost drivers
- [ ] What is the USD/INR sensitivity? (1% depreciation = ?% margin impact)
- [ ] How does USFDA observation/action affect specific facilities?
- [ ] What is the R&D spend as % of revenue?

### Competitive dynamics
- [ ] Market share of top 5 pharma companies in India
- [ ] Which therapeutic areas are most competitive?
- [ ] How does generic pricing erosion work in the US market?

## Evidence recording

For each fact found, create an Evidence record in `data/research/evidence.jsonl`:
```json
{
  "edge_id": "edge_<hash>",
  "fact": "specific claim with numbers",
  "source_type": "annual_report | credit_rating_rationale | drhp",
  "source_title": "Sun Pharma Annual Report FY2024",
  "source_organisation": "Sun Pharmaceutical Industries",
  "page": 42,
  "section": "Cost of Materials Consumed",
  "confidence": "high",
  "extraction_method": "manual | pdf_parse"
}
```

Run `python scripts/builders/apply_evidence.py` after adding evidence to upgrade edge validation statuses.
