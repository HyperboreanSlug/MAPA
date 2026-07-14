"""Startup source health probe for ArrestArchiverApp."""
from __future__ import annotations

import threading
from typing import Any, Dict, List


class SourceHealthMixin:
    """Ping mugshot hosts in a background thread; store results on the app."""

    def _start_source_health_probe(self, *, force: bool = False) -> None:
        if getattr(self, "_source_health_busy", False) and not force:
            return
        self._source_health_busy = True
        try:
            from scraper.mugshot_sources import list_mugshot_sources

            sources = list_mugshot_sources(available_only=False)
        except Exception:
            sources = []

        health: Dict[str, Dict[str, Any]] = getattr(self, "_source_health", None) or {}
        self._source_health = health
        for s in sources:
            health[s.id] = {
                "id": s.id,
                "label": s.label,
                "base_url": s.base_url,
                "status": "checking",
                "detail": "",
                "latency_ms": None,
            }
        if hasattr(self, "_rb_live_refresh_source_status_ui"):
            try:
                self._rb_live_refresh_source_status_ui()
            except Exception:
                pass
        self.log("Probing mugshot sources…")

        def work() -> None:
            try:
                from scraper.mugshot_sources.health import probe_all_sources

                result = probe_all_sources(sources=sources or None)
            except Exception as exc:
                result = {
                    s.id: {
                        "id": s.id,
                        "label": s.label,
                        "base_url": s.base_url,
                        "status": "offline",
                        "detail": str(exc)[:48],
                        "latency_ms": None,
                    }
                    for s in sources
                }

            def apply() -> None:
                self._source_health = result
                self._source_health_busy = False
                online = [
                    str(r.get("label") or sid)
                    for sid, r in result.items()
                    if r.get("status") == "online"
                ]
                offline = [
                    f"{r.get('label') or sid} ({r.get('detail') or 'down'})"
                    for sid, r in result.items()
                    if r.get("status") != "online"
                ]
                self.log(
                    f"Source health: {len(online)} online"
                    + (f" — {', '.join(online)}" if online else "")
                    + "."
                )
                if offline:
                    self.log("Offline: " + "; ".join(offline[:6]))
                if hasattr(self, "_rb_live_refresh_source_status_ui"):
                    try:
                        self._rb_live_refresh_source_status_ui()
                    except Exception:
                        pass

            try:
                self.after(0, apply)
            except Exception:
                self._source_health_busy = False

        threading.Thread(target=work, daemon=True).start()
