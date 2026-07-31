"""
Atomic, idempotent JSON I/O for InvestorLens.

Two guarantees:

  1. Atomicity: writes either fully succeed or leave the existing file untouched.
     We never leave a half-written file on disk. Implementation: write to a
     `<path>.tmp` file, fsync, then os.replace() (atomic on POSIX).

  2. Idempotency: upserts keyed on `id`. If the same record is written twice
     with identical content, the file is left unchanged (verified by content hash).
     This keeps git diffs clean and makes pipelines safely re-runnable.

Usage:
    from investorlens.io import write_json, upsert_records

    write_json("data/master/companies.json", record_dict)

    upsert_records(
        "data/processed/observations.jsonl",
        new_observations,
        key="id",
    )
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "write_json",
    "read_json",
    "upsert_records",
    "read_jsonl",
    "write_jsonl",
    "ensure_dir",
    "CachedSession",
    "FetchError",
]


# Submodule re-export — keep at end to avoid circular imports.
from .http import CachedSession, FetchError  # noqa: E402


def ensure_dir(path: str | Path) -> Path:
    """Create the directory (and parents) if it does not exist. Idempotent."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default_serializer(obj: Any) -> Any:
    """Fallback JSON serializer for non-standard types (date, datetime, Decimal, Enum)."""
    from datetime import date, datetime
    from decimal import Decimal
    from enum import Enum

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        # Use str to preserve precision; float() would lose it.
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_json(path: str | Path, data: Any, *, indent: int = 2, sort_keys: bool = True) -> Path:
    """Atomically write `data` as JSON to `path`.

    - Writes to a sibling .tmp file first, fsyncs, then atomically replaces.
    - The output is canonical (sorted keys, fixed indent) so that two writes
      of the same data produce byte-identical files. This makes git diffs clean
      and is essential for idempotent pipelines.
    """
    p = Path(path)
    ensure_dir(p.parent)
    payload = json.dumps(data, indent=indent, sort_keys=sort_keys, default=_default_serializer, ensure_ascii=False)
    payload_bytes = payload.encode("utf-8")

    # tempfile in the same dir guarantees the os.replace() is atomic on the same filesystem.
    fd, tmp_path = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, p)
    except Exception:
        # Best-effort cleanup of the temp file if anything went wrong.
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return p


def read_json(path: str | Path) -> Any:
    """Read JSON from `path`. Raises FileNotFoundError if missing."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL file (one JSON object per line). Skips blank lines."""
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> Path:
    """Atomically overwrite `path` with the given records as JSONL.

    Sorts records by their `id` field (if present) so output is deterministic
    regardless of fetch order.
    """
    materialized = list(records)
    # Deterministic ordering by id if available.
    if materialized and isinstance(materialized[0], Mapping) and "id" in materialized[0]:
        materialized.sort(key=lambda r: str(r.get("id", "")))
    lines = [
        json.dumps(r, sort_keys=True, default=_default_serializer, ensure_ascii=False)
        for r in materialized
    ]
    payload = ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
    p = Path(path)
    ensure_dir(p.parent)
    fd, tmp_path = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return p


def upsert_records(
    path: str | Path,
    new_records: Sequence[Mapping[str, Any]],
    *,
    key: str = "id",
) -> dict[str, int]:
    """Idempotently merge `new_records` into a JSONL file at `path`.

    Behavior:
      - Reads existing records (if file exists).
      - Builds a dict keyed by `key` (default: "id").
      - Updates existing records with new values, appends new ones.
      - Writes the merged result back atomically, sorted by key.

    Returns a small stats dict: {"inserted": N, "updated": N, "total": N}.

    If the new content is byte-identical to the existing file, the file is
    left untouched (no rewrite) — keeps mtimes clean and git diffs empty.
    """
    existing: dict[str, dict] = {}
    if os.path.exists(path):
        for rec in read_jsonl(path):
            k = rec.get(key)
            if k is not None:
                existing[str(k)] = rec

    inserted = 0
    updated = 0
    for rec in new_records:
        k = rec.get(key)
        if k is None:
            raise ValueError(f"upsert_records: record missing required key '{key}': {rec!r}")
        k = str(k)
        if k in existing:
            if existing[k] != dict(rec):
                existing[k] = dict(rec)
                updated += 1
        else:
            existing[k] = dict(rec)
            inserted += 1

    merged = list(existing.values())

    # Skip the rewrite if the merged content equals what's already on disk.
    if os.path.exists(path):
        on_disk = read_jsonl(path)
        if _canonical_equal(on_disk, merged, key=key):
            return {"inserted": 0, "updated": 0, "total": len(on_disk)}

    write_jsonl(path, merged)
    return {"inserted": inserted, "updated": updated, "total": len(merged)}


def _canonical_equal(a: list[dict], b: list[dict], *, key: str) -> bool:
    """Compare two lists of dicts by key for semantic equality (order-insensitive)."""
    if len(a) != len(b):
        return False
    a_map = {str(r.get(key)): r for r in a if r.get(key) is not None}
    b_map = {str(r.get(key)): r for r in b if r.get(key) is not None}
    return a_map == b_map
