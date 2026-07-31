"""InvestorLens — Data → Knowledge Graph → Value Chain → Impact Algorithms.

Top-level package. Submodules:
  - investorlens.ids      — deterministic ID generation
  - investorlens.models   — Pydantic core domain models
  - investorlens.io       — atomic, idempotent JSON I/O
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("investorlens")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.1.0+dev"

__all__ = ["__version__"]
