"""
Builders — pure functions that merge / transform structured records.

Like parsers, builders are pure functions of their inputs: no I/O, no network,
no time dependency. They take Pydantic models (or dicts) and return Pydantic
models (or dicts). This makes them trivially testable.

  [Record] + [Record]  →  builder  →  [MergedRecord]
                              ↑
                       (pure, deterministic)
"""

from .adjusted_prices import build_adjusted_prices, compute_adjustment_factor, adjust_prices_for_security
from .canvas import build_index_canvas, build_sector_canvas
from .evidence_upgrader import count_evidence_by_edge, upgrade_edges_with_evidence
from .graph import build_graph_data
from .isin_master import build_isin_master, merge_two_isin_records
from .notes import build_company_note, slugify_company
from .sector_notes import build_sector_note, format_value_chain_edges_table

__all__ = [
    "build_isin_master",
    "merge_two_isin_records",
    "build_adjusted_prices",
    "compute_adjustment_factor",
    "adjust_prices_for_security",
    "build_company_note",
    "slugify_company",
    "build_sector_canvas",
    "build_index_canvas",
    "build_graph_data",
    "build_sector_note",
    "format_value_chain_edges_table",
    "upgrade_edges_with_evidence",
    "count_evidence_by_edge",
]
