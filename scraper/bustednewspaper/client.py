"""Polite HTTP client for Busted Newspaper public pages.

Note (2026-07): Busted Newspaper currently fails TLS handshakes in this
environment (OpenSSL / remote SSL stack mismatch). Scrapes are expected to
fail fast with :class:`BustedNewspaperUnavailable` until that is resolved —
do not burn retries on SSL errors.
"""
from __future__ import annotations

import time
from typing import Optional, Tuple

import requests

from ..config import DEFAULT_DELAY, MAX_RETRIES, REQUEST_TIMEOUT, USER_AGENT
from .client_outage import (
    BN_OUTAGE_MSG,
    BN_SSL_OUTAGE_MSG,
    BustedNewspaperUnavailable,
    is_hard_outage,
    is_transient,
)

# Transient (non-SSL) retries only. SSL is treated as a hard outage.
_BN_MAX_RETRIES = max(3, int(MAX_RETRIES))
_BN_TIMEOUT: Tuple[float, float] = (12.0, float(max(30, int(REQUEST_TIMEOUT))))

_BN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class BustedNewspaperClient:
    """Retrying client. SSL failures raise :class:`BustedNewspaperUnavailable` immediately."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.delay = max(0.0, float(delay))
        self.session = session or requests.Session()
        self._apply_headers()
        self._last_request_at: Optional[float] = None

    def _apply_headers(self) -> None:
        self.session.headers.clear()
        self.session.headers.update(
            {
                "User-Agent": _BN_USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        self.session.headers.setdefault("X-Research-Client", USER_AGENT[:80])

    def _reset_session(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass
        self.session = requests.Session()
        self._apply_headers()
        self._last_request_at = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.delay - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def get(self, url: str, *, referer: Optional[str] = None) -> str:
        return self._request(url, referer=referer).text

    def get_bytes(self, url: str, *, referer: Optional[str] = None, max_bytes: int = 15_000_000) -> bytes:
        data = self._request(url, referer=referer).content
        if len(data) > max_bytes:
            raise ValueError(f"Body too large: {len(data)} bytes")
        return data

    @staticmethod
    def _is_hard_outage(exc: BaseException) -> bool:
        return is_hard_outage(exc)

    # Back-compat name used in earlier drafts / tests.
    _is_ssl_failure = _is_hard_outage

    @staticmethod
    def _is_transient(exc: BaseException) -> bool:
        return is_transient(exc)

    def _request(self, url: str, *, referer: Optional[str] = None) -> requests.Response:
        last_error: Optional[BaseException] = None
        headers = {"Referer": referer or "https://bustednewspaper.com/"}

        for attempt in range(_BN_MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(
                    url,
                    timeout=_BN_TIMEOUT,
                    headers=headers,
                    allow_redirects=True,
                )
                self._last_request_at = time.monotonic()
                if response.status_code in (408, 425, 429, 500, 502, 503, 504):
                    last_error = requests.HTTPError(
                        f"{response.status_code} for {url}", response=response
                    )
                    if attempt + 1 >= _BN_MAX_RETRIES:
                        response.raise_for_status()
                    pause = self.delay * (2 ** min(attempt, 3))
                    if response.status_code == 429:
                        pause = max(pause, 5.0)
                    time.sleep(min(20.0, pause))
                    self._reset_session()
                    continue
                response.raise_for_status()
                raw = response.content[:4]
                if raw.startswith(b"\xef\xbb\xbf") or raw.lstrip().startswith(b"<?xml"):
                    response.encoding = "utf-8"
                return response
            except requests.RequestException as exc:
                last_error = exc
                if self._is_hard_outage(exc):
                    raise BustedNewspaperUnavailable(BN_OUTAGE_MSG) from exc
                if (
                    isinstance(exc, requests.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code
                    not in (408, 425, 429, 500, 502, 503, 504)
                ):
                    raise
                if attempt + 1 >= _BN_MAX_RETRIES or not self._is_transient(exc):
                    raise
                pause = self.delay * (1.5 ** attempt) + 0.5
                time.sleep(min(15.0, max(self.delay, pause)))
                self._reset_session()
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Busted Newspaper request failed for {url}")  # pragma: no cover

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "BustedNewspaperClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# Re-export for importers that used client-level names
__all__ = [
    "BustedNewspaperClient",
    "BustedNewspaperUnavailable",
    "BN_OUTAGE_MSG",
    "BN_SSL_OUTAGE_MSG",
]
