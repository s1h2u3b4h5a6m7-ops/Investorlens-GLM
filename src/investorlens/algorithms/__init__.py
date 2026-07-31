"""
InvestorLens algorithms package.

Phase 4 modules:
  - leontief: input-output model for shock propagation through the value chain

Each algorithm is a pure function — no I/O, no side effects. Inputs are
plain Python data structures (dicts, lists); outputs are dicts/lists that
can be serialized to JSON.
"""

from . import exposure_matrix, leontief, scoring, status_upgrader, validation

__all__ = ["leontief", "exposure_matrix", "scoring", "validation", "status_upgrader"]
