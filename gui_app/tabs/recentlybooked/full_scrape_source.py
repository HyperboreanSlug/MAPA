"""Full Scrape source dropdown labels + health status from live probe."""
from __future__ import annotations

from typing import List

from .constants import _BN_UNAVAILABLE_HINT, _RB_SOURCE_BY_LABEL, _RB_SOURCE_OPTIONS

_ALL_LABEL = "All available (load-balanced)"


class RbFullScrapeSourceMixin:
    def _rb_full_source_values(self) -> List[str]:
        """Dropdown labels with live-feed health status tokens."""
        out: List[str] = []
        for sid, label in _RB_SOURCE_OPTIONS:
            base = label.replace(" (unavailable)", "").strip()
            token = "…"
            if hasattr(self, "_rb_live_status_token"):
                try:
                    token = self._rb_live_status_token(sid)
                except Exception:
                    token = "…"
            out.append(f"{base} · {token}")
        health = getattr(self, "_source_health", None) or {}
        online = sum(
            1 for r in health.values() if str(r.get("status")) == "online"
        )
        if health and not any(
            str(r.get("status")) == "checking" for r in health.values()
        ):
            all_tok = f"{online} up"
        elif health:
            all_tok = "checking…"
        else:
            all_tok = "…"
        out.append(f"{_ALL_LABEL} · {all_tok}")
        return out

    def _rb_full_refresh_source_status(self) -> None:
        """Sync Full Scrape source dropdown with the latest health probe."""
        combo = getattr(self, "rb_full_source", None)
        if combo is None:
            return
        prev_id = self._rb_full_source_id()
        values = self._rb_full_source_values()
        try:
            combo.configure(values=values)
        except Exception:
            return
        chosen = None
        for v in values:
            if self._rb_full_id_from_label(v) == prev_id:
                chosen = v
                break
        if chosen is None and values:
            chosen = values[0]
        if chosen is not None:
            try:
                combo.set(chosen)
            except Exception:
                pass

    @staticmethod
    def _rb_full_id_from_label(label: str) -> str:
        text = (label or "").strip()
        if not text:
            return "recentlybooked"
        base = text.split(" · ")[0].strip()
        if "load-balanced" in base.lower() or "load-balanced" in text.lower():
            return "all"
        for full_label, sid in _RB_SOURCE_BY_LABEL.items():
            plain = full_label.replace(" (unavailable)", "").strip()
            if base == full_label or base == plain:
                return sid
        return _RB_SOURCE_BY_LABEL.get(base, "recentlybooked")

    def _rb_full_source_id(self) -> str:
        label = (
            getattr(self, "rb_full_source", None).get()
            if getattr(self, "rb_full_source", None)
            else "RecentlyBooked"
        )
        return self._rb_full_id_from_label(label)

    def _rb_full_on_source_change(self, _choice=None):
        src = self._rb_full_source_id()
        if src == "all":
            self.rb_state.configure(placeholder_text="State (e.g. fl or Florida)")
            self.rb_county.configure(placeholder_text="County slug (optional)")
            self.rb_full_status.configure(
                text=(
                    "Load-balanced multi-host: counties split across available "
                    "sources; identity dedupe skips mirrored people."
                )
            )
        elif src == "bustednewspaper":
            self.rb_state.configure(placeholder_text="State slug (e.g. texas)")
            self.rb_county.configure(
                placeholder_text="County slug (e.g. brazos-county)"
            )
            self.rb_full_status.configure(
                text=_BN_UNAVAILABLE_HINT
                + " Full scrape will fail fast if SSL is still broken."
            )
        elif src == "mugshotscom":
            self.rb_state.configure(placeholder_text="State (e.g. fl or Florida)")
            self.rb_county.configure(
                placeholder_text="County (e.g. Alachua-County-FL)"
            )
            self.rb_full_status.configure(
                text="Mugshots.com: US-States county pages; Threads = workers per county."
            )
        else:
            self.rb_state.configure(placeholder_text="State (e.g. nj)")
            self.rb_county.configure(placeholder_text="County slug (optional)")
            self.rb_full_status.configure(
                text="Multi-thread counties; set Threads + Delay per request."
            )
