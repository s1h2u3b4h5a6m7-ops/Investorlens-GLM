# GitHub Actions Setup Guide

This guide walks you through deploying InvestorLens to GitHub so the daily
and weekly pipelines run automatically.

**Time required**: ~15 minutes (one-time setup).

---

## Prerequisites

- A GitHub account (free).
- This repo checked out locally.
- ~50 MB of free disk for the `.git/` history.

---

## Step 1 — Create the GitHub repository

1. Go to https://github.com/new.
2. **Repository name**: `investorlens` (or your preferred name).
3. **Description**: `Data → Knowledge Graph → Value Chain → Impact Algorithms — Indian listed companies research infrastructure.`
4. **Visibility**:
   - **Public** (recommended): free unlimited GitHub Actions minutes; the data is already public (NSE/BSE/RBI/MOSPI publish it).
   - **Private**: 2,000 free Actions minutes/month. The pipeline uses ~1,020 min/month (well within the limit), but you may hit the cap if you add more fetchers.
5. **Initialize**: leave "Add a README" / "Add .gitignore" / "Choose a license" **unchecked** — the repo already has all of these.
6. Click **Create repository**.

---

## Step 2 — Connect your local repo to GitHub

After creating the repo, GitHub shows you the remote URL. Use the SSH or HTTPS
URL depending on your setup:

```bash
cd /path/to/investorlens

# Add the remote (replace <USER> and <REPO> with your values)
git remote add origin git@github.com:<USER>/<REPO>.git
# or, using HTTPS:
# git remote add origin https://github.com/<USER>/<REPO>.git

# Verify
git remote -v
# origin  git@github.com:<USER>/<REPO>.git (fetch)
# origin  git@github.com:<USER>/<REPO>.git (push)

# Push the existing history
git push -u origin main
```

---

## Step 3 — Verify the workflows are detected

1. Go to your repo on GitHub: `https://github.com/<USER>/<REPO>`.
2. Click the **Actions** tab.
3. You should see two workflows listed on the left:
   - **Daily Pipeline**
   - **Weekly Backfill**

If you don't see them, check that `.github/workflows/daily.yml` and
`.github/workflows/weekly.yml` are committed and pushed.

---

## Step 4 — Trigger a manual run (smoke test)

Before relying on the schedule, trigger a manual run to verify everything works:

1. In the **Actions** tab, click **Daily Pipeline**.
2. Click the **Run workflow** dropdown (top-right).
3. (Optional) Customize:
   - **symbols**: e.g. `RELIANCE,TCS` (defaults to 5 large-caps).
   - **skip_macro**: check this for a faster first run (skips RBI/MOSPI).
4. Click the green **Run workflow** button.
5. Click the run that appears in the list to watch it execute.

The run has two jobs:
- **smoke** (~3-5 min): fast check that the repo installs and unit tests pass.
- **daily** (~15-25 min): the full pipeline — fetchers, builders, validation, commit.

If `smoke` fails, `daily` is skipped. If `daily` fails, a GitHub issue is
automatically created with the failure context.

---

## Step 5 — Verify the commit

After the `daily` job completes:

1. Go to your repo's **commits** page: `https://github.com/<USER>/<REPO>/commits/main`.
2. You should see a commit by `github-actions[bot]` titled something like:
   ```
   data: daily pipeline 2024-10-15

   - isin_master: 15 rows
   - observations: 186 rows
   - corporate_actions: 8 rows
   ```
3. Click the commit to see the diff — it should show updates to
   `data/master/*.jsonl` and `data/processed/*.jsonl`.

If you see no commit, the workflow may have run but produced no changes
(e.g. all sources were cached, no new data). Check the workflow run's
**Summary** tab — it shows file counts, observation-kind breakdown, and
latest retrieval timestamps.

---

## Step 6 — Verify the scheduled runs

The daily workflow runs at 13:00 UTC = 18:30 IST, Monday through Saturday.
The weekly workflow runs at 02:00 UTC Sundays = 07:30 IST Sundays.

To confirm scheduled runs are working:
1. Wait until the next scheduled time (or trigger a manual run as in Step 4).
2. Check the **Actions** tab for new runs.
3. If no scheduled runs appear after 24 hours, see **Troubleshooting** below.

**Important**: GitHub Actions scheduled workflows can be disabled
automatically if the repo has had no activity for 60 days. To prevent this:
- Star the repo (creates activity).
- Or push any commit (even a README tweak) every few weeks.
- Or set `keepalive-workflow` (a third-party action) to ping the repo.

---

## Step 7 — Configure issue notifications (optional but recommended)

When the pipeline fails, an issue is automatically created with the
`pipeline-failure` label (if the label exists). To get notified:

1. Go to your repo's **Watch** dropdown (top-right of the repo page).
2. Select **Custom** → **Issues** → **Apply**.
3. (Optional) Create the `pipeline-failure` label in advance:
   - Go to **Issues** → **Labels** → **New label**.
   - Name: `pipeline-failure`, Color: `d73a4a` (red), Description: `Automated pipeline failure`.

If the `pipeline-failure` label doesn't exist, the issue is still created —
just without the label.

---

## Step 8 — Customize the symbol list (optional)

The default tracked symbols are 5 large-caps: `RELIANCE,TCS,INFY,SUNPHARMA,HDFCBANK`.

To track more symbols, you have two options:

