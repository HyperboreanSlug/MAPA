"""Catalog of mugshot aggregator hosts and lookup helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class MugshotSourceInfo:
    id: str
    label: str
    base_url: str
    available: bool = True
    notes: str = ""
    # Relative host weight for load balancing (higher = can take more work)
    weight: float = 1.0


# Catalog of mugshot aggregators known to publish names + race + photos.
MUGSHOT_SOURCES: List[MugshotSourceInfo] = [
    MugshotSourceInfo(
        id="recentlybooked",
        label="RecentlyBooked",
        base_url="https://recentlybooked.com/",
        available=True,
        notes="County booking pages + homepage live feed.",
        weight=1.0,
    ),
    MugshotSourceInfo(
        id="mugshotscom",
        label="Mugshots.com",
        base_url="https://mugshots.com/",
        available=True,
        notes="US-States / County listings with biographic fields and mugshots.",
        weight=1.0,
    ),
    MugshotSourceInfo(
        id="bustednewspaper",
        label="Busted Newspaper",
        base_url="https://bustednewspaper.com/",
        available=False,
        notes="SSL/remote disconnect outage — disabled until environment can reach host.",
        weight=0.0,
    ),
    # Documented for future work (blocked / SPA / flaky today).
    MugshotSourceInfo(
        id="arrestsorg",
        label="Arrests.org",
        base_url="https://arrests.org/",
        available=False,
        notes="Cloudflare challenge; not scrapable without browser automation.",
        weight=0.0,
    ),
    MugshotSourceInfo(
        id="arrest",
        label="Arre.st",
        base_url="https://new.arre.st/",
        available=False,
        notes="JS SPA shell; no server-rendered listings yet.",
        weight=0.0,
    ),
    # Custom city jail monitors (not aggregators — direct jail search forms).
    MugshotSourceInfo(
        id="sf_sheriff",
        label="SF Sheriff (city monitor)",
        base_url="https://www.sfsheriff.gov/inmate-search",
        available=True,
        notes="San Francisco Sheriff inmate search. HTML form.",
        weight=0.5,
    ),
    MugshotSourceInfo(
        id="nyc_doc",
        label="NYC DOC (city monitor)",
        base_url="https://a073-ilsweb.nyc.gov/",
        available=True,
        notes="NYC DOC Inmate Lookup Service. HTML form, race coded.",
        weight=0.5,
    ),
    MugshotSourceInfo(
        id="hawaii_doc",
        label="Hawaii DOC (city monitor)",
        base_url="https://corrections.ehawaii.gov/",
        available=True,
        notes="Hawaii DOC offender search. HTML form, photo on detail.",
        weight=0.5,
    ),
    MugshotSourceInfo(
        id="baltimore_dpscs",
        label="Baltimore DPSCS (city monitor)",
        base_url="https://dpscs.maryland.gov/",
        available=False,
        notes="Module pending. No scraper yet.",
        weight=0.0,
    ),
    MugshotSourceInfo(
        id="alaska_doc",
        label="Alaska DOC (city monitor)",
        base_url="https://doc.alaska.gov/",
        available=False,
        notes="Module pending. No scraper yet.",
        weight=0.0,
    ),
]

_SOURCE_BY_ID = {s.id: s for s in MUGSHOT_SOURCES}


def get_mugshot_source(source_id: str) -> Optional[MugshotSourceInfo]:
    return _SOURCE_BY_ID.get((source_id or "").strip().lower())


def list_mugshot_sources(*, available_only: bool = False) -> List[MugshotSourceInfo]:
    if available_only:
        return [s for s in MUGSHOT_SOURCES if s.available]
    return list(MUGSHOT_SOURCES)


def source_labels(*, include_unavailable: bool = True) -> List[Tuple[str, str]]:
    """Return (id, label) pairs for GUI checkboxes."""
    out = []
    for s in MUGSHOT_SOURCES:
        if not include_unavailable and not s.available:
            continue
        label = s.label if s.available else f"{s.label} (unavailable)"
        out.append((s.id, label))
    return out
