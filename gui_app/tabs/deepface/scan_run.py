"""DeepFace scan start worker."""
from __future__ import annotations

import threading

from gui_app.theme import C


class DeepfaceScanRunMixin:
    def _deepface_scan_start(self) -> None:
        if getattr(self, "_df_scan_running", False):
            self._deepface_scan_log_msg("Scan already running")
            return
        self._deepface_scan_save_options()
        opts = self._deepface_scan_collect_options()
        if not opts["recorded_races"]:
            self._deepface_scan_log_msg("Select at least one recorded race filter")
            return
        if not opts["face_labels"]:
            self._deepface_scan_log_msg("Select at least one face label to flag")
            return
        self._df_scan_cancel = False
        self._df_scan_hits = []
        self._df_scan_hit_ids = set()
        self._df_scan_hits_by_iid = {}
        self._df_scan_selected_iid = None
        self._df_scan_image_refs = []
        self._df_scan_live_preview = True
        self._df_scan_live_seq = int(getattr(self, "_df_scan_live_seq", 0) or 0) + 1
        live_gen = self._df_scan_live_seq
        try:
            self.df_scan_tree.delete(*self.df_scan_tree.get_children())
            self.df_scan_progress.set(0)
            self._deepface_scan_clear_review()
            self.df_scan_review_meta.configure(
                text="Starting scan — mugshots will appear here as they are scored."
            )
        except Exception:
            pass
        self._deepface_scan_set_busy(True)
        self._deepface_scan_log_msg(
            f"Starting scan: state={opts['state'] or 'ALL'} "
            f"source={opts.get('source_system') or 'ALL'} "
            f"min_conf={opts['min_confidence']} limit={opts['limit'] or '∞'} "
            f"recorded={opts['recorded_races']} faces={opts['face_labels']}"
            f"{' · FORCE RESCAN' if opts.get('force_rescan') else ' · skip already scanned'}"
        )
        try:
            self.df_scan_status.configure(text="Starting…", text_color=C["accent"])
        except Exception:
            pass

        db_path = str(getattr(self, "db_path", None) or "data/arrests.db")
        detector = "retinaface"
        try:
            from scraper.app_settings import load_settings

            detector = str(
                (getattr(self, "app_settings", None) or load_settings()).get(
                    "deepface_detector"
                )
                or "retinaface"
            )
        except Exception:
            pass

        progress, on_photo, on_scored, on_hit = self._deepface_scan_callbacks(live_gen)

        def worker() -> None:
            hits = []
            err = None
            try:
                from scraper.mugshot_ethnicity.setup import configure_tf_keras_env
                from scraper.mugshot_ethnicity.scorer import (
                    BackendUnavailableError,
                    MugshotEthnicityScorer,
                )
                from scraper.mugshot_ethnicity.scanner import scan_gross_misclassifications

                # Legacy TF env only needed if auto falls back to DeepFace.
                configure_tf_keras_env()
                # Default: FairFace (face-race) → DeepFace → CLIP
                try:
                    scorer = MugshotEthnicityScorer(
                        backend="auto",
                        auto_install=True,
                        log=self._deepface_scan_log_msg,
                    )
                except BackendUnavailableError as e:
                    raise RuntimeError(str(e)) from e

                self._deepface_scan_log_msg(
                    f"Using backend: {scorer.backend_name}"
                )
                hits = scan_gross_misclassifications(
                    db_path=db_path, scorer=scorer,
                    recorded_races=opts["recorded_races"],
                    face_labels=opts["face_labels"],
                    min_confidence=opts["min_confidence"],
                    limit=opts["limit"], state=opts["state"],
                    source_system=opts.get("source_system"),
                    progress=progress, log=self._deepface_scan_log_msg,
                    cancel=lambda: bool(getattr(self, "_df_scan_cancel", False)),
                    skip_scanned=not bool(opts.get("force_rescan")),
                    force_rescan=bool(opts.get("force_rescan")),
                    persist=True, detector=detector,
                    on_hit=on_hit, on_photo=on_photo, on_scored=on_scored,
                )
            except Exception as e:
                err = e
                self._deepface_scan_log_msg(f"ERROR: {e}")

            def done():
                self._deepface_scan_finish(hits, err)

            try:
                self.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, name="deepface-scan", daemon=True).start()
