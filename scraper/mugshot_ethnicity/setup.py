"""Ensure DeepFace (local race model) is installed and ready.

Called automatically when mugshot scoring starts with backend auto/deepface.
Installs from ``requirements-vision.txt`` into the current interpreter, then
optionally warms the race model (downloads weights to ``~/.deepface/weights/``).

Hardening:
  * pip always targets *this* process's site-packages (pythonw → python.exe)
  * cross-process file lock so two GUIs cannot fight over WinError 32
  * retries on file-lock / permission pip failures
  * detects numpy ABI mismatches and force-repairs the vision stack
  * sets TF_USE_LEGACY_KERAS so RetinaFace works with TF 2.16+/Keras 3
"""
from __future__ import annotations

from scraper.mugshot_ethnicity.setup_common import configure_tf_keras_env
from scraper.mugshot_ethnicity.setup_fairface import (
    ensure_fairface,
    ensure_fairface_background,
    fairface_available,
    fairface_runtime_ok,
)
from scraper.mugshot_ethnicity.setup_install import (
    ensure_deepface,
    ensure_deepface_background,
)
from scraper.mugshot_ethnicity.setup_runtime import (
    deepface_available,
    deepface_importable,
    deepface_runtime_ok,
    invalidate_runtime_cache,
)
from scraper.mugshot_ethnicity.setup_warm import (
    download_selected_weights,
    warm_deepface_models,
)

__all__ = [
    "configure_tf_keras_env",
    "deepface_available",
    "deepface_importable",
    "deepface_runtime_ok",
    "download_selected_weights",
    "ensure_deepface",
    "ensure_deepface_background",
    "ensure_fairface",
    "ensure_fairface_background",
    "fairface_available",
    "fairface_runtime_ok",
    "invalidate_runtime_cache",
    "warm_deepface_models",
]
