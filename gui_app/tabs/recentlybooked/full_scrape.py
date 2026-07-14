"""RecentlyBooked Full Scrape filters and tree rebuild."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from gui_app.widgets import tree_row_bind, tree_rows_reset


class RbFullScrapeMixin:
    def _rb_full_filter_flags(self) -> tuple[bool, bool]:
        hide_race = bool(
            getattr(self, "rb_full_hide_no_race_var", None)
            and self.rb_full_hide_no_race_var.get()
        )
        hide_photo = bool(
            getattr(self, "rb_full_hide_no_photo_var", None)
            and self.rb_full_hide_no_photo_var.get()
        )
        return hide_race, hide_photo

    def _rb_full_update_filter_status(self, *, log: bool = True) -> None:
        shown = len(self._rb_full_records)
        total = len(getattr(self, "_rb_full_all", []) or [])
        hide_race, hide_photo = self._rb_full_filter_flags()
        mode = self._rb_filter_mode_text(
            hide_no_race=hide_race, hide_no_photo=hide_photo
        )
        self.rb_full_status.configure(
            text=f"Full scrape: {shown}/{total} shown ({mode})."
        )
        if log:
            self.log(f"Full scrape filter: {mode} ({shown}/{total}).")

    def _rb_full_on_race_filter_toggle(self):
        self._rb_rebuild_full_tree()
        self._rb_full_update_filter_status()

    def _rb_full_on_photo_filter_toggle(self):
        self._rb_rebuild_full_tree()
        self._rb_full_update_filter_status()

    def _rb_rebuild_full_tree(self, *, select_url: Optional[str] = None) -> None:
        eth = getattr(self, "_rb_full_eth", None)
        all_rows = getattr(self, "_rb_full_all", []) or []
        hide_race, hide_photo = self._rb_full_filter_flags()
        shown = self._rb_filter_rows(
            all_rows,
            hide_no_race=hide_race,
            hide_no_photo=hide_photo,
        )
        self._rb_full_records = shown
        self.rb_full_tree.delete(*self.rb_full_tree.get_children())
        tree_rows_reset(self.rb_full_tree)
        select_item = None
        select_rec = None
        for rec in shown:
            item = self.rb_full_tree.insert(
                "", "end", values=self._rb_row_values(rec, eth)
            )
            tree_row_bind(self.rb_full_tree, item, rec)
            if select_url and str(rec.get("source_url") or "") == select_url:
                select_item = item
                select_rec = rec
        if select_item:
            self.rb_full_tree.selection_set(select_item)
            self.rb_full_tree.see(select_item)
            self.rb_full_sidebar.show(select_rec)
        elif not shown:
            self.rb_full_sidebar.clear("No rows match filter.")
