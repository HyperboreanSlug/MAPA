"""RecentlyBooked Misclassify UI and actual-race override."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import (
    RecordSidebar,
    merge_race_manual_flags,
)
from gui_app.tabs.browse.misclassify_constants import (
    VERIFICATION_FILTERS,
    verification_label,
    verification_query,
)
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_iid_for_record,
    tree_selected_record,
)
from scraper.database import Database

from .full_scrape_flow import FlowRow, after_idle_reflow


class RbMisclassifyMixin:
    def _build_rb_misclassify(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        flow = FlowRow(bar, padx=5, pady=4)

        race_lbl = ctk.CTkLabel(
            flow.host, text="Stated race", font=FONT_SM, text_color=C["muted"]
        )
        race_values = ["All"]
        try:
            race_values = ["All"] + Database(self.db_path).distinct_race_labels()
        except Exception:
            pass
        self.rb_mc_stated_race = ctk.CTkComboBox(
            flow.host, values=race_values, width=130, command=self._rb_mc_filter_changed
        )
        self.rb_mc_stated_race.set("All")

        conf_lbl = ctk.CTkLabel(
            flow.host, text="Confirmation", font=FONT_SM, text_color=C["muted"]
        )
        self.rb_mc_review = ctk.CTkComboBox(
            flow.host,
            values=list(VERIFICATION_FILTERS),
            width=170,
            command=self._rb_mc_filter_changed,
        )
        self.rb_mc_review.set("Unverified")

        analyze_btn = ctk.CTkButton(
            flow.host, text="Analyze", command=self._rb_analyze
        )
        self.rb_mc_status = ctk.CTkLabel(
            flow.host,
            text="Surname misclass; confirmed names stay out unless filtered in.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        for w in (
            race_lbl,
            self.rb_mc_stated_race,
            conf_lbl,
            self.rb_mc_review,
            analyze_btn,
            self.rb_mc_status,
        ):
            flow.add(w)
        after_idle_reflow(self, flow)
        bar.bind("<Configure>", lambda _e: flow.reflow(), add="+")

        pane = _hpaned(tab)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, self.rb_mc_tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        cols = ["name", "race", "likely", "conf", "review", "charge", "state"]
        labels = {
            "name": "Name",
            "race": "Stated race",
            "likely": "Likely",
            "conf": "Conf",
            "review": "Confirmation",
            "charge": "Charge",
            "state": "State",
        }
        self.rb_mc_tree.configure(columns=cols)
        _enable_tree_column_sort(self.rb_mc_tree, cols, labels)
        _stretch_columns(self.rb_mc_tree, cols, [170, 90, 100, 55, 140, 170, 50])
        self.rb_mc_sidebar = RecordSidebar(pane)
        self.rb_mc_sidebar.bind_after(self.after)
        self.rb_mc_sidebar.bind_verdict(self._rb_mc_on_verdict)
        self.rb_mc_sidebar.bind_actual_race(self._rb_mc_set_actual_race)
        pane.add(left, minsize=360, stretch="always")
        pane.add(self.rb_mc_sidebar.frame, minsize=400, stretch="always")
        self._rb_mc_records: List[Dict[str, Any]] = []

        def on_select(_event=None):
            record = tree_selected_record(self.rb_mc_tree)
            if record is None:
                self.rb_mc_sidebar.clear()
                return
            self.rb_mc_sidebar.show(record)

        self.rb_mc_tree.bind("<<TreeviewSelect>>", on_select)

    def _rb_mc_filter_changed(self, _choice: str = "") -> None:
        # Re-run only when a prior result set exists (avoids surprise full scan).
        if getattr(self, "_rb_mc_records", None) is not None and self._rb_mc_records:
            self._rb_analyze()

    def _rb_mc_review_query(self) -> Optional[str]:
        widget = getattr(self, "rb_mc_review", None)
        label = widget.get() if widget is not None else "Unverified"
        return verification_query(label)

    def _rb_mc_on_verdict(self, record: Dict[str, Any], verdict: str) -> None:
        want = self._rb_mc_review_query()
        # Drop when filter is Unverified (default) or when the new status
        # no longer matches Confirmed correct / Confirmed incorrect.
        remove = (
            want == "unreviewed"
            or (want == "correct" and verdict != "correct")
            or (want == "incorrect" and verdict != "incorrect")
        )
        self._rb_apply_verdict(
            record,
            verdict,
            tree=self.rb_mc_tree,
            records=self._rb_mc_records,
            sidebar=self.rb_mc_sidebar,
            remove_from_list=remove,
        )
        if not remove:
            # Refresh confirmation column in place.
            for existing in self._rb_mc_records:
                same_id = record.get("id") and existing.get("id") == record.get("id")
                same_url = (
                    record.get("source_url")
                    and existing.get("source_url") == record.get("source_url")
                )
                if same_id or same_url or existing is record:
                    existing["flags"] = record.get("flags")
                    iid = tree_iid_for_record(self.rb_mc_tree, existing)
                    if iid is not None:
                        vals = list(self.rb_mc_tree.item(iid, "values"))
                        if len(vals) >= 5:
                            vals[4] = verification_label(existing)
                            self.rb_mc_tree.item(iid, values=vals)
                    break

    def _rb_mc_set_actual_race(self, record: Dict[str, Any], actual: str) -> None:
        from gui_app.shared.record_sidebar_flags import verdict_for_actual_vs_stated
        from gui_app.shared.verdict_persist import persist_ethnicity_verdict

        actual = (actual or "").strip() or "Unknown"
        record["likely_ethnicity"] = actual
        # Actual-race choice confirms classification so they leave Unverified.
        verdict = verdict_for_actual_vs_stated(record.get("race"), actual)
        ok, _flags, err = persist_ethnicity_verdict(
            self.db_path,
            record,
            verdict,
            extra_fields={"likely_ethnicity": actual},
        )
        flags_json = merge_race_manual_flags(record.get("flags"))
        record["flags"] = flags_json
        rid = record.get("id")
        source_url = str(record.get("source_url") or "").strip()
        if rid is None and source_url:
            db = Database(self.db_path)
            try:
                row = db._conn.execute(
                    "SELECT id FROM arrests WHERE source_url = ? LIMIT 1",
                    (source_url,),
                ).fetchone()
                if row:
                    rid = row["id"] if hasattr(row, "keys") else row[0]
                    record["id"] = int(rid)
            finally:
                db.close()
        if rid is not None:
            try:
                self.db.update_arrest(
                    int(rid),
                    {"likely_ethnicity": actual, "flags": flags_json},
                )
            except Exception as exc:
                self.log(f"Could not save actual race: {exc}")
                return
        want = self._rb_mc_review_query()
        if ok and want == "unreviewed":
            self._rb_apply_verdict(
                record,
                verdict,
                tree=self.rb_mc_tree,
                records=self._rb_mc_records,
                sidebar=self.rb_mc_sidebar,
                remove_from_list=True,
            )
            self.log(f"RB misclass actual race set: {actual} (confirmed {verdict})")
            return
        for existing in self._rb_mc_records:
            same_id = record.get("id") and existing.get("id") == record.get("id")
            same_url = source_url and existing.get("source_url") == source_url
            if same_id or same_url or existing is record:
                existing["likely_ethnicity"] = actual
                existing["flags"] = flags_json
                iid = tree_iid_for_record(self.rb_mc_tree, existing)
                if iid is not None:
                    vals = list(self.rb_mc_tree.item(iid, "values"))
                    if len(vals) >= 3:
                        vals[2] = actual
                    if len(vals) >= 5:
                        vals[4] = verification_label(existing)
                    self.rb_mc_tree.item(iid, values=vals)
                break
        conf = f" confirmed {verdict}" if ok else f" (confirm failed: {err})"
        self.log(f"RB misclass actual race set: {actual}{conf}")

    def _rb_mc_race_filter(self) -> Optional[str]:
        race = (
            getattr(self, "rb_mc_stated_race", None).get()
            if getattr(self, "rb_mc_stated_race", None)
            else "All"
        )
        if race in (None, "", "All"):
            return None
        return str(race)
