"""Live reachability probes for mugshot aggregator hosts."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests

from .registry import MUGSHOT_SOURCES, MugshotSourceInfo, list_mugshot_sources

# Short timeouts — startup probe must not hang the UI thread (runs in worker).
_CONNECT_TIMEOUT = 4.0
_READ_TIMEOUT = 6.0
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _classify_error(exc: BaseException) -> str:
    msg = str(exc).lower()
    name = type(exc).__name__
    if "ssl" in msg or "ssl" in name.lower() or "certificate" in msg:
        return "ssl error"
    if "remotedisconnected" in msg or "connection aborted" in msg:
        return "connection closed"
    if "timed out" in msg or "timeout" in name.lower():
        return "timeout"
    if "403" in msg or "cloudflare" in msg:
        return "blocked (403)"
    if "503" in msg:
        return "unavailable (503)"
    text = str(exc).strip()
    return (text[:48] + "…") if len(text) > 48 else (text or name)


def probe_source(
    source: MugshotSourceInfo,
    *,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Probe one source homepage.

    Returns dict with keys: id, label, status, detail, latency_ms, base_url.
    status ∈ online | offline | disabled
    """
    base = {
        "id": source.id,
        "label": source.label,
        "base_url": source.base_url,
        "latency_ms": None,
        "detail": source.notes or "",
    }
    # Catalog-disabled hosts still get a quick probe so UI can show truth.
    own = session is None
    http = session or requests.Session()
    if own:
        http.headers.update(
            {
                "User-Agent": _UA,
                "Accept": "text/html,*/*;q=0.8",
                "Connection": "close",
            }
        )
    t0 = time.monotonic()
    try:
        # Prefer HEAD; fall back to GET if rejected.
        try:
            resp = http.head(
                source.base_url,
                timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
                allow_redirects=True,
            )
            if resp.status_code in (403, 405, 501) or resp.status_code >= 400:
                resp = http.get(
                    source.base_url,
                    timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
                    allow_redirects=True,
                    stream=True,
                )
                # Don't download body
                try:
                    resp.close()
                except Exception:
                    pass
        except requests.RequestException:
            resp = http.get(
                source.base_url,
                timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
                allow_redirects=True,
                stream=True,
            )
            try:
                resp.close()
            except Exception:
                pass
        ms = int((time.monotonic() - t0) * 1000)
        code = int(resp.status_code)
        if 200 <= code < 400:
            # Cloudflare challenge pages often 403; 200 with "Just a moment" is rare on HEAD.
            return {
                **base,
                "status": "online",
                "detail": f"HTTP {code}",
                "latency_ms": ms,
            }
        if code == 403:
            return {
                **base,
                "status": "offline",
                "detail": "blocked (403)",
                "latency_ms": ms,
            }
        return {
            **base,
            "status": "offline",
            "detail": f"HTTP {code}",
            "latency_ms": ms,
        }
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        return {
            **base,
            "status": "offline",
            "detail": _classify_error(exc),
            "latency_ms": ms,
        }
    finally:
        if own:
            try:
                http.close()
            except Exception:
                pass


def probe_all_sources(
    *,
    sources: Optional[List[MugshotSourceInfo]] = None,
    max_workers: int = 4,
) -> Dict[str, Dict[str, Any]]:
    """Probe all registered sources in parallel; return map id → status dict."""
    items = list(sources or list_mugshot_sources(available_only=False) or MUGSHOT_SOURCES)
    out: Dict[str, Dict[str, Any]] = {}
    if not items:
        return out
    workers = max(1, min(int(max_workers), len(items)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(probe_source, s): s.id for s in items}
        for fut in as_completed(futs):
            sid = futs[fut]
            try:
                out[sid] = fut.result()
            except Exception as exc:
                src = next((s for s in items if s.id == sid), None)
                out[sid] = {
                    "id": sid,
                    "label": src.label if src else sid,
                    "base_url": src.base_url if src else "",
                    "status": "offline",
                    "detail": _classify_error(exc),
                    "latency_ms": None,
                }
    return out


def status_label(row: Dict[str, Any]) -> str:
    """Short status token for UI rows."""
    st = str(row.get("status") or "unknown")
    if st == "online":
        ms = row.get("latency_ms")
        return f"online · {ms}ms" if ms is not None else "online"
    if st == "checking":
        return "checking…"
    detail = str(row.get("detail") or "offline").strip()
    if detail and detail.lower() != "offline":
        return f"offline · {detail}"
    return "offline"
