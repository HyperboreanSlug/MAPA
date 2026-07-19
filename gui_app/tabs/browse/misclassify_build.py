"""Browse tab UI construction and static helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import RecordSidebar
from gui_app.tabs.browse.misclassify_constants import (
    BROWSE_ACTUAL_RACES,
    BROWSE_COLS,
    BROWSE_DEFAULT_LIMIT,
    BROWSE_LABELS,
    VERIFICATION_FILTERS,
    bucket_actual_race,
    verification_label,
    verification_query,
)
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_selected_record,
)
from scraper.charge_summary import summarize_charge
from scraper.database import Database
from scraper.searcher import format_race_label


class MisclassifyBuildMixin:
    """Build the browse tree + sidebar layout."""

    def _build_misclassify(self, tab):
        tab.configure(fg_color=C["surface"])
        controls = ctk.CTkFrame(tab, fg_color=C["panel"])
        controls.pack(fill="x", padx=8, pady=8)
        from gui_app.tabs.recentlybooked.full_scrape_flow import (
            FlowRow,
            after_idle_reflow,
        )

        flow = FlowRow(controls, padx=5, pady=4)
        host = flow.host

        races = ["All"] + self._browse_race_choices()
        actuals = ["All"] + list(BROWSE_ACTUAL_RACES)

        def _lbl(text: str):
            return ctk.CTkLabel(
                host, text=text, font=FONT_SM, text_color=C["muted"]
            )

        self.browse_stated_race = ctk.CTkComboBox(
            host, values=races, width=120, command=self._browse_filter_changed
        )
        self.browse_actual_race_filter = ctk.CTkComboBox(
            host,
            values=actuals,
            width=150,
            command=self._browse_filter_changed,
        )
        self.browse_review = ctk.CTkComboBox(
            host,
            values=VERIFICATION_FILTERS,
            width=170,
            command=self._browse_filter_changed,
        )
        # Source (RecentlyBooked / Mugshots.com / DOC bulk / …)
        src_values = ["All"] + self._browse_source_choices()
        self.browse_source_filter = ctk.CTkComboBox(
            host,
            values=src_values,
            width=150,
            command=self._browse_filter_changed,
        )
        self.browse_source_filter.set("All")
        # Last N days / weeks (empty amount = any time)
        self.browse_window_amount = ctk.CTkEntry(
            host, width=52, placeholder_text="any"
        )
        self.browse_window_unit = ctk.CTkComboBox(
            host,
            values=["days", "weeks"],
            width=78,
            command=self._browse_filter_changed,
        )
        self.browse_window_unit.set("days")
        self.browse_window_amount.bind(
            "<Return>", lambda _e: self._browse_filter_changed()
        )
        # Default cap keeps multi-million DOC DBs from OOM on auto-refresh.
        # 0 = "all" but GUI clamps to BROWSE_HARD_MAX in the refresh path.
        self.browse_limit = ctk.CTkEntry(
            host, width=90, placeholder_text=str(BROWSE_DEFAULT_LIMIT)
        )
        self.browse_stated_race.set("All")
        self.browse_actual_race_filter.set("All")
        self.browse_review.set("Unverified")
        self.browse_limit.insert(0, str(BROWSE_DEFAULT_LIMIT))
        self.browse_misclass_only = ctk.CTkCheckBox(
            host,
            text="Suspected misclassifications only",
            font=FONT_SM,
            command=self._browse_filter_changed,
        )
        self.browse_refresh_btn = ctk.CTkButton(
            host, text="Refresh", command=self._browse_refresh
        )
        export_btn = ctk.CTkButton(
            host, text="Export CSV", command=self._browse_export
        )
        self.browse_status = ctk.CTkLabel(
            host,
            text="Filter arrests and review with the sidebar. Confirmed stay out of Unverified.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        for w in (
            _lbl("Stated race"),
            self.browse_stated_race,
            _lbl("Actual race"),
            self.browse_actual_race_filter,
            _lbl("Confirmation"),
            self.browse_review,
            _lbl("Source"),
            self.browse_source_filter,
            _lbl("Last"),
            self.browse_window_amount,
            self.browse_window_unit,
            _lbl("Limit"),
            self.browse_limit,
            self.browse_misclass_only,
            self.browse_refresh_btn,
            export_btn,
            self.browse_status,
        ):
            flow.add(w)
        after_idle_reflow(self, flow)
        controls.bind("<Configure>", lambda _e: flow.reflow(), add="+")

        self.mc_status = self.browse_status
        self.mc_analyze_btn = self.browse_refresh_btn

        pane = _hpaned(tab)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, self.mc_tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        self.mc_tree.configure(columns=BROWSE_COLS)
        _enable_tree_column_sort(self.mc_tree, BROWSE_COLS, BROWSE_LABELS)
        _stretch_columns(
            self.mc_tree, BROWSE_COLS, [200, 100, 130, 140, 180, 50, 110, 120]
        )

        self.browse_sidebar = RecordSidebar(pane)
        # Coarse actual-race buckets only on Browse (not the long ethnicity list).
        self.browse_sidebar._actual_race_options = list(BROWSE_ACTUAL_RACES)
        self.browse_sidebar.bind_after(self.after)
        self.browse_sidebar.bind_verdict(self._browse_sidebar_verdict)
        self.browse_sidebar.bind_actual_race(self._browse_sidebar_actual_race)
        pane.add(left, minsize=360, stretch="always")
        pane.add(self.browse_sidebar.frame, minsize=400, stretch="always")

        self._browse_records: List[Dict[str, Any]] = []
        self._mc_results = self._browse_records
        self.mc_tree.bind("<<TreeviewSelect>>", self._browse_on_select)
        self.after(200, self._browse_refresh)

    def _browse_race_choices(self) -> List[str]:
        try:
            return Database(self.db_path).distinct_race_labels()
        except Exception:
            return []

    def _browse_source_choices(self) -> List[str]:
        try:
            db = Database(self.db_path)
            try:
                if hasattr(db, "distinct_source_systems"):
                    return list(db.distinct_source_systems())
            finally:
                db.close()
        except Exception:
            pass
        return [
            "recentlybooked",
            "mugshotscom",
            "bustednewspaper",
            "nc_dac",
            "il_idoc",
            "tx_tdcj",
        ]

    def _browse_filter_changed(self, _choice: str = "") -> None:
        if getattr(self, "_browse_busy", False):
            return
        self._browse_refresh()

    def _browse_since_date(self) -> Optional[str]:
        """ISO cutoff from Last N days/weeks controls, or None for any time."""
        try:
            from scraper.database.date_window import resolve_cutoff

            amount = ""
            unit = "days"
            if getattr(self, "browse_window_amount", None) is not None:
                amount = self.browse_window_amount.get()
            if getattr(self, "browse_window_unit", None) is not None:
                unit = self.browse_window_unit.get()
            return resolve_cutoff(amount, unit)
        except Exception:
            return None

    @staticmethod
    def _browse_verification_query(label: Optional[str]) -> Optional[str]:
        return verification_query(label)

    @staticmethod
    def _browse_review_label(record: Dict[str, Any]) -> str:
        return verification_label(record)

    @staticmethod
    def _browse_name(record: Dict[str, Any]) -> str:
        name = (
            str(record.get("full_name") or "").strip()
            or f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
            or "—"
        )
        return name.upper() if name and name != "—" else name

    def _browse_row_values(self, record: Dict[str, Any]) -> tuple:
        raw_actual = (record.get("likely_ethnicity") or "").strip()
        actual = bucket_actual_race(raw_actual) or raw_actual or "—"
        return (
            self._browse_name(record),
            format_race_label(record.get("race") or ""),
            actual,
            self._browse_review_label(record),
            summarize_charge(record),
            record.get("state") or "—",
            record.get("arrest_date") or record.get("booking_date") or "—",
            record.get("source_system") or "—",
        )

    def _browse_selected_index(self) -> Optional[int]:
        record = tree_selected_record(self.mc_tree)
        if record is None:
            return None
        try:
            return self._browse_records.index(record)
        except ValueError:
            return None

    def _browse_on_select(self, _event=None):
        record = tree_selected_record(self.mc_tree)
        if record is None:
            self.browse_sidebar.clear()
            return
        self.browse_sidebar.show(record)
