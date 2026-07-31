# Deployment Guide

This document walks through deploying InvestorLens to GitHub so the daily and weekly
pipelines actually run on a schedule.

**Time required**: ~15 minutes if you already have a GitHub account.

---

## Prerequisites

1. A GitHub account (free tier is sufficient).
2. The InvestorLens repo on your local machine (you're reading this from it).
3. `git` installed locally.

You do **NOT** need:
- A paid GitHub plan (free public repos get unlimited Actions minutes; private repos
  get 2000 min/month free, which is plenty for our usage).
- Any API keys (NSE, BSE, RBI, MOSPI, Yahoo all have free, no-auth endpoints).
- Any paid infrastructure.

---

## Step 1: Create a GitHub repository

1. Go to https://github.com/new.
2. **Repository name**: `investorlens` (or any name you prefer).
3. **Description**: `Data → Knowledge Graph → Value Chain → Impact Algorithms — Indian listed companies research infrastructure`.
4. **Visibility**:
   - **Public** (recommended): free unlimited Actions minutes, anyone can see the data.
   - **Private**: 2000 free min/month (our daily pipeline uses ~5–10 min/day, so this is plenty).
5. **DO NOT** initialize with README / .gitignore / license — your local repo already has these.
6. Click **Create repository**.

GitHub will show you a page with commands like:
```
git remote add origin https://github.com/YOUR_USERNAME/investorlens.git
git branch -M main
git push -u origin main
```

Copy these — you'll use them in Step 3.

---

## Step 2: Verify your local repo is ready

From your local InvestorLens directory:

```bash
. .venv/bin/activate
pytest -q                          # should be 339+ tests passing
python scripts/validate_workflows.py
python scripts/validate_outputs.py
```

All three should exit cleanly. If any fail, fix before pushing — CI will fail on the
same issues.

---

## Step 3: Push to GitHub

From your local repo:

```bash
# Replace YOUR_USERNAME with your actual GitHub username.
git remote add origin https://github.com/YOUR_USERNAME/investorlens.git
git branch -M main
git push -u origin main
```

If you're using SSH instead of HTTPS:
```bash
git remote add origin git@github.com:YOUR_USERNAME/investorlens.git
git push -u origin main
```

Verify on GitHub: refresh the repo page, you should see all the files (src/, scripts/,
docs/, tests/, .github/workflows/, etc.).

---

## Step 4: Enable GitHub Actions

GitHub usually enables Actions automatically for new repos, but verify:

1. Go to your repo on GitHub → **Settings** → **Actions** → **General**.
2. Under **Actions permissions**, select **Allow all actions and reusable workflows**.
3. Under **Workflow permissions**, ensure **Read and write permissions** is selected
   (the daily pipeline needs to commit data back to the repo).
4. Check the box **Allow GitHub Actions to create and approve pull requests** (not strictly
   required, but useful for future automation).
5. Click **Save**.

---

## Step 5: Verify CI workflow runs

The `ci.yml` workflow runs on every push. It should have triggered automatically when
you pushed in Step 3.

1. Go to your repo → **Actions** tab.
2. You should see a workflow run named **CI** with a green ✓ (or in progress).
3. Click into it to see the individual steps: YAML validation, pytest, validate_outputs,
   smoke_test_e2e, summary.
4. If any step fails, click it to see the logs. Common causes:
   - Missing dependency: ensure `pyproject.toml` is up to date and committed.
   - Test failure: run `pytest -q` locally to reproduce.

CI must be green before continuing.

---

## Step 6: Trigger the daily pipeline manually

The daily pipeline (`daily.yml`) is scheduled to run at 13:00 UTC (18:30 IST) Mon–Sat.
But you can trigger it manually to verify it works end-to-end:

1. Go to **Actions** → **Daily Pipeline** (left sidebar).
2. Click **Run workflow** (top right).
3. (Optional) Customize inputs:
   - `symbols`: comma-separated NSE symbols (default: `RELIANCE,TCS,INFY,SUNPHARMA,HDFCBANK`).
   - `skip_macro`: check this to skip RBI/MOSPI fetches for a faster smoke test.
4. Click **Run workflow**.
5. Click the new run that appears to watch it in real time.

Expected runtime: 5–15 minutes depending on whether this is the first run (no cache)
or a subsequent run (cache hits speed things up).

When complete, the run should:
- Show a green ✓.
- Have committed data files back to the repo (check the commit history).
- Have a **Summary** tab with the pipeline summary (file counts, observation kinds,
  sources, etc.).

---

## Step 7: Verify the daily commit

After the daily pipeline completes:

1. Go to your repo's main page.
2. Look at the commit history — you should see a commit like:
   ```
   data: daily pipeline 2026-07-31

   - isin_master: 1500 rows
   - observations: 25000 rows
   - corporate_actions: 200 rows
   ```
   (The actual row counts will be much larger than the seeded test data because the
   live pipeline fetches ALL NSE equities, not just the 5 in the test fixtures.)
3. Click the commit to see the diff — `data/master/*.jsonl` and
   `data/processed/*.jsonl` should be updated.

If the commit didn't happen but the workflow succeeded, check the "Commit changes"
step logs — it logs "No changes to commit." if the data was identical to what's
already in the repo (rare on the first run, common on subsequent runs of the same day).

---

## Step 8: Verify the weekly backfill

The weekly backfill (`weekly.yml`) runs every Sunday at 02:00 UTC (07:30 IST). It
fetches a 5-year history for the tracked symbols and re-builds the adjusted prices.

To trigger manually:
1. Go to **Actions** → **Weekly Backfill**.
2. Click **Run workflow**.
3. (Optional) Pick a different backfill period (1y / 2y / 5y / 10y / max).
4. Click **Run workflow**.

Expected runtime: 15–45 minutes (Yahoo rate-limits us to 0.5 req/s for backfills).

---

## Step 9: Handle failures

If a pipeline run fails:

1. Go to **Actions** → click the failed run.
2. The **Open GitHub Issue on failure** step (if it ran) will have created an issue
   in your repo with the failure context.
3. Click the failed step to see its logs.
4. Common failures and fixes:
   - **NSE/BSE/Yahoo/RBI returns 403 or 429**: transient rate limiting. Click
     **Re-run failed jobs** in the Actions UI. If it persists, the source may have
     changed their CDN/WAF rules — investigate `data/raw/<source>/` for the actual
     response body.
   - **Parser produced 0 observations**: the source's HTML/CSV format changed.
     Download the raw file from `data/raw/`, inspect it, and update the parser
     in `src/investorlens/parsers/`.
   - **Test failure**: a regression. Run `pytest -q` locally to reproduce, fix, push.

When the pipeline is green again, **close the issue** manually (the script doesn't
auto-close — that's intentional, you should verify the fix).

---

## Step 10: Monitor ongoing runs

Useful pages to bookmark:

- **Actions tab**: https://github.com/YOUR_USERNAME/investorlens/actions
- **Daily Pipeline runs**: filter by workflow name in the left sidebar.
- **Issues**: https://github.com/YOUR_USERNAME/investorlens/issues (failure issues
  are labeled `pipeline-failure` if the label exists; otherwise they have no label).

For long-term monitoring, consider:
- **GitHub Actions usage page** (Settings → Billing → Actions): shows minute usage.
  A typical daily run is 5–10 min; weekly is 15–45 min. Monthly total: ~200–400 min
  for daily + ~60–180 min for weekly = well within free tier.
- **A GitHub Action that pings you on failure** via email/Slack: the existing
  `gh_create_issue_on_failure.py` opens an issue, which GitHub emails you about by
  default (if you've enabled notifications for the repo).

---

## Optional: Customizing the tracked symbols

The default symbol list is `RELIANCE,TCS,INFY,SUNPHARMA,HDFCBANK`. To track more:

1. Edit `.github/workflows/daily.yml` and `.github/workflows/weekly.yml`.
2. Find the `SYMBOLS:` env var (in the daily job) and the `--symbols` argument
   (in the fetch_hist_prices step).
3. Replace with your list, e.g. `RELIANCE,TCS,INFY,SUNPHARMA,HDFCBANK,WIPRO,ITC,SBIN`.
4. Commit and push. The next scheduled run (or manual trigger) will use the new list.

**Note**: every additional symbol adds ~2 seconds to the daily run (Yahoo rate limit).
100 symbols ≈ 3 minutes; 1000 symbols ≈ 30 minutes. The free tier is 2000 min/month,
so 100 symbols is comfortable; 1000 symbols is borderline.

---

## Optional: Disabling scheduled runs during development

If you want to pause the daily/weekly runs (e.g. during a major refactor):

1. Edit `.github/workflows/daily.yml` and `.github/workflows/weekly.yml`.
2. Comment out the `on.schedule` block (lines starting with `schedule:` and `cron:`).
3. Leave `workflow_dispatch:` so you can still trigger manually.
4. Commit and push.

The pipelines will no longer run on schedule but can still be triggered manually
via the Actions UI. Remember to uncomment when you're done.

---

## What's next?

Once the daily pipeline is running cleanly for a few days:

1. **Phase 1 is complete**. The data infrastructure is production-ready.
2. Move to **Phase 2** (Knowledge Base & Canvas): company Markdown notes, sector
   canvases, the large-scale React web graph. See `docs/ROADMAP.md`.
3. Phase 2 builds ON TOP of the data you're now collecting — it doesn't replace it.

If you hit any issues not covered here, check:
- `worklog.md` for the full session-by-session history.
- `docs/ARCHITECTURE.md` for the layered design.
- `docs/ROADMAP.md` for what's planned next.
- The issue tracker on GitHub for known problems.
