"""
Open a GitHub Issue when the InvestorLens pipeline fails.

Uses the `gh` CLI (pre-installed on GitHub Actions runners) to create an issue
with the failure context: workflow name, run URL, branch, commit, failed step.

This script is invoked from the workflow's `if: failure()` step. It only
runs inside GitHub Actions (detects via $GITHUB_ACTIONS env var); outside
of CI, it prints what it would do and exits 0.

To avoid issue spam, the script first searches for an open issue with the
same title prefix; if found, it adds a comment instead of creating a new
issue.

Usage (from a workflow step):
    if: failure()
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    run: |
      python scripts/gh_create_issue_on_failure.py \
        --workflow "$WORKFLOW_NAME" \
        --failed-step "$FAILED_STEP"
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("gh_create_issue_on_failure")


def _gh(args: list[str], *, check: bool = True) -> str:
    """Run `gh` CLI and return stdout. Raises if check=True and gh fails."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=check)
    return result.stdout.strip()


def _find_existing_issue(title_prefix: str) -> str | None:
    """Return the issue number of an existing open issue with the given title prefix, or None."""
    try:
        out = _gh([
            "issue", "list",
            "--state", "open",
            "--search", f"{title_prefix} in:title",
            "--json", "number,title",
            "--limit", "5",
        ], check=False)
        if not out:
            return None
        import json
        issues = json.loads(out)
        for issue in issues:
            if issue.get("title", "").startswith(title_prefix):
                return str(issue["number"])
    except Exception as e:
        log.warning("Failed to search for existing issues: %s", e)
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the failure-issue script.

    Args:
        argv: optional argument list (for testing). If None, uses sys.argv.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", type=str, default="InvestorLens Pipeline", help="Workflow display name.")
    parser.add_argument("--failed-step", type=str, default="(unknown)", help="Name of the failed step.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done; don't call gh.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Only run inside GitHub Actions unless --dry-run.
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    if not is_ci and not args.dry_run:
        log.info("Not running inside GitHub Actions and --dry-run not set; nothing to do.")
        return 0

    # Gather context from GitHub Actions env vars.
    repo = os.environ.get("GITHUB_REPOSITORY", "unknown/unknown")
    run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
    run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if run_id != "unknown" else "(unknown URL)"
    branch = os.environ.get("GITHUB_REF_NAME", "(unknown branch)")
    commit_sha = os.environ.get("GITHUB_SHA", "(unknown commit)")
    short_sha = commit_sha[:7] if len(commit_sha) >= 7 else commit_sha
    actor = os.environ.get("GITHUB_ACTOR", "(unknown actor)")

    title = f"[Pipeline Failure] {args.workflow}"

    body = f"""## InvestorLens Pipeline Failure

**Workflow:** {args.workflow}
**Failed step:** `{args.failed_step}`
**Branch:** `{branch}`
**Commit:** `{short_sha}`
**Triggered by:** @{actor}

### Run details

- Run URL: {run_url}
- Run ID: `{run_id}`

### Next steps

1. Click the run URL above to see the failed step's logs.
2. Re-run the failed job from the Actions UI if it was a transient error.
3. If the failure persists, investigate the underlying cause (source down,
   schema change, parser bug, etc.).
4. Close this issue once the pipeline is green again.

### Auto-generated

This issue was created automatically by `scripts/gh_create_issue_on_failure.py`.
"""

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Title: {title}")
        print("---")
        print(body)
        return 0

    # Check for an existing open issue with the same title.
    existing_number = _find_existing_issue(title)
    if existing_number:
        log.info("Found existing open issue #%s; adding a comment instead of creating a new issue.", existing_number)
        try:
            _gh(["issue", "comment", existing_number, "--body", body])
            log.info("Commented on issue #%s", existing_number)
        except subprocess.CalledProcessError as e:
            log.error("Failed to comment on issue #%s: %s", existing_number, e)
            return 1
    else:
        log.info("No existing open issue; creating a new one.")
        try:
            out = _gh([
                "issue", "create",
                "--title", title,
                "--body", body,
                "--label", "pipeline-failure",
            ])
            log.info("Created issue: %s", out)
        except subprocess.CalledProcessError as e:
            # The 'pipeline-failure' label may not exist on the repo. Retry without it.
            log.warning("Issue creation with label failed (%s); retrying without label.", e)
            try:
                out = _gh([
                    "issue", "create",
                    "--title", title,
                    "--body", body,
                ])
                log.info("Created issue (no label): %s", out)
            except subprocess.CalledProcessError as e2:
                log.error("Issue creation failed entirely: %s", e2)
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
