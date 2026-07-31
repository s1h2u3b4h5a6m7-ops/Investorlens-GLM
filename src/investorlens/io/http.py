"""
Rate-limited, cached HTTP session for InvestorLens fetchers.

Design goals:
  - Polite: respects a per-source rate limit (default ≤ 3 req/s).
  - Cached: every successful response is saved to data/raw/<source>/<date>/<slug>
    so re-running on the same date doesn't re-hit the network.
  - Retried: transient HTTP errors (429, 5xx) are retried with exponential backoff.
  - Browser-like: many Indian sources (NSE in particular) reject requests
    without a realistic User-Agent and Accept-Language. We set sensible defaults.
  - Fail-safe: a fetcher that can't reach the network returns a clear error;
    it never silently produces fabricated data (Principle 4).

Usage:
    from investorlens.io.http import CachedSession

    s = CachedSession(source_slug="nse", rate_limit_per_sec=2.0)
    text = s.get_text("https://nseindia.com/api/equity-stock")
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# Import ensure_dir directly from the canonical definition to avoid a circular
# import with investorlens.io.__init__ (which imports this module).
# ensure_dir is defined inline in __init__.py; we re-define a tiny helper here
# to break the cycle. The behavior is identical.


def _ensure_dir(path: "Path") -> "Path":
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

__all__ = ["CachedSession", "FetchError"]

log = logging.getLogger(__name__)

# Default browser-like headers. NSE/BSE reject non-browser UA with 403.
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# Project data root — kept in sync with scripts/init_workspace.py
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"


class FetchError(RuntimeError):
    """Raised when a fetch cannot be completed after retries."""


class CachedSession:
    """A requests.Session wrapper that adds rate-limiting, caching, and retries.

    Caching strategy:
      - First call on a given date → HTTP GET, save body to disk, return body.
      - Subsequent calls on the same date for the same URL → read from disk, no HTTP.
      - Cache key: hash of the URL + query string. Same URL → same cache file.

    The cache is per-date so that re-runs on the same day are free, but a fresh
    run tomorrow re-fetches. This matches the daily-pipeline use case.
    """

    def __init__(
        self,
        source_slug: str,
        *,
        rate_limit_per_sec: float = 2.0,
        max_retries: int = 3,
        backoff_base: float = 1.5,
        cache_root: Path | None = None,
        timeout: float = 30.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.source_slug = source_slug
        self.rate_limit_per_sec = max(0.1, rate_limit_per_sec)
        self.min_interval = 1.0 / self.rate_limit_per_sec
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self.cache_root = cache_root or (_DATA_ROOT / source_slug)
        self._session = requests.Session()
        headers = dict(_DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        self._session.headers.update(headers)
        self._last_request_at: float = 0.0

    # ------------------------------------------------------------------ helpers

    def _throttle(self) -> None:
        """Sleep just long enough to respect the rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _cache_path(self, url: str, *, date_str: str | None = None) -> Path:
        """Return the local cache path for a URL on a given date."""
        import hashlib

        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Hash the full URL (path + query) so different params get different files.
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        # Keep a small human-readable suffix for debuggability.
        parsed = urlparse(url)
        suffix = (parsed.path.rstrip("/").split("/")[-1] or "index")[:40]
        return self.cache_root / date_str / f"{url_hash}_{suffix}"

    def _read_cache(self, path: Path) -> bytes | None:
        if path.exists():
            log.debug("cache hit: %s", path)
            return path.read_bytes()
        return None

    def _write_cache(self, path: Path, body: bytes) -> None:
        _ensure_dir(path.parent)
        # Atomic write — same pattern as write_json.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(path)

    # ------------------------------------------------------------------ public

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        date_str: str | None = None,
    ) -> bytes:
        """GET the URL, returning the raw response body.

        - If `use_cache` and a cached copy exists for today, return it (no HTTP).
        - Otherwise: rate-limit → retry on transient errors → cache → return.
        """
        full_url = requests.Request("GET", url, params=params).prepare().url
        cache_path = self._cache_path(full_url, date_str=date_str)

        if use_cache:
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                last_exc = e
                log.warning("[%s] attempt %d/%d failed: %s", self.source_slug, attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base ** attempt)
                continue

            if resp.status_code == 200:
                self._write_cache(cache_path, resp.content)
                return resp.content

            # 429 Too Many Requests — always retry with backoff.
            # 5xx — retry with backoff.
            # 4xx (other) — don't retry; raise immediately.
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                log.warning(
                    "[%s] attempt %d/%d got HTTP %d, retrying",
                    self.source_slug,
                    attempt,
                    self.max_retries,
                    resp.status_code,
                )
                last_exc = FetchError(f"HTTP {resp.status_code} for {url}")
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base ** attempt)
                continue

            # 4xx (e.g. 403, 404) — not retryable.
            raise FetchError(
                f"HTTP {resp.status_code} for {url}: {resp.text[:300]}"
            ) from last_exc

        raise FetchError(f"All {self.max_retries} attempts failed for {url}: {last_exc}") from last_exc

    def get_text(self, url: str, **kwargs: Any) -> str:
        """Convenience: GET and decode as UTF-8 text."""
        body = self.get(url, **kwargs)
        return body.decode("utf-8", errors="replace")

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "CachedSession":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
