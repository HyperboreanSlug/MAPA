"""Polite HTTP client for mugshots.com public pages."""

from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import requests

from ..config import DEFAULT_DELAY, MAX_RETRIES, REQUEST_TIMEOUT

_TIMEOUT: Tuple[float, float] = (12.0, float(max(45, int(REQUEST_TIMEOUT))))
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class MugshotsComClient:
    """Rate-limited client; ``delay`` is paced per client instance (per-thread)."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.delay = max(0.0, float(delay))
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self._last_request_at: Optional[float] = None
        self._pace_lock = threading.Lock()

    def _wait(self) -> None:
        with self._pace_lock:
            now = time.monotonic()
            last = self._last_request_at
            delay = self.delay
            if last is not None:
                remaining = delay - (now - last)
                if remaining > 0:
                    time.sleep(remaining)
            self._last_request_at = time.monotonic()

    def get(self, url: str, *, referer: Optional[str] = None) -> str:
        return self._request(url, referer=referer).text

    def get_bytes(self, url: str, *, referer: Optional[str] = None, max_bytes: int = 15_000_000) -> bytes:
        data = self._request(url, referer=referer).content
        if len(data) > max_bytes:
            raise ValueError(f"Body too large: {len(data)} bytes")
        return data

    def _request(self, url: str, *, referer: Optional[str] = None) -> requests.Response:
        last_error: Optional[BaseException] = None
        headers = {"Referer": referer or "https://mugshots.com/"}
        retries = max(3, int(MAX_RETRIES))
        for attempt in range(retries):
            self._wait()
            try:
                response = self.session.get(
                    url, timeout=_TIMEOUT, headers=headers, allow_redirects=True
                )
                if response.status_code in (408, 429, 500, 502, 503, 504):
                    last_error = requests.HTTPError(
                        f"{response.status_code} for {url}", response=response
                    )
                    if attempt + 1 >= retries:
                        response.raise_for_status()
                    time.sleep(self.delay * (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= retries:
                    raise
                time.sleep(self.delay * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError(f"mugshots.com request failed: {url}")

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "MugshotsComClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
