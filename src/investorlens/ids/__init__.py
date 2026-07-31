"""
Deterministic ID generation for InvestorLens.

Every entity in the system gets a stable ID derived from its meaningful content,
NOT from a counter, timestamp, or random value. This guarantees:

  - idempotency: re-running the same pipeline produces the same IDs
  - deduplication: the same real-world fact maps to the same ID across runs
  - referential integrity: edges/links stay valid even if a node is regenerated

ID format:  <prefix>_<short_hash>
  - prefix: 2-4 letter entity type code (e.g. "co" for company, "sec" for security)
  - short_hash: 12-character SHA-256 hex digest of the canonical content

Example:
    company_id = make_id("co", {"isin": "INE002A01018"})
    # -> "co_a3f1b9c2d4e5"
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

__all__ = [
    "make_id",
    "content_hash",
    "canonicalize",
]

# Entity-type prefixes — keep this list small and stable.
# Adding a new prefix is a schema change; document it in docs/DATA_MODEL.md.
ENTITY_PREFIXES: frozenset[str] = frozenset(
    {
        "co",      # company
        "sec",     # security (a tradable instrument)
        "isin",    # ISIN identifier record
        "sctr",    # sector (introduced in Milestone 2.2 to resolve sec_ collision with Security)
        "ind",     # industry
        "prod",    # product
        "rm",      # raw material
        "sup",     # supplier
        "cust",    # customer
        "drv",     # macro driver
        "met",     # metric
        "src",     # source (website / publisher)
        "doc",     # document (an actual file / URL)
        "edge",    # value-chain edge / relationship
        "exp",     # exposure record
        "ca",      # corporate action
        "obs",     # observation (a single numeric/string fact at a point in time)
        "evt",     # real-world event
        "mdl",     # model
        "scr",     # score
        "val",     # validation record
    }
)

_HASH_LEN = 12


def canonicalize(value: Any) -> str:
    """
    Serialize any Python value into a canonical, deterministic JSON string.

    Used so that two semantically-equal inputs always produce the same hash,
    regardless of key insertion order or float formatting.

    Rules:
      - dicts sorted by key
      - tuples/lists preserved as-is (order matters)
      - strings UTF-8 encoded
      - None -> null
      - numbers preserved; floats rounded to 6 decimals to absorb float noise
    """
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    # Fallback: stringify unknown types
    return str(value)


def content_hash(value: Any) -> str:
    """Return the 12-char SHA-256 hex digest of the canonicalized input."""
    payload = canonicalize(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:_HASH_LEN]


def make_id(prefix: str, content: Mapping[str, Any] | Sequence[Any] | str) -> str:
    """
    Construct a deterministic ID.

    Args:
        prefix: entity-type code, must be in ENTITY_PREFIXES.
        content: the meaningful fields that uniquely identify this entity.
                 For a company, this is typically {"isin": "INE..."}.
                 For an observation, it's (company_id, metric_id, period, source_id).

    Returns:
        A stable ID like "co_a3f1b9c2d4e5".

    Raises:
        ValueError: if the prefix is not in the known set.
    """
    if prefix not in ENTITY_PREFIXES:
        raise ValueError(
            f"Unknown entity prefix '{prefix}'. "
            f"Known prefixes: {sorted(ENTITY_PREFIXES)}. "
            f"Add new prefixes in src/investorlens/ids/__init__.py and document in docs/DATA_MODEL.md."
        )
    if isinstance(content, str):
        payload = content
    else:
        payload = content_hash(content)
    return f"{prefix}_{payload}"
