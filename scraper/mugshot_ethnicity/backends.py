"""Pluggable *local* mugshot ethnicity backends (lazy imports).

Production default is **DeepFace** (https://github.com/serengil/deepface):
open-source, runs entirely on-machine, downloads model weights once into the
user cache. It exposes a dedicated race attribute model (White / Black / Asian /
Indian / Middle Eastern / Latino Hispanic) which is what we need for
high-confidence gross misclassification checks.

Optional fallbacks:
  - CLIP zero-shot (local transformers + torch) if DeepFace is not installed
  - MockBackend for unit tests only (never selected by ``auto``)
"""
from __future__ import annotations

from typing import Dict, List, Type

from scraper.mugshot_ethnicity.backends_base import EthnicityBackend, MockBackend
from scraper.mugshot_ethnicity.backends_clip import ClipBackend
from scraper.mugshot_ethnicity.backends_deepface import DeepFaceBackend
from scraper.mugshot_ethnicity.backends_fairface import FairFaceBackend

# Production backends only — mock is never in auto chain
_BACKEND_CLASSES: List[Type[EthnicityBackend]] = [
    FairFaceBackend,
    DeepFaceBackend,
    ClipBackend,
]


def list_backend_status() -> Dict[str, bool]:
    """Fast presence check via find_spec — never import torch/keras on the UI thread."""
    import importlib.util

    out: Dict[str, bool] = {"mock": True, "fairface": False}
    try:
        out["fairface"] = FairFaceBackend().is_available()
    except Exception:
        out["fairface"] = False
    try:
        out["deepface"] = importlib.util.find_spec("deepface") is not None
    except Exception:
        out["deepface"] = False
    try:
        out["clip"] = (
            importlib.util.find_spec("torch") is not None
            and importlib.util.find_spec("transformers") is not None
        )
    except Exception:
        out["clip"] = False
    return out


def create_backend(
    name: str = "auto",
    *,
    auto_install: bool = True,
    log=None,
) -> EthnicityBackend:
    """
    Create a backend by name.

    ``auto`` → FairFace (face-race) if available, else DeepFace, else CLIP.
    ``fairface`` → standalone FairFace package only.
    ``deepface`` → DeepFace race head (legacy).
    ``mock`` → tests only.
    """
    from scraper.mugshot_ethnicity.setup import ensure_deepface
    from scraper.mugshot_ethnicity.setup_fairface import ensure_fairface

    key = (name or "auto").strip().lower()
    if key == "mock":
        return MockBackend()

    if key in ("auto", "fairface"):
        if auto_install:
            try:
                ensure_fairface(auto_install=True, warm=True, log=log)
            except Exception as e:
                if log:
                    try:
                        log(f"FairFace auto-setup: {e}")
                    except Exception:
                        pass
        fb = FairFaceBackend(log=log)
        if fb.is_available():
            try:
                if auto_install:
                    fb._get_scorer()
                return fb
            except Exception as e:
                if key == "fairface":
                    raise RuntimeError(
                        "FairFace (face-race) setup failed.\n"
                        "  Auto-setup could not finish — see log.\n"
                        f"Detail: {e}"
                    ) from e
                if log:
                    try:
                        log(f"FairFace unavailable ({e}); trying DeepFace…")
                    except Exception:
                        pass
        elif key == "fairface":
            raise RuntimeError(
                "FairFace backend not available after auto-setup.\n"
                "Ensure sibling face-race exists and torch installs, or:\n"
                "  cd face-race && pip install -e .\n"
                "Weights: ~/.face_race/weights/"
            )

    if key in ("auto", "deepface"):
        if auto_install:
            ensure_deepface(auto_install=True, warm=True, log=log)
        b = DeepFaceBackend()
        if b.is_available():
            return b
        if key == "deepface":
            raise RuntimeError(
                "DeepFace could not be set up automatically.\n"
                f"Interpreter: {__import__('sys').executable}\n"
                "Try:\n"
                "  python -m pip install -r requirements-vision.txt\n"
                "Or set SOR_SKIP_DEEPFACE_INSTALL=1 only to disable auto-install."
            )
        try:
            c = ClipBackend()
            if c.is_available():
                return c
        except Exception:
            pass
        status = list_backend_status()
        raise RuntimeError(
            "No local vision backend available.\n"
            f"Status: {status}\n"
            "  cd face-race && pip install -e .\n"
            "  python -m pip install -r requirements-vision.txt"
        )

    if key == "clip":
        b = ClipBackend()
        if not b.is_available():
            raise RuntimeError(
                "CLIP backend not installed:\n"
                "  pip install torch transformers pillow"
            )
        return b
    raise ValueError(f"Unknown mugshot backend: {name!r}")


__all__ = [
    "EthnicityBackend",
    "MockBackend",
    "DeepFaceBackend",
    "ClipBackend",
    "FairFaceBackend",
    "list_backend_status",
    "create_backend",
    "_BACKEND_CLASSES",
]
