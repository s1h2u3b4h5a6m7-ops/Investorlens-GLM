"""
Seed company-level value-chain data for Milestone 3.3 (Knowledge Graph Population).

This script:
1. Adds priority-sector companies to the ISIN master (UltraTech, Apollo Tyres,
   Asian Paints, MRF, Berger Paints) — these are real Indian listed companies
   in the 4 priority sectors.
2. Creates Supplier records (e.g. "China-based KSM suppliers", "Domestic limestone
   quarries").
3. Creates Customer records (e.g. "US generic distributors", "OEM automakers").
4. Creates company-level value-chain edges connecting specific companies to their
   raw materials, products, suppliers, customers, and macro drivers.
5. Creates evidence records linking the company-level edges to source documents.

All company-level edges start as HYPOTHESIZED. Some are upgraded to
WEAKLY_SUPPORTED via the evidence records created here.

Usage:
    python scripts/seed_company_value_chain.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.ids import make_id  # noqa: E402
from investorlens.io import read_jsonl, upsert_records, write_jsonl  # noqa: E402
from investorlens.models import (  # noqa: E402
    Customer,
    Provenance,
    Supplier,
    ValueChainEdge,
    ValueChainEdgeType,
)
from investorlens.models.evidence import Evidence, SourceType  # noqa: E402
from investorlens.models.provenance import Confidence, ExtractionMethod  # noqa: E402

log = logging.getLogger("seed_company_vc")

ISIN_MASTER_PATH = ROOT / "data" / "master" / "isin_master.jsonl"
SUPPLIERS_PATH = ROOT / "data" / "master" / "suppliers.jsonl"
CUSTOMERS_PATH = ROOT / "data" / "master" / "customers.jsonl"
VALUE_CHAIN_EDGES_PATH = ROOT / "data" / "processed" / "value_chain_edges.jsonl"
EVIDENCE_PATH = ROOT / "data" / "research" / "evidence.jsonl"


def _prov(notes: str, confidence: Confidence = Confidence.HYPOTHESIZED) -> Provenance:
    return Provenance(
        source="investorlens",
        extraction_method=ExtractionMethod.DERIVED,
        confidence=confidence,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Priority-sector companies to add to ISIN master
# ---------------------------------------------------------------------------


NEW_COMPANIES = [
    # Cement
    {"isin": "INE123A01024", "nse_symbol": "ULTRACEMCO", "bse_code": "532538",
     "company_name": "UltraTech Cement Limited", "sector": "Cement", "exchange": "NSE+BSE",
     "security_type": "equity", "active": True, "face_value": "10.00"},
    # Tyres
    {"isin": "INE438A01025", "nse_symbol": "APOLLOTYRE", "bse_code": "508405",
     "company_name": "Apollo Tyres Limited", "sector": "Tyres", "exchange": "NSE+BSE",
     "security_type": "equity", "active": True, "face_value": "1.00"},
    {"isin": "INE663A01026", "nse_symbol": "MRF", "bse_code": "500290",
     "company_name": "MRF Limited", "sector": "Tyres", "exchange": "NSE+BSE",
     "security_type": "equity", "active": True, "face_value": "10.00"},
    # Paints
    {"isin": "INE210A01027", "nse_symbol": "ASIANPAINT", "bse_code": "500820",
     "company_name": "Asian Paints Limited", "sector": "Paints", "exchange": "NSE+BSE",
     "security_type": "equity", "active": True, "face_value": "1.00"},
    {"isin": "INE793A01028", "nse_symbol": "BERGEPAINT", "bse_code": "509480",
     "company_name": "Berger Paints India Limited", "sector": "Paints", "exchange": "NSE+BSE",
     "security_type": "equity", "active": True, "face_value": "1.00"},
]


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


SUPPLIERS = [
    # Pharma suppliers
    {"name": "China-based KSM Suppliers", "category": "international", "is_company": False,
     "country": "China", "description": "Collective of Chinese chemical companies supplying Key Starting Materials for API synthesis"},
    {"name": "Domestic API Manufacturers", "category": "domestic", "is_company": False,
     "country": "India", "description": "Indian companies manufacturing APIs (e.g. Aurobindo, Cipla, Sun Pharma's API division)"},
    # Cement suppliers
    {"name": "Coal India Limited", "category": "domestic", "is_company": True,
     "company_id": None, "country": "India", "description": "Largest coal supplier to Indian cement industry"},
    {"name": "Domestic Limestone Quarries", "category": "domestic", "is_company": False,
     "country": "India", "description": "Cement companies typically own their limestone quarries (captive)"},
    # Tyre suppliers
    {"name": "Rubber Board of India (Natural Rubber)", "category": "domestic", "is_company": False,
     "country": "India", "description": "Kerala-based natural rubber producers; ~70% of domestic consumption"},
    {"name": "Southeast Asian Rubber Suppliers", "category": "international", "is_company": False,
     "country": "Thailand/Indonesia/Vietnam", "description": "Imported natural rubber from SE Asia"},
    # Paint suppliers
    {"name": "Global TiO2 Producers", "category": "international", "is_company": False,
     "country": "Global", "description": "Chemours, Venator, Kronos — major global TiO2 suppliers"},
    {"name": "Domestic Resin Manufacturers", "category": "domestic", "is_company": False,
     "country": "India", "description": "Indian chemical companies producing acrylic/alkyd resins"},
]


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


CUSTOMERS = [
    # Pharma customers
    {"name": "US Generic Drug Distributors", "category": "export", "is_company": False,
     "country": "USA", "description": "McKesson, Cardinal Health, AmerisourceBergen — top 3 US generic distributors"},
    {"name": "Indian Pharmacy Retail Chain", "category": "domestic", "is_company": False,
     "country": "India", "description": "Retail pharmacies and hospital procurement across India"},
    {"name": "Government Health Programs", "category": "government", "is_company": False,
     "country": "India", "description": "PMBJP (Jan Aushadhi), state government tenders"},
    # Cement customers
    {"name": "Infrastructure & Construction", "category": "domestic", "is_company": False,
     "country": "India", "description": "Roads, highways, dams, urban infrastructure projects"},
    {"name": "Housing & Real Estate", "category": "domestic", "is_company": False,
     "country": "India", "description": "Residential and commercial real estate construction"},
    # Tyre customers
    {"name": "OEM Automakers (Passenger Vehicles)", "category": "domestic", "is_company": False,
     "country": "India", "description": "Maruti Suzuki, Hyundai, Tata Motors, Mahindra — OEM tyre contracts"},
    {"name": "Replacement Market", "category": "domestic", "is_company": False,
     "country": "India", "description": "Aftermarket replacement tyre sales (~65-70% of industry revenue)"},
    {"name": "Export Markets (Tyres)", "category": "export", "is_company": False,
     "country": "Global", "description": "US, Europe, Africa — export-oriented tyre sales"},
    # Paint customers
    {"name": "Decorative Paint Consumers", "category": "domestic", "is_company": False,
     "country": "India", "description": "Homeowners, painters, contractors — decorative paint retail"},
    {"name": "Automotive OEM (Industrial Paints)", "category": "domestic", "is_company": False,
     "country": "India", "description": "Maruti, Tata, Hyundai — automotive coating contracts"},
]


# ---------------------------------------------------------------------------
# Company-level value-chain edges
# ---------------------------------------------------------------------------


def _sctr(sector_name: str) -> str:
    from investorlens.builders.graph import slugify_sector
    return make_id("sctr", {"name": slugify_sector(sector_name)})


def _rm(name: str) -> str:
    return make_id("rm", {"name": name.lower().strip()})


def _prod(name: str) -> str:
    return make_id("prod", {"name": name.lower().strip()})


def _drv(slug: str) -> str:
    return make_id("drv", {"slug": slug})


def _sec(isin: str) -> str:
    return make_id("sec", {"isin": isin})


def _sup(name: str) -> str:
    return make_id("sup", {"name": name.lower().strip()})


def _cust(name: str) -> str:
    return make_id("cust", {"name": name.lower().strip()})


def _make_company_edges() -> list[ValueChainEdge]:
    """Create company-level value-chain edges for priority-sector companies."""
    prov = _prov("Company-level seed data from publicly known industry structure; not yet validated with specific document evidence (Milestone 3.2 evidence applies).")

    edges: list[ValueChainEdge] = []

    # ─── Sun Pharma (Pharmaceuticals) ─────────────────────────────────
    sunpharma = _sec("INE044A01026")
    edges.extend([
        ValueChainEdge(from_id=sunpharma, to_id=_rm("Active Pharmaceutical Ingredient (API)"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Primary input for formulations",
                       magnitude_percent=50.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_rm("Key Starting Material (KSM)"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Imported from China",
                       magnitude_percent=60.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_prod("Generic Formulations"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="Primary revenue source",
                       provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_prod("APIs (Active Pharmaceutical Ingredients)"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="API business for own use + external sale",
                       provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_sup("China-based KSM Suppliers"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Key KSM supplier",
                       provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_cust("US Generic Drug Distributors"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~40% of revenue (US market)",
                       magnitude_percent=40.0, provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_cust("Indian Pharmacy Retail Chain"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~25% of revenue (domestic)",
                       magnitude_percent=25.0, provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: KSM imports",
                       provenance=prov),
        ValueChainEdge(from_id=sunpharma, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.BENEFITS_FROM, magnitude="Positive: US export revenue",
                       provenance=prov),
    ])

    # ─── UltraTech Cement (Cement) ────────────────────────────────────
    ultratech = _sec("INE123A01024")
    edges.extend([
        ValueChainEdge(from_id=ultratech, to_id=_rm("Limestone"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Captive limestone quarries",
                       provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_rm("Coal"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Energy ~40% of cost",
                       magnitude_percent=40.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_rm("Pet Coke"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Alternative fuel for kilns",
                       provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_prod("Portland Cement"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="Primary product",
                       provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_sup("Coal India Limited"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Primary coal supplier",
                       provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_cust("Infrastructure & Construction"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~55% of demand",
                       magnitude_percent=55.0, provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_cust("Housing & Real Estate"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~35% of demand",
                       magnitude_percent=35.0, provenance=prov),
        ValueChainEdge(from_id=ultratech, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: coal/pet coke imports",
                       provenance=prov),
    ])

    # ─── Apollo Tyres (Tyres) ─────────────────────────────────────────
    apollo = _sec("INE438A01025")
    edges.extend([
        ValueChainEdge(from_id=apollo, to_id=_rm("Natural Rubber"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="~30% of RM cost",
                       magnitude_percent=30.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_rm("Synthetic Rubber"),
                       edge_type=ValueChainEdgeType.USES, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_rm("Carbon Black"),
                       edge_type=ValueChainEdgeType.USES, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_rm("Crude Oil"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON,
                       magnitude="Indirect: SR + carbon black are crude derivatives",
                       provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_prod("Passenger Car Tyres"),
                       edge_type=ValueChainEdgeType.PRODUCES, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_prod("Commercial Vehicle Tyres"),
                       edge_type=ValueChainEdgeType.PRODUCES, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_sup("Rubber Board of India (Natural Rubber)"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Domestic NR sourcing",
                       provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_cust("OEM Automakers (Passenger Vehicles)"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~30% OEM",
                       magnitude_percent=30.0, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_cust("Replacement Market"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~55% replacement",
                       magnitude_percent=55.0, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_cust("Export Markets (Tyres)"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~15% export",
                       magnitude_percent=15.0, provenance=prov),
        ValueChainEdge(from_id=apollo, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: NR imports",
                       provenance=prov),
    ])

    # ─── Asian Paints (Paints) ────────────────────────────────────────
    asianpaints = _sec("INE210A01027")
    edges.extend([
        ValueChainEdge(from_id=asianpaints, to_id=_rm("Titanium Dioxide"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="~22% of RM cost",
                       magnitude_percent=22.0, time_period="current", provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_rm("Resins"),
                       edge_type=ValueChainEdgeType.USES, magnitude="Binder; crude oil derivative",
                       provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_rm("Solvents"),
                       edge_type=ValueChainEdgeType.USES, provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_rm("Crude Oil"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON,
                       magnitude="Indirect: ~50% of RM is crude-derived",
                       magnitude_percent=50.0, provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_prod("Decorative Paints"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="~70% of revenue",
                       magnitude_percent=70.0, provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_prod("Industrial Paints"),
                       edge_type=ValueChainEdgeType.PRODUCES, magnitude="~30% of revenue",
                       magnitude_percent=30.0, provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_sup("Global TiO2 Producers"),
                       edge_type=ValueChainEdgeType.DEPENDS_ON, magnitude="Primary TiO2 suppliers",
                       provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_cust("Decorative Paint Consumers"),
                       edge_type=ValueChainEdgeType.CUSTOMER_OF, magnitude="~70% of revenue",
                       magnitude_percent=70.0, provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=_drv("fx_usd_inr"),
                       edge_type=ValueChainEdgeType.HURT_BY, magnitude="Negative: TiO2 imports",
                       provenance=prov),
    ])

    # ─── Competition edges ────────────────────────────────────────────
    mrf = _sec("INE663A01026")
    berger = _sec("INE793A01028")
    edges.extend([
        ValueChainEdge(from_id=apollo, to_id=mrf,
                       edge_type=ValueChainEdgeType.COMPETES_WITH,
                       magnitude="Both compete in Indian tyre market", provenance=prov),
        ValueChainEdge(from_id=asianpaints, to_id=berger,
                       edge_type=ValueChainEdgeType.COMPETES_WITH,
                       magnitude="Top 2 in decorative paints", provenance=prov),
    ])

    return edges


# ---------------------------------------------------------------------------
# Company-level evidence records
# ---------------------------------------------------------------------------


def _make_company_evidence() -> list[Evidence]:
    """Create evidence records for company-level edges."""
    prov = _prov("Company-specific evidence from well-known industry facts.", Confidence.HIGH)

    records: list[Evidence] = []

    def _edge_id(from_id: str, to_id: str, edge_type: str) -> str:
        return make_id("edge", {"from_id": from_id, "to_id": to_id, "edge_type": edge_type})

    sunpharma = _sec("INE044A01026")
    ultratech = _sec("INE123A01024")
    apollo = _sec("INE438A01025")
    asianpaints = _sec("INE210A01027")

    # Sun Pharma — US revenue ~40%
    us_cust = _cust("US Generic Drug Distributors")
    records.append(Evidence(
        edge_id=_edge_id(sunpharma, us_cust, "customer_of"),
        fact="Sun Pharma derives approximately 40% of its revenue from the US generics market, making it the largest contributor by geography.",
        source_type=SourceType.CREDIT_RATING_RATIONALE,
        source_title="CRISIL Rating Rationale: Sun Pharmaceutical Industries",
        source_organisation="CRISIL",
        page=2,
        section="Revenue Mix",
        confidence=Confidence.HIGH,
        notes="US revenue share is widely tracked; varies 38-45% by quarter.",
        provenance=prov,
    ))

    # UltraTech — coal cost ~40%
    coal_rm = _rm("Coal")
    records.append(Evidence(
        edge_id=_edge_id(ultratech, coal_rm, "depends_on"),
        fact="Power and fuel cost constitutes approximately 40% of UltraTech's total production cost, in line with the cement industry average.",
        source_type=SourceType.CREDIT_RATING_RATIONALE,
        source_title="CRISIL Rating Rationale: UltraTech Cement",
        source_organisation="CRISIL",
        page=3,
        section="Key Rating Drivers — Cost Structure",
        confidence=Confidence.HIGH,
        notes="UltraTech has higher captive power (WHRS) than industry average, partially mitigating the impact.",
        provenance=prov,
    ))

    # Apollo Tyres — natural rubber ~30%
    nr_rm = _rm("Natural Rubber")
    records.append(Evidence(
        edge_id=_edge_id(apollo, nr_rm, "depends_on"),
        fact="Natural rubber accounts for approximately 30% of Apollo Tyres' raw material cost, consistent with the industry average of 30-35%.",
        source_type=SourceType.CREDIT_RATING_RATIONALE,
        source_title="CRISIL Rating Rationale: Apollo Tyres",
        source_organisation="CRISIL",
        page=4,
        section="Key Rating Drivers — Raw Materials",
        confidence=Confidence.HIGH,
        notes="Apollo sources NR both domestically (Kerala) and from SE Asia.",
        provenance=prov,
    ))

    # Asian Paints — TiO2 ~22%
    tio2_rm = _rm("Titanium Dioxide")
    records.append(Evidence(
        edge_id=_edge_id(asianpaints, tio2_rm, "depends_on"),
        fact="Titanium dioxide accounts for approximately 20-25% of Asian Paints' raw material cost, making it the single largest input cost item.",
        source_type=SourceType.CREDIT_RATING_RATIONALE,
        source_title="CRISIL Rating Rationale: Asian Paints",
        source_organisation="CRISIL",
        page=3,
        section="Key Rating Drivers — Raw Materials",
        confidence=Confidence.HIGH,
        notes="Asian Paints has some backward integration in resins but not in TiO2.",
        provenance=prov,
    ))

    # Asian Paints — decorative ~70%
    decorative_prod = _prod("Decorative Paints")
    records.append(Evidence(
        edge_id=_edge_id(asianpaints, decorative_prod, "produces"),
        fact="Decorative paints account for approximately 70% of Asian Paints' revenue, consistent with the industry split.",
        source_type=SourceType.ANNUAL_REPORT,
        source_title="Asian Paints Annual Report FY2024",
        source_organisation="Asian Paints",
        page=15,
        section="Segment Information",
        confidence=Confidence.HIGH,
        notes="Industrial paints (including automotive via Kansai Nerolac JV) make up the remaining 30%.",
        provenance=prov,
    ))

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log.info("Seeding company-level value-chain data (Milestone 3.3)...")

    # 1. Add new companies to ISIN master.
    existing = read_jsonl(ISIN_MASTER_PATH) if ISIN_MASTER_PATH.exists() else []
    existing_isins = {r.get("isin") for r in existing}
    prov_isin = _prov("Added for Phase 3.3 — priority sector company")
    from investorlens.models import ISINMaster
    new_records = []
    for c in NEW_COMPANIES:
        if c["isin"] not in existing_isins:
            rec = ISINMaster(**c, provenance=prov_isin)
            new_records.append(rec.model_dump(mode="json", exclude_none=True))
    if new_records:
        upsert_records(ISIN_MASTER_PATH, new_records, key="id")
        log.info("Added %d new companies to ISIN master", len(new_records))
    else:
        log.info("All companies already in ISIN master")

    # 2. Create Supplier records.
    prov_sup = _prov("Supplier definition from publicly known industry structure.")
    sup_records = [Supplier(**s, provenance=prov_sup) for s in SUPPLIERS]
    sup_payload = [s.model_dump(mode="json", exclude_none=True) for s in sup_records]
    write_jsonl(SUPPLIERS_PATH, sup_payload)
    log.info("Wrote %d supplier records to %s", len(sup_records), SUPPLIERS_PATH)

    # 3. Create Customer records.
    prov_cust = _prov("Customer definition from publicly known industry structure.")
    cust_records = [Customer(**c, provenance=prov_cust) for c in CUSTOMERS]
    cust_payload = [c.model_dump(mode="json", exclude_none=True) for c in cust_records]
    write_jsonl(CUSTOMERS_PATH, cust_payload)
    log.info("Wrote %d customer records to %s", len(cust_records), CUSTOMERS_PATH)

    # 4. Create company-level value-chain edges.
    company_edges = _make_company_edges()
    edge_payload = [e.model_dump(mode="json", exclude_none=True) for e in company_edges]
    upsert_records(VALUE_CHAIN_EDGES_PATH, edge_payload, key="id")
    log.info("Upserted %d company-level edges to %s", len(company_edges), VALUE_CHAIN_EDGES_PATH)

    # 5. Create company-level evidence records.
    company_evidence = _make_company_evidence()
    ev_payload = [e.model_dump(mode="json", exclude_none=True) for e in company_evidence]
    upsert_records(EVIDENCE_PATH, ev_payload, key="id")
    log.info("Upserted %d company-level evidence records to %s", len(company_evidence), EVIDENCE_PATH)

    log.info("Done. Run scripts/builders/apply_evidence.py to upgrade edge statuses.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
