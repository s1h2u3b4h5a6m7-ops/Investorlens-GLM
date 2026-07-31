"""
Fetch RBI Policy Rates (Repo, SDF, MSF, Bank Rate, CRR, SLR, Reverse Repo).

Source: https://rbi.org.in/Scripts/BS_ViewPolicyRates.aspx (HTML table)

Output:
  - Raw HTML cached to: data/raw/rbi/policy_rates/<YYYY-MM-DD>.html
  - Parsed Observations upserted to: data/processed/observations.jsonl

Each rate becomes a single Observation with kind=POLICY_RATE. The subject_id
is a `drv_*` ID (macro driver) which Phase 3 will formalize as a MacroDriver.

Idempotent: re-running on the same date reads from cache, upserts with no
duplicates.

Usage:
    python scripts/fetchers/fetch_rbi_rates.py
    python scripts/fetchers/fetch_rbi_rates.py --date 2024-10-09
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from investorlens.io import CachedSession, FetchError, upsert_records  # noqa: E402
from investorlens.parsers import rbi  # noqa: E402

log = logging.getLogger("fetch_rbi_rates")

URL = "https://rbi.org.in/Scripts/BS_ViewPolicyRates.aspx"
OUTPUT_PATH = ROOT / "data" / "processed" / "observations.jsonl"
RAW_DIR = ROOT / "data" / "raw" / "rbi" / "policy_rates"


def fetch(date_str: str | None = None) -> int:
    """Fetch and parse RBI policy rates, upserting to observations.jsonl."""
    retrieved_at = datetime.now(timezone.utc)
    date_str = date_str or retrieved_at.strftime("%Y-%m-%d")
    raw_path = RAW_DIR / f"{date_str}.html"

    html_text: str | None = None
    if raw_path.exists():
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Reading cached HTML: %s", rel)
        html_text = raw_path.read_text(encoding="utf-8", errors="replace")
    else:
        log.info("Fetching RBI policy rates from %s", URL)
        try:
            with CachedSession(
                source_slug="rbi",
                rate_limit_per_sec=1.0,
                max_retries=3,
            ) as session:
                body = session.get(URL, date_str=date_str)
                html_text = body.decode("utf-8", errors="replace")
        except FetchError as e:
            log.error("Fetch failed: %s", e)
            return 1

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = raw_path.with_suffix(".html.tmp")
        tmp.write_text(html_text, encoding="utf-8")
        tmp.replace(raw_path)
        try:
            rel = str(raw_path.relative_to(ROOT))
        except ValueError:
            rel = str(raw_path)
        log.info("Cached HTML to %s", rel)

    log.info("Parsing %d bytes of HTML", len(html_text))
    observations = rbi.parse_policy_rates_html(
        html_text,
        retrieved_at=retrieved_at,
        source_url=URL,
        as_of=datetime.strptime(date_str, "%Y-%m-%d").date(),
    )
    log.info("Parsed %d policy-rate observations", len(observations))

    if not observations:
        log.warning("Parser produced 0 observations — possibly HTML structure changed.")
        return 1

    payload = [o.model_dump(mode="json", exclude_none=True) for o in observations]
    stats = upsert_records(OUTPUT_PATH, payload, key="id")
    try:
        out_rel = str(OUTPUT_PATH.relative_to(ROOT))
    except ValueError:
        out_rel = str(OUTPUT_PATH)
    log.info(
        "Upserted to %s: inserted=%d updated=%d total=%d",
        out_rel, stats["inserted"], stats["updated"], stats["total"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD for cache keying. Defaults to today.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return fetch(date_str=args.date)


if __name__ == "__main__":
    sys.exit(main())
