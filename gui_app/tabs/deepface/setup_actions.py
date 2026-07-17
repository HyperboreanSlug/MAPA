"""DeepFace setup actions: options, weights, download, install worker."""
from __future__ import annotations

import threading
from typing import List

from gui_app.theme import C


class DeepfaceSetupActionsMixin:
    def _deepface_selected_weight_ids(self) -> List[str]:
        ids = ["Race"]
        for mid, var in getattr(self, "_df_weight_vars", {}).items():
            try:
                if bool(var.get()) and mid not in ids:
                    ids.append(mid)
            except Exception:
                pass
        return ids

    def _deepface_selected_detector_id(self) -> str:
        label = ""
        try:
            label = (self.df_detector_var.get() or "").strip()
        except Exception:
            pass
        return (getattr(self, "_df_det_id_by_label", {}) or {}).get(label, "retinaface")

    def _deepface_on_detector_change(self, _choice: str = "") -> None:
        from scraper.mugshot_ethnicity.weights_catalog import (
            detector_local_status,
            explain_detector,
        )

        det = self._deepface_selected_detector_id()
        try:
            self.df_detector_help.configure(text=explain_detector(det))
        except Exception:
            pass
        try:
            st = detector_local_status(det)
            if hasattr(self, "df_detector_status"):
                self.df_detector_status.configure(
                    text=st.get("label") or "",
                    text_color=C["success"] if st.get("downloaded") else C["danger"],
                )
        except Exception:
            pass
        self._deepface_save_options()

    def _deepface_on_weight_toggle(self, model_id: str = "") -> None:
        from scraper.mugshot_ethnicity.weights_catalog import explain_weight

        mid = model_id or "Race"
        if mid == "Race" and mid in getattr(self, "_df_weight_vars", {}):
            try:
                self._df_weight_vars["Race"].set(True)
            except Exception:
                pass
        try:
            self.df_weight_help.configure(text=explain_weight(mid))
        except Exception:
            pass
        self._deepface_save_options()

    def _deepface_save_options(self) -> None:
        try:
            from scraper.app_settings import load_settings, save_settings, normalize_settings

            raw = load_settings()
            raw["deepface_auto_setup"] = bool(self.df_auto_setup.get())
            raw["deepface_auto_warm"] = bool(self.df_auto_warm.get())
            raw["deepface_detector"] = self._deepface_selected_detector_id()
            raw["deepface_weight_models"] = ",".join(self._deepface_selected_weight_ids())
            save_settings(raw)
            self.app_settings = normalize_settings(raw)
            self._deepface_append_log(
                f"Saved: auto_setup={raw['deepface_auto_setup']} "
                f"auto_warm={raw['deepface_auto_warm']} "
                f"detector={raw['deepface_detector']} "
                f"weights={raw['deepface_weight_models']}"
            )
        except Exception as e:
            self._deepface_append_log(f"Could not save options: {e}")

    def _deepface_set_busy(self, busy: bool) -> None:
        self._df_setup_running = busy
        state = "disabled" if busy else "normal"
        for name in ("df_install_btn", "df_warm_btn"):
            w = getattr(self, name, None)
            if w is not None:
                try:
                    w.configure(state=state)
                except Exception:
                    pass
        if hasattr(self, "df_job_status"):
            self.df_job_status.configure(
                text="Working… (see activity log)" if busy else ""
            )

    def _deepface_download_selected_weights(self) -> None:
        """Download checked model weights + selected detector into local cache."""
        self._deepface_save_options()
        self._deepface_run_setup(warm=True, install=False, weights_only=True)

    def _deepface_run_setup(
        self,
        *,
        warm: bool = True,
        install: bool = True,
        weights_only: bool = False,
    ) -> None:
        if getattr(self, "_df_setup_running", False):
            self._deepface_append_log("Setup already running")
            return
        self._deepface_set_busy(True)
        models = self._deepface_selected_weight_ids()
        detector = self._deepface_selected_detector_id()
        self._deepface_append_log(
            f"Starting setup (install={install}, warm={warm}, "
            f"detector={detector}, models={models})…"
        )

        def worker():
            ok = False
            try:
                from scraper.mugshot_ethnicity.setup_fairface import (
                    ensure_fairface,
                    fairface_available,
                )
                from scraper.mugshot_ethnicity.setup import (
                    ensure_deepface,
                    download_selected_weights,
                    deepface_available,
                )

                if install:
                    ff_ok = ensure_fairface(
                        auto_install=True,
                        warm=True,
                        log=self._deepface_append_log,
                        force_reinstall=False,
                    )
                    self._deepface_append_log(
                        f"FairFace (primary): {'OK' if ff_ok else 'failed'}"
                    )
                    df_ok = ensure_deepface(
                        auto_install=True,
                        warm=False,
                        log=self._deepface_append_log,
                        force_reinstall=False,
                    )
                    ok = bool(ff_ok or df_ok)
                    if df_ok and warm:
                        results = download_selected_weights(
                            models,
                            detector_backend=detector,
                            log=self._deepface_append_log,
                        )
                        ok = bool(
                            ff_ok
                            or results.get("Race")
                            or any(results.values())
                        )
                elif warm or weights_only:
                    ff_ok = ensure_fairface(
                        auto_install=False,
                        warm=True,
                        log=self._deepface_append_log,
                    )
                    if not deepface_available() and not fairface_available():
                        self._deepface_append_log(
                            "No vision backend — use Install / repair packages first"
                        )
                        ok = False
                    else:
                        results = {}
                        if deepface_available():
                            results = download_selected_weights(
                                models,
                                detector_backend=detector,
                                log=self._deepface_append_log,
                            )
                        ok = bool(
                            ff_ok
                            or results.get("Race")
                            or any(results.values())
                        )
                else:
                    ok = fairface_available() or deepface_available()
            except Exception as e:
                self._deepface_append_log(f"ERROR: {e}")
                ok = False

            def done():
                self._deepface_set_busy(False)
                self._deepface_refresh_status()
                try:
                    self._deepface_refresh_download_badges()
                except Exception:
                    pass
                if hasattr(self, "df_job_status"):
                    self.df_job_status.configure(
                        text="Setup finished OK" if ok else "Setup failed — see log",
                        text_color=C["success"] if ok else C["danger"],
                    )
                self._deepface_append_log(
                    "Done." if ok else "Finished with errors."
                )

            try:
                self.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, name="deepface-tab-setup", daemon=True).start()
