"""
Validate all processed outputs against their JSON Schema.

For now this is a stub: it walks data/ and reports file counts and sizes.
Milestone 1.2+ will wire in actual JSON Schema validation using `jsonschema`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def main() -> int:
    if not DATA_DIR.exists():
        print(f"[validate] data dir missing: {DATA_DIR}")
        return 1

    print(f"[validate] scanning {DATA_DIR}")
    total_files = 0
    total_bytes = 0
    by_subdir: dict[str, list[Path]] = {}

    for p in DATA_DIR.rglob("*"):
        if not p.is_file():
            continue
        total_files += 1
        total_bytes += p.stat().st_size
        rel = p.relative_to(DATA_DIR).parent
        by_subdir.setdefault(str(rel), []).append(p)

    print(f"[validate] total files: {total_files}")
    print(f"[validate] total bytes: {total_bytes:,}")
    for sub in sorted(by_subdir):
        print(f"[validate]   data/{sub}/  ({len(by_subdir[sub])} files)")

    # Light sanity check: every JSONL file should be parseable.
    errors = 0
    for p in DATA_DIR.rglob("*.jsonl"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    json.loads(line)
        except json.JSONDecodeError as e:
            errors += 1
            print(f"[validate]   ERROR in {p}:{e.lineno}: {e.msg}")

    # Light sanity check: every JSON file should be parseable.
    for p in DATA_DIR.rglob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors += 1
            print(f"[validate]   ERROR in {p}: {e.msg}")

    if errors:
        print(f"[validate] {errors} parse errors found.")
        return 1

    print("[validate] all files parse cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