### Option A — One-off override (per run)

Use the `workflow_dispatch` input when triggering a manual run. This doesn't
affect scheduled runs.

### Option B — Permanent change (affects scheduled runs)

Edit `.github/workflows/daily.yml` and `.github/workflows/weekly.yml`,
find the line:

```yaml
SYMBOLS: ${{ github.event.inputs.symbols || 'RELIANCE,TCS,INFY,SUNPHARMA,HDFCBANK' }}
```

Replace the default string with your preferred list. Commit and push.

**Note**: Each additional symbol adds ~1-2 seconds to the Yahoo fetch step
(rate-limited at 1 req/s). 50 symbols ≈ 1 minute extra. The 30-minute job
timeout is plenty.

---

## Troubleshooting

### The scheduled workflow didn't run

1. Check the **Actions** tab for any error indicators.
2. Verify the cron syntax in `.github/workflows/daily.yml`:
   ```yaml
   on:
     schedule:
       - cron: "0 13 * * 1-6"  # 13:00 UTC Mon–Sat
   ```
3. GitHub Actions scheduled workflows can have a ~15-minute delay during
   peak load. Wait until 13:30 UTC before concluding it didn't run.
4. If the repo has had no commits/activity for 60 days, GitHub may have
   disabled scheduled workflows. Push any commit to re-enable.

### The `smoke` job fails

This usually means a unit test broke or the package can't install. Check
the smoke job's logs. Common causes:
- A recent commit broke a test (run `pytest -q` locally to reproduce).
- A new dependency was added to `pyproject.toml` but not committed.

### A fetcher fails (but the pipeline continues)

This is **expected** behavior. Each fetcher uses `|| true` so a single
source being down doesn't block the others. Check the daily job's logs
to see which fetcher failed. Common causes:
- NSE/BSE/RBI rate-limiting (the fetcher retries 3 times with backoff;
  if all fail, the run continues with cached data).
- A source changed its HTML/CSV format (the parser may need updating).
- Network glitch (re-run the workflow manually).

### No commit was made

Possible causes:
- All sources were cached and no new data was fetched (re-running on the
  same day with the same cache is a no-op).
- The fetchers all failed (check logs).
- The commit step's `git diff --cached --quiet` returned true (no changes).

### The issue-creation step fails

The `gh_create_issue_on_failure.py` script needs `issues: write` permission,
which is set in the workflow's `permissions:` block. If it still fails:
- Verify the `GITHUB_TOKEN` secret is available (it's automatic on GitHub
  Actions; you don't need to create it).
- Check that the repo allows issue creation (Settings → Features → Issues).

### The `pip install -e ".[dev]"` step is slow

This happens on the first run (no cache). Subsequent runs reuse the pip
wheel cache (`~/.cache/pip`), keyed on `pyproject.toml`'s hash. If you
change dependencies, the cache is invalidated and the install runs fresh.

---

## Cost analysis

| Workflow | Frequency      | Run time (avg) | Monthly minutes |
|----------|----------------|-----------------|-----------------|
| Daily    | Mon–Sat (×26)  | ~20 min         | ~520            |
| Weekly   | Sundays (×4)   | ~40 min         | ~160            |
| **Total**|                 |                 | **~680**        |

For **public repos**: GitHub Actions is free and unlimited. No cost.

For **private repos**: Free tier is 2,000 minutes/month. The pipeline uses
~680 minutes — comfortably within the limit, leaving ~1,320 minutes for
other CI work (tests, etc.).

If you exceed the free tier, GitHub Actions just pauses until the next
month — it doesn't charge you unexpectedly.

---

## What gets committed vs. what stays in the cache

| Path                              | Committed? | Why                                                        |
|-----------------------------------|------------|------------------------------------------------------------|
| `data/master/*.jsonl`             | **Yes**    | Small, canonical, useful for offline analysis.             |
| `data/processed/*.jsonl`          | **Yes**    | Small, canonical, the actual research data.                |
| `data/raw/**/*.zip`               | No         | Large, re-fetchable, in `.gitignore`.                      |
| `data/raw/**/*.csv`               | No         | Same.                                                      |
| `data/raw/**/*.html`              | No         | Same.                                                      |
| `data/raw/**/*.pdf`               | No         | Same.                                                      |
| `data/raw/**/*.xlsx`              | No         | Same.                                                      |

The raw downloads are cached at the GitHub Actions layer (`actions/cache@v4`
with the `data/raw` path), so re-runs on the same day are free. Different
days re-fetch.

---

## Disabling the pipeline

To temporarily disable scheduled runs (e.g. for maintenance):

1. Go to **Actions** → **Daily Pipeline**.
2. Click the **...** menu (top-right) → **Disable workflow**.
3. Re-enable with the same menu when ready.

Alternatively, comment out the `on.schedule:` block in the YAML file and
commit. The workflow can still be triggered manually via `workflow_dispatch`.

---

## Next steps

Once the daily pipeline is running green for a few days:
- **Phase 1 is complete.** Move to Phase 2 (Knowledge Base + Canvas).
- The data in `data/processed/observations.jsonl` is now continuously
  updating — Phase 2 can build the company Markdown notes and Dataview
  dashboards on top of it.
- The macro observations in the same file (`drv_*` subject_ids) are ready
  for Phase 3 (value-chain research) and Phase 4 (impact algorithms).
