"""
Initialize the InvestorLens workspace.

Creates the data/ subdirectories if they don't exist and writes empty
master files so that fetchers can upsert into them safely.

Idempotent: running this multiple times is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable when running the script directly (without pip install).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import ensure_dir, write_jsonl  # noqa: E402

DATA_DIR = ROOT / "data"
MASTER_FILES = [
    "master/isin_master.jsonl",
    "master/companies.jsonl",
    "master/sectors.jsonl",
    "master/sources.jsonl",
    "processed/observations.jsonl",
    "processed/corporate_actions.jsonl",
]
SUBDIRS = [
    "raw/nse/bhavcopy",
    "raw/bse/bhavcopy",
    "raw/rbi",
    "raw/mospi",
    "raw/company_ar",
    "raw/company_drhp",
    "master",
    "processed",
    "provenance/runs",
]


def main() -> int:
    print(f"[init] project root: {ROOT}")
    print(f"[init] data dir:    {DATA_DIR}")

    for sub in SUBDIRS:
        ensure_dir(DATA_DIR / sub)
        print(f"[init]   ensured dir: data/{sub}")

    for rel in MASTER_FILES:
        path = DATA_DIR / rel
        if not path.exists():
            write_jsonl(path, [])
            print(f"[init]   created empty file: data/{rel}")
        else:
            print(f"[init]   exists, skipped:    data/{rel}")

    print("[init] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
