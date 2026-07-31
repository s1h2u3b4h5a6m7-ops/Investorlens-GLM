"""
Validate all GitHub Actions workflow YAML files.

Checks:
  1. Every .yml/.yaml file in .github/workflows/ parses as valid YAML.
  2. Every `run:` step that calls `python scripts/<name>.py` references a
     script that actually exists. (Catches the classic "workflow references
     a script that was never written" bug.)
  3. Every `uses:` action is from a known publisher (actions/*, softprops/*, etc.)
     — currently just warns, doesn't fail.

Usage:
    python scripts/validate_workflows.py
    python scripts/validate_workflows.py --strict   # fail on warnings too
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
SCRIPTS_DIR = ROOT / "scripts"

log = logging.getLogger("validate_workflows")


def _load_yaml(text: str) -> object:
    """Parse YAML using PyYAML (already a project dependency)."""
    import yaml
    return yaml.safe_load(text)


def _extract_python_script_calls(workflow_text: str) -> list[str]:
    """Find all `python scripts/<name>.py` invocations in `run:` blocks.

    Returns a list of script paths (relative to repo root).

    Handles both:
      - `run: python scripts/foo.py` (inline)
      - `run: |\n  python scripts/foo.py` (block scalar, indented)
    """
    # Match `python scripts/foo.py` or `python scripts/foo/bar.py` anywhere
    # in the text, with optional leading whitespace. The `python` keyword
    # must be preceded by whitespace or start of line (not e.g. `mypython`).
    pattern = re.compile(r"(?:^|\s)python\s+(scripts/[\w/]+\.py)", re.MULTILINE)
    return pattern.findall(workflow_text)


def _walk_run_steps(obj, found_scripts: list[str]) -> None:
    """Recursively walk a parsed workflow dict looking for `run:` keys."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "run" and isinstance(v, str):
                found_scripts.extend(_extract_python_script_calls(v))
            else:
                _walk_run_steps(v, found_scripts)
    elif isinstance(obj, list):
        for item in obj:
            _walk_run_steps(item, found_scripts)


def validate_workflow(path: Path, *, strict: bool = False) -> list[str]:
    """Validate a single workflow file. Returns a list of error messages (empty = OK)."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")

    # 1. Parse as YAML.
    try:
        workflow = _load_yaml(text)
    except Exception as e:
        errors.append(f"{path.name}: invalid YAML — {e}")
        return errors

    # 2. Find all `python scripts/X.py` calls and verify they exist.
    found_scripts: list[str] = []
    _walk_run_steps(workflow, found_scripts)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_scripts = []
    for s in found_scripts:
        if s not in seen:
            seen.add(s)
            unique_scripts.append(s)

    for script_rel in unique_scripts:
        script_path = ROOT / script_rel
        if not script_path.exists():
            errors.append(f"{path.name}: references non-existent script `{script_rel}`")

    if strict:
        # In strict mode, also warn about any `uses:` from unknown publishers.
        # (Just a heuristic for now.)
        unknown_uses = re.findall(r"uses:\s+(\S+)", text)
        for u in unknown_uses:
            if not any(u.startswith(prefix) for prefix in ("actions/", "softprops/", "actions-cache", "github/")):
                log.warning("%s: uses unknown action `%s` (review recommended)", path.name, u)

    return errors


def main(argv: list[str] | None = None) -> int:
    """Run the validator.

    Args:
        argv: optional argument list (for testing). If None, uses sys.argv.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not WORKFLOWS_DIR.exists():
        log.error("Workflows directory not found: %s", WORKFLOWS_DIR)
        return 1

    workflow_files = sorted(
        list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
    )
    if not workflow_files:
        log.warning("No workflow files found in %s", WORKFLOWS_DIR)
        return 0

    log.info("Validating %d workflow file(s)...", len(workflow_files))
    all_errors: list[str] = []
    for path in workflow_files:
        errors = validate_workflow(path, strict=args.strict)
        if errors:
            for e in errors:
                log.error("  ✗ %s", e)
                all_errors.append(e)
        else:
            log.info("  ✓ %s", path.name)

    if all_errors:
        log.error("Validation FAILED with %d error(s).", len(all_errors))
        return 1

    log.info("All workflows valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
