"""RecentlyBooked Live Feed source selection helpers + health UI updates."""
from __future__ import annotations

import threading
from typing import List

from gui_app.theme import C

from .constants import _RB_SOURCE_OPTIONS


class RbLiveSourcesMixin:
    def _rb_live_sources_button_text(self) -> str:
        selected = self._rb_live_selected_sources()
        health = getattr(self, "_source_health", None) or {}
        online_ids = {
            sid
            for sid, row in health.items()
            if str(row.get("status") or "") == "online"
        }
        n_sel = len(selected)
        if n_sel == 0:
            base = "Sources (none)"
        elif n_sel >= len(_RB_SOURCE_OPTIONS):
            base = "Sources (all)"
        else:
            base = f"Sources ({n_sel})"
        open_mark = " ▴" if getattr(self, "_rb_live_sources_open", False) else " ▾"
        if not health:
            return base + " · …" + open_mark
        if health and all(
            str(r.get("status")) == "checking" for r in health.values()
        ):
            return base + " · checking…" + open_mark
        return f"{base} · {len(online_ids)} up" + open_mark

    def _rb_live_selected_sources(self) -> List[str]:
        vars_map = getattr(self, "_rb_live_source_vars", None) or {}
        return [
            sid
            for sid, _lab in _RB_SOURCE_OPTIONS
            if bool(vars_map.get(sid) and vars_map[sid].get())
        ]

    def _rb_live_status_token(self, sid: str) -> str:
        health = getattr(self, "_source_health", None) or {}
        row = health.get(sid) or {}
        st = str(row.get("status") or "")
        if not health:
            return "…"
        if st == "checking":
            return "checking…"
        if st == "online":
            ms = row.get("latency_ms")
            return f"online · {ms} ms" if ms is not None else "online"
        detail = str(row.get("detail") or "offline")
        if len(detail) > 36:
            detail = detail[:35] + "…"
        return f"offline · {detail}"

    def _rb_live_status_color(self, sid: str) -> str:
        health = getattr(self, "_source_health", None) or {}
        st = str((health.get(sid) or {}).get("status") or "")
        if st == "online":
            return C.get("success", "#7dcea0")
        if st == "offline":
            return C.get("danger", "#e07a7a")
        if st == "checking":
            return C.get("info", "#8ab4c9")
        return C["muted"]

    def _rb_live_refresh_source_status_ui(self) -> None:
        """Update open panel labels + Sources button after a health probe."""
        try:
            self.rb_live_sources_btn.configure(
                text=self._rb_live_sources_button_text()
            )
        except Exception:
            pass
        labels = getattr(self, "_rb_live_source_status_labels", None) or {}
        for sid, lbl in labels.items():
            try:
                lbl.configure(
                    text=self._rb_live_status_token(sid),
                    text_color=self._rb_live_status_color(sid),
                )
            except Exception:
                pass
        self._rb_live_apply_health_to_checks()
        if hasattr(self, "_rb_full_refresh_source_status"):
            try:
                self._rb_full_refresh_source_status()
            except Exception:
                pass

    def _rb_live_apply_health_to_checks(self) -> None:
        """On probe results: check all online sources, uncheck offline."""
        health = getattr(self, "_source_health", None) or {}
        vars_map = getattr(self, "_rb_live_source_vars", None) or {}
        if not health or not vars_map:
            return
        # Only auto-adjust after a real probe (not all-checking).
        if any(str(r.get("status")) == "checking" for r in health.values()):
            return
        if not any(str(r.get("status")) in ("online", "offline") for r in health.values()):
            return
        # First successful probe after startup: sync checks to live status.
        # Later probes (Recheck) only uncheck newly offline hosts so the
        # user can still deselect online sources mid-session.
        first_sync = not getattr(self, "_rb_live_health_synced", False)
        changed = False
        for sid, row in health.items():
            var = vars_map.get(sid)
            if var is None:
                continue
            st = str(row.get("status") or "")
            if st == "online":
                if first_sync and not var.get():
                    var.set(True)
                    changed = True
            elif st == "offline":
                if var.get():
                    var.set(False)
                    changed = True
        if first_sync:
            self._rb_live_health_synced = True
        if not self._rb_live_selected_sources():
            for sid, row in health.items():
                if str(row.get("status")) == "online" and sid in vars_map:
                    vars_map[sid].set(True)
                    changed = True
                    break
            if not self._rb_live_selected_sources() and vars_map:
                next(iter(vars_map.values())).set(True)
                changed = True
        if changed:
            self._rb_live_on_sources_changed()

    def _rb_live_recheck_sources(self) -> None:
        if hasattr(self, "_start_source_health_probe"):
            self._start_source_health_probe(force=True)
        else:
            self._rb_live_run_health_probe()

    def _rb_live_run_health_probe(self) -> None:
        """Fallback probe when shell helper is not available."""
        health = getattr(self, "_source_health", None)
        if health is None:
            self._source_health = {}
            health = self._source_health
        for sid, label in _RB_SOURCE_OPTIONS:
            health[sid] = {
                "id": sid,
                "label": label,
                "status": "checking",
                "detail": "",
                "latency_ms": None,
            }
        self._rb_live_refresh_source_status_ui()

        def work():
            try:
                from scraper.mugshot_sources.health import probe_all_sources

                result = probe_all_sources()
            except Exception as exc:
                result = {
                    sid: {
                        "id": sid,
                        "status": "offline",
                        "detail": str(exc)[:48],
                        "latency_ms": None,
                    }
                    for sid, _ in _RB_SOURCE_OPTIONS
                }

            def apply():
                self._source_health = result
                self._rb_live_refresh_source_status_ui()
                online = sum(
                    1 for r in result.values() if r.get("status") == "online"
                )
                self.log(f"Source health: {online}/{len(result)} online.")

            try:
                self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _rb_live_on_sources_changed(self):
        selected = self._rb_live_selected_sources()
        if not selected and self._rb_live_source_vars:
            health = getattr(self, "_source_health", None) or {}
            restored = False
            for sid, row in health.items():
                if (
                    str(row.get("status")) == "online"
                    and sid in self._rb_live_source_vars
                ):
                    self._rb_live_source_vars[sid].set(True)
                    restored = True
                    break
            if not restored:
                first = next(iter(self._rb_live_source_vars.values()))
                first.set(True)
        try:
            self.rb_live_sources_btn.configure(
                text=self._rb_live_sources_button_text()
            )
        except Exception:
            pass
        self._rb_rebuild_live_tree()
        self._rb_live_update_filter_status(log=False)
