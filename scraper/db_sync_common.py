"""Download / update the public arrests SQLite archive from GitHub.

Release assets (format 2):
  - ``arrests.db.zip`` base snapshot (+ ``MANIFEST.json``)
  - ``arrests.delta.NNNN.zip`` incremental upsert/delete packs
  - ``arrests.photos.NNN.zip`` mugshots under ``data/photos/*/photos/``

Clients only download. Upload is gated to the local publisher machine
(``data/db_publish.allow`` + ``scripts/publish_database_release.py``).

Default source: ``HyperboreanSlug/MAPA`` tag ``database-latest``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_GITHUB_REPO = "HyperboreanSlug/MAPA"
DEFAULT_RELEASE_TAG = "database-latest"
DEFAULT_ASSET_NAME = "arrests.db.zip"
DEFAULT_MANIFEST_NAME = "MANIFEST.json"
DEFAULT_DB_REL = Path("data/arrests.db")
USER_AGENT = "Arrest-Public-Archiver-DB-Sync/1.1"
PHOTO_ASSET_PREFIX = "arrests.photos."
DELTA_ASSET_PREFIX = "arrests.delta."


@dataclass
class SyncResult:
    ok: bool
    action: str  # skipped | downloaded | updated | error
    message: str
    record_count: Optional[int] = None
    sha256: Optional[str] = None
    bytes_written: int = 0
    photos_extracted: int = 0
    deltas_applied: int = 0


