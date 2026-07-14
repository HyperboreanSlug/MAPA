#!/usr/bin/env python3
"""
Arrest Public Archiver — desktop GUI (CustomTkinter).

Dark UI for scrape / search / ethnic misclassification / RecentlyBooked / DeepFace.
Double-click ``Launch Arrest Archiver.vbs`` (no console), or ``run_gui.bat``, or ``pythonw gui.py``.
Tab UI lives under gui_app/ (lazy-loaded). See MODULES.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    os.chdir(_ROOT)
except OSError:
    pass

# RetinaFace / DeepFace need legacy Keras before any tensorflow import
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


def _fatal(msg: str) -> None:
    text = msg[:1800]
    try:
        (_ROOT / "gui_error.log").write_text(msg, encoding="utf-8")
    except OSError:
        pass
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, "Arrest Public Archiver", 0x10)
    except Exception:
        try:
            print(msg, file=sys.stderr)
        except Exception:
            pass


def _ensure_dependencies() -> None:
    need = []
    for mod, pip_name in (
        ("customtkinter", "customtkinter"),
        ("bs4", "beautifulsoup4"),
        ("requests", "requests"),
        ("curl_cffi", "curl_cffi"),
    ):
        try:
            __import__(mod)
        except ImportError:
            need.append(pip_name)
    if not need:
        return
    req = _ROOT / "requirements.txt"
    cmd = [sys.executable, "-m", "pip", "install", "--user"]
    if req.is_file():
        cmd += ["-r", str(req)]
    else:
        cmd += need
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        _fatal(
            "Missing packages and auto-install failed.\n\n"
            f"Interpreter:\n{sys.executable}\n\n"
            f"Need: {', '.join(need)}\n\n{e}\n\n"
            "Run: python -m pip install -r requirements.txt"
        )
        raise SystemExit(1) from e


_ensure_dependencies()


def _start_deepface_setup_background(app_settings: Optional[dict] = None) -> None:
    sett = app_settings or {}
    if not bool(sett.get("deepface_auto_setup", True)):
        return

    def _log(msg: str) -> None:
        try:
            with open(_ROOT / "deepface_setup.log", "a", encoding="utf-8") as f:
                from datetime import datetime

                f.write(f"{datetime.now().isoformat()} {msg.rstrip()}\n")
        except OSError:
            pass

    warm = bool(sett.get("deepface_auto_warm", True))
    models = [
        p.strip()
        for p in str(sett.get("deepface_weight_models") or "Race").split(",")
        if p.strip()
    ]
    detector = str(sett.get("deepface_detector") or "retinaface")

    def _run() -> None:
        try:
            import time

            time.sleep(3)
            from scraper.mugshot_ethnicity.setup import (
                deepface_available,
                download_selected_weights,
                ensure_deepface,
            )

            ok = ensure_deepface(auto_install=True, warm=False, log=_log)
            if ok and warm and deepface_available():
                download_selected_weights(
                    models or ["Race"],
                    detector_backend=detector,
                    log=_log,
                )
        except Exception as e:
            _log(f"Background DeepFace setup error: {e}")

    try:
        import threading

        threading.Thread(target=_run, name="deepface-setup", daemon=True).start()
    except Exception:
        pass


def main() -> None:
    try:
        from gui_app.shell import ArrestArchiverApp
    except Exception as e:
        import traceback

        _fatal(
            f"Failed to import GUI:\n\n{e}\n\n{traceback.format_exc()}\n\n{sys.executable}"
        )
        raise SystemExit(1) from e
    app = ArrestArchiverApp()
    sett = getattr(app, "app_settings", None) or {}
    _start_deepface_setup_background(sett if isinstance(sett, dict) else {})
    # Never leave python(w) alive after the window closes (TF non-daemon threads)
    from gui_app.process_lifecycle import run_app_mainloop

    run_app_mainloop(app)


if __name__ == "__main__":
    main()
