"""Registry and multi-host orchestrator for mugshot HTML sources.

Sources similar to RecentlyBooked / Busted Newspaper:
  - recentlybooked.com  — multi-state county booking pages
  - mugshots.com        — multi-state county booking pages (implemented)
  - bustednewspaper.com — currently SSL-blocked (registered as unavailable)

When multiple sources cover the same county/person, the orchestrator:
  1. Partitions work units (state/county) across available hosts (round-robin)
  2. Shares a cross-host identity index so detail pages for the same person
     are only fetched from one host
  3. Runs sources in parallel threads so load is split rather than stacked
"""
from __future__ import annotations

from .health import probe_all_sources, probe_source, status_label
from .identity import IdentityIndex, identity_keys_for_record
from .orchestrator import MultiSourceOrchestrator
from .partition import partition_work_units
from .registry import (
    MUGSHOT_SOURCES,
    MugshotSourceInfo,
    get_mugshot_source,
    list_mugshot_sources,
    source_labels,
)
from .result import MultiSourceResult
from .types import CancelCheck, ProgressCallback, RecordCallback

__all__ = [
    "CancelCheck",
    "ProgressCallback",
    "RecordCallback",
    "MugshotSourceInfo",
    "MUGSHOT_SOURCES",
    "get_mugshot_source",
    "list_mugshot_sources",
    "source_labels",
    "IdentityIndex",
    "identity_keys_for_record",
    "partition_work_units",
    "MultiSourceResult",
    "MultiSourceOrchestrator",
    "probe_all_sources",
    "probe_source",
    "status_label",
]
