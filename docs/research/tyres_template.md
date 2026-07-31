# Research Template: Tyres

## Source hierarchy

1. **DRHPs** — SEBI filings (Apollo Tyres, MRF, CEAT, JK Tyre)
   - Extract: raw material breakdown, natural rubber sourcing, OEM vs replacement mix, export markets

2. **Annual reports** — Company IR pages
   - Extract: raw material cost as % of revenue, inventory levels, OEM vs replacement revenue split

3. **Credit rating rationales** — CRISIL, ICRA
   - Extract: natural rubber cost %, crude oil linkage, automotive demand sensitivity

## Key research questions

### Raw materials
- [ ] Natural rubber: what % of RM cost? (target: 30-35%)
- [ ] Synthetic rubber: what % of RM cost? What types (SBR, BR, etc.)?
- [ ] Carbon black: what % of RM cost? Domestic vs imported?
- [ ] Steel/nylon tyre cord: what % of RM cost?
- [ ] Is the company backward-integrated into any raw material?

### Cost structure
- [ ] Raw material as % of revenue (target: ~65%)
- [ ] Employee cost as % of revenue
- [ ] Power & fuel as % of revenue
- [ ] What is the inventory cycle for natural rubber? (typically 2-3 months)

### Demand drivers
- [ ] OEM vs replacement market split (replacement is ~65-70% of industry)
- [ ] Commercial vehicle tyre demand (tracks Tonnage freight, CV sales)
- [ ] Passenger car tyre demand (tracks PV sales)
- [ ] Two-wheeler tyre demand (tracks 2W sales)
- [ ] Export market: what % of revenue? Which regions?

### Pricing and margins
- [ ] Pricing power: can companies pass through raw material cost increases?
- [ ] What is the typical lag between RM price increase and price hike? (3-6 months)
- [ ] How do OEM contracts work? (annual rate contracts vs spot)

## Key edges to validate:
- `depends_on` Natural Rubber → validate the 30-35% figure
- `depends_on` Crude Oil → validate the indirect exposure (synthetic rubber + carbon black)
- `exposed_to` USD/INR → validate natural rubber import exposure
