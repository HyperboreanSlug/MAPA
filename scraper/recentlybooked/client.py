"""Polite HTTP client for RecentlyBooked public pages."""

from __future__ import annotations

import threading
import time
from typing import Optional

import requests

from ..config import DEFAULT_DELAY, MAX_RETRIES, REQUEST_TIMEOUT, USER_AGENT


class RecentlyBookedClient:
    """Spaces this client's requests by at least ``delay`` seconds (per-thread)."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.delay = max(0.0, delay)
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._last_request_at: Optional[float] = None
        self._pace_lock = threading.Lock()

    def _wait_for_rate_limit(self) -> None:
        with self._pace_lock:
            now = time.monotonic()
            last = self._last_request_at
            delay = self.delay
            if last is not None:
                remaining = delay - (now - last)
                if remaining > 0:
                    time.sleep(remaining)
            self._last_request_at = time.monotonic()

    def get(self, url: str) -> str:
        """Fetch *url* and return decoded response text, retrying transient failures."""
        return self._request(url).text

    def get_bytes(self, url: str, *, max_bytes: int = 15_000_000) -> bytes:
        """Fetch bytes. Stop large bodies to avoid memory spikes."""
        data = self._request(url).content
        if len(data) > max_bytes:
            raise ValueError(f"Body too large: {len(data)} bytes")
        return data

    def _request(self, url: str) -> requests.Response:
        """Fetch *url* and return the response after rate limiting and retries."""
        last_error: Optional[requests.RequestException] = None
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                # Prefer UTF-8 when the body starts with a UTF-8 BOM or XML decl.
                raw = response.content[:4]
                if raw.startswith(b"\xef\xbb\xbf") or raw.lstrip().startswith(b"<?xml"):
                    response.encoding = "utf-8"
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 == MAX_RETRIES:
                    raise
                time.sleep(self.delay * (attempt + 1))
        raise last_error  # pragma: no cover

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self.session.close()

    def __enter__(self) -> "RecentlyBookedClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
