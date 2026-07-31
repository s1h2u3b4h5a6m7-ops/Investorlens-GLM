"""
Source-specific parsers.

Each parser takes raw text/bytes (CSV, XLSX, HTML, ...) from a source and
returns a list of normalized records (Pydantic models or plain dicts).

Parsers MUST be pure functions of their input — no I/O, no network, no time
dependency. This makes them trivially testable with fixtures.

  raw bytes  →  parser  →  [Record, Record, ...]
                              ↑
                       (pure, deterministic)
"""

from . import bhavcopy, bse, corp_actions, mospi, nse, rbi, yahoo

__all__ = ["nse", "bse", "bhavcopy", "yahoo", "corp_actions", "rbi", "mospi"]
