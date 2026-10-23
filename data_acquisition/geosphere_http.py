"""Shared GeoSphere HTTP client with header-driven rate limiting and retries."""

from __future__ import annotations

import math
import time

import requests


class RateLimiter:
    """Pace sequential requests using the server's remaining quota and reset delay."""

    def __init__(self):
        self.next_request_at = 0.0

    def wait(self):
        delay = self.next_request_at - time.monotonic()
        if delay > 0:
            if delay >= 1:
                print(f"    API rate limit, waiting {delay:.1f}s ...")
            time.sleep(delay)

    def update(self, response: requests.Response):
        def number(name):
            try:
                value = float(response.headers[name])
            except (KeyError, TypeError, ValueError):
                return None
            return value if math.isfinite(value) and value >= 0 else None

        limit = number("x-ratelimit-limit-second")
        delay = 1 / limit + 0.01 if limit else 0.3
        remaining_second = number("x-ratelimit-remaining-second")
        if remaining_second == 0:
            delay = max(delay, 1.01)
        if number("x-ratelimit-remaining-hour") == 0 or (response.status_code == 429 and remaining_second != 0):
            reset = number("ratelimit-reset")
            delay = max(delay, (reset if reset is not None else 60) + 2)
        self.next_request_at = max(self.next_request_at, time.monotonic() + delay)


class GeoSphereClient:
    """Reuse one session and rate limiter across a builder's station and grid requests."""

    def __init__(self, *, retries: int = 10):
        self.retries = retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "foehn-dataset-builder (research)"
        self.rate_limiter = RateLimiter()

    def get(self, url: str, params: dict, *, retries: int | None = None) -> requests.Response:
        """GET with header-driven pacing, quota waits, and HTTP/network retries."""
        if retries is None:
            retries = self.retries
        for attempt in range(retries):
            self.rate_limiter.wait()
            try:
                r = self.session.get(url, params=params, timeout=300)
            except requests.RequestException as exc:
                wait = 10 * (attempt + 1)
                print(f"    network error ({exc.__class__.__name__}), retry in {wait}s")
                time.sleep(wait)
                continue
            self.rate_limiter.update(r)
            if r.status_code == 429:
                continue
            if r.status_code >= 500:
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code} for {r.url[:300]}\n{r.text[:500]}")
            return r
        raise RuntimeError(f"giving up on {url}")
