"""Hard process lifecycle: stop jobs, end Tk, force-exit lingering workers.

Daemon threads die with the process; TensorFlow / some libraries start
*non-daemon* threads that keep python(w).exe alive after the window closes.
This module makes close always terminate the process cleanly.
"""
from __future__ import annotations

import atexit
import os
import sys
import threading
import time
from typing import Any

_FORCE_EXIT_SEC = 1.25
_atexit_registered = False


def mark_closing(app: Any) -> None:
    """Flip all known cancel / closing flags so workers exit loops ASAP."""
    try:
        app._closing = True
    except Exception:
        pass
    for attr, val in (
        ("_nsopw_cancel", True),
        ("_df_scan_cancel", True),
        ("_enrich_cancel", True),
        ("_requeue_cancel", True),
        ("_scrape_cancel", True),
        ("is_running", False),
    ):
        try:
            setattr(app, attr, val)
        except Exception:
            pass


def _force_exit(code: int = 0) -> None:
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(code)


def schedule_force_exit(delay_sec: float = _FORCE_EXIT_SEC, code: int = 0) -> None:
    def _go() -> None:
        _force_exit(code)

    try:
        t = threading.Timer(max(0.2, float(delay_sec)), _go)
        t.daemon = True
        t.name = "force-process-exit"
        t.start()
    except Exception:
        _force_exit(code)


def register_atexit_force() -> None:
    global _atexit_registered
    if _atexit_registered:
        return
    _atexit_registered = True

    def _on_exit() -> None:
        try:
            alive = [
                t
                for t in threading.enumerate()
                if t is not threading.main_thread() and t.is_alive() and not t.daemon
            ]
            if alive:
                _force_exit(0)
        except Exception:
            pass

    try:
        atexit.register(_on_exit)
    except Exception:
        pass


def shutdown_app(app: Any, *, force_delay: float = _FORCE_EXIT_SEC) -> None:
    if getattr(app, "_closing", False) and getattr(app, "_shutdown_armed", False):
        return
    mark_closing(app)
    try:
        app._shutdown_armed = True
    except Exception:
        pass

    register_atexit_force()
    schedule_force_exit(force_delay, 0)

    try:
        app.quit()
    except Exception:
        pass
    try:
        app.destroy()
    except Exception:
        pass


def run_app_mainloop(app: Any) -> None:
    register_atexit_force()
    try:
        app.mainloop()
    finally:
        mark_closing(app)
        try:
            time.sleep(0.05)
        except Exception:
            pass
        _force_exit(0)
