"""DeepFace scan and setup controls adapted for arrest records."""
from __future__ import annotations

import threading

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.theme import C
from gui_app.widgets import (
    _enable_tree_column_sort,
    _stretch_columns,
    _tree_frame,
)
from scraper.app_settings import save_settings
from scraper.database import Database


class DeepfaceTabMixin:
    def _build_deepface(self, tab):
        tab.configure(fg_color=C["surface"])
        view = ctk.CTkTabview(
            tab,
            fg_color=C["surface"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent_dim"],
        )
        view.pack(fill="both", expand=True, padx=6, pady=6)
        host = LazyTabHost(view)
        host.register("Scan", self._build_deepface_scan)
        host.register("Setup", self._build_deepface_setup)
        view.set("Scan")
        host.ensure("Scan")
        return host

    def _build_deepface_scan(self, tab):
        s = self.app_settings
        top = ctk.CTkFrame(tab, fg_color=C["panel"])
        top.pack(fill="x", padx=8, pady=8)
        self.df_state = ctk.CTkEntry(top, placeholder_text="State (all)")
        self.df_source = ctk.CTkEntry(
            top, placeholder_text="Source, e.g. recentlybooked"
        )
        self.df_conf = ctk.CTkEntry(top, placeholder_text="Min confidence")
        self.df_limit = ctk.CTkEntry(top, placeholder_text="Limit (0=all)")
        for w, v in (
            (self.df_state, s.get("deepface_scan_state", "")),
            (self.df_source, s.get("deepface_scan_source", "")),
            (self.df_conf, s.get("deepface_scan_min_conf", "0.85")),
            (self.df_limit, s.get("deepface_scan_limit", "0")),
        ):
            w.insert(0, str(v))
            w.pack(side="left", padx=5, pady=8)
        self.df_start = ctk.CTkButton(
            top, text="Scan mugshots", command=self._start_deepface_scan
        )
        self.df_start.pack(side="left", padx=5)
        self.df_status = ctk.CTkLabel(
            tab,
            text="Scans local mugshots only; results appear in Browse → DeepFace.",
            text_color=C["muted"],
        )
        self.df_status.pack(anchor="w", padx=10)
        wrap, self.df_tree = _tree_frame(tab)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ["id", "name", "race", "state", "source", "photo"]
        self.df_tree.configure(columns=cols)
        _enable_tree_column_sort(self.df_tree, cols)
        _stretch_columns(self.df_tree, cols)

    def _start_deepface_scan(self):
        try:
            conf = float(self.df_conf.get() or 0.85)
            limit = int(self.df_limit.get() or 0)
        except ValueError:
            self.df_status.configure(text="Confidence and limit must be numbers.")
            return
        state = self.df_state.get().strip()
        source = self.df_source.get().strip()
        self.app_settings.update(
            deepface_scan_state=state,
            deepface_scan_source=source,
            deepface_scan_min_conf=str(conf),
            deepface_scan_limit=str(limit),
        )
        save_settings(self.app_settings)
        self.df_start.configure(state="disabled")
        self.df_status.configure(text="Preparing candidates…")
        db_path = self.db_path
        detector = self.app_settings.get("deepface_detector", "retinaface")

        def work():
            hits = 0
            rows: list = []
            try:
                from scraper.mugshot_ethnicity.scorer import MugshotEthnicityScorer

                db = Database(db_path)
                try:
                    rows = list(
                        db.iter_arrests(
                            limit=limit or None,
                            with_photos=True,
                            source_system=source or None,
                        )
                    )
                    if state:
                        rows = [
                            r
                            for r in rows
                            if (r.get("state") or "").upper() == state.upper()
                        ]
                    self.after(0, lambda: self._show_deepface_candidates(rows))
                    scorer = MugshotEthnicityScorer(backend="auto")
                    for index, row in enumerate(rows, 1):
                        face = scorer.score_record(row)
                        label = (face.top_label or "").lower()
                        score = float(face.top_confidence or 0.0)
                        recorded = (row.get("race") or "").upper()
                        hit = bool(
                            face.ok
                            and score >= conf
                            and label in {"black", "indian", "asian"}
                            and recorded in {"WHITE", "W", "CAUCASIAN"}
                        )
                        if hit:
                            hits += 1
                        db.upsert_deepface_scan(
                            arrest_id=int(row["id"]),
                            photo_path=row.get("photo_path"),
                            top_label=label,
                            top_confidence=score,
                            scores=face.scores,
                            backend=face.backend,
                            detector=detector,
                            face_detected=face.face_detected,
                            error=face.error,
                            is_hit=hit,
                            recorded_race=row.get("race") or "",
                            predicted_label=label,
                            severity=(
                                "high"
                                if hit and score >= 0.9
                                else "medium"
                                if hit
                                else ""
                            ),
                            reason=(
                                f"Face scores {label} at {score:.0%} but recorded "
                                f"race is {recorded}"
                                if hit
                                else ""
                            ),
                            scan_min_conf=conf,
                        )
                        if index % 5 == 0:
                            self.log(f"DeepFace: {index}/{len(rows)} scanned")
                finally:
                    db.close()
                n_rows, n_hits = len(rows), hits
                self.after(
                    0,
                    lambda: self.df_status.configure(
                        text=f"Scan complete: {n_rows:,} arrests, {n_hits:,} hits."
                    ),
                )
            except Exception as e:
                err = str(e)
                self.after(
                    0, lambda: self.df_status.configure(text=f"Scan failed: {err}")
                )
            finally:
                self.after(0, lambda: self.df_start.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    def _show_deepface_candidates(self, rows):
        self.df_tree.delete(*self.df_tree.get_children())
        for r in rows:
            name = (
                r.get("full_name")
                or f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            )
            self.df_tree.insert(
                "",
                "end",
                values=(
                    r["id"],
                    name,
                    r.get("race") or "",
                    r.get("state") or "",
                    r.get("source_system") or "",
                    r.get("photo_path") or "",
                ),
            )
        self.df_status.configure(
            text=f"Scanning {len(rows):,} arrests with mugshots…"
        )

    def _build_deepface_setup(self, tab):
        ctk.CTkLabel(tab, text="DeepFace setup", font=("Segoe UI", 16, "bold")).pack(
            anchor="w", padx=14, pady=(14, 4)
        )
        self.df_detector = ctk.CTkComboBox(
            tab,
            values=[
                "retinaface",
                "opencv",
                "ssd",
                "mtcnn",
                "yunet",
                "mediapipe",
                "centerface",
            ],
        )
        self.df_detector.set(self.app_settings.get("deepface_detector", "retinaface"))
        self.df_detector.pack(anchor="w", padx=14, pady=6)
        self.df_auto = ctk.CTkCheckBox(tab, text="Set up DeepFace automatically")
        if self.app_settings.get("deepface_auto_setup", True):
            self.df_auto.select()
        else:
            self.df_auto.deselect()
        self.df_auto.pack(anchor="w", padx=14, pady=6)
        ctk.CTkButton(
            tab, text="Save setup preferences", command=self._save_deepface_setup
        ).pack(anchor="w", padx=14, pady=8)
        self.df_setup_status = ctk.CTkLabel(
            tab,
            text="Install optional vision dependencies from requirements-vision.txt.",
            text_color=C["muted"],
        )
        self.df_setup_status.pack(anchor="w", padx=14)

    def _save_deepface_setup(self):
        self.app_settings["deepface_detector"] = self.df_detector.get()
        self.app_settings["deepface_auto_setup"] = bool(self.df_auto.get())
        save_settings(self.app_settings)
        self.df_setup_status.configure(text="Saved.")
