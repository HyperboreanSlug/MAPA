"""Dispatch named state DOC bulk imports."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from scraper.state_bulk.common import log

# Registry of bulk sources that ship named offender rows
STATE_SOURCES = {
    "illinois": {
        "id": "il_idoc",
        "name": "Illinois IDOC population / admissions / parole XLS",
        "state": "IL",
        "portal": "https://idoc.illinois.gov/reportsandstatistics/populationdatasets.html",
    },
    "il": {"alias": "illinois"},
    "texas": {
        "id": "tx_tdcj",
        "name": "Texas TDCJ High Value inmate dataset",
        "state": "TX",
        "portal": "https://www.tdcj.texas.gov/documents/High_Value_Data_Sets.xlsx",
    },
    "tx": {"alias": "texas"},
    "missouri": {
        "id": "mo_doc",
        "name": "Missouri DOC Sunshine Law offender file (since 1974)",
        "state": "MO",
        "portal": "https://docservices.mo.gov/Sunshine_Law/fak930.zip",
    },
    "mo": {"alias": "missouri"},
    "vermont": {
        "id": "vt_doc",
        "name": "Vermont DOC public use file (Socrata, daily)",
        "state": "VT",
        "portal": "https://data.vermont.gov/Public-Safety/DOCPublicUseFile/vf3r-u4kv",
    },
    "vt": {"alias": "vermont"},
}


def resolve_states(spec: str) -> List[str]:
    raw = (spec or "all").strip().lower()
    if raw in ("all", "*"):
        return ["illinois", "texas", "missouri", "vermont"]
    out: List[str] = []
    for part in raw.replace(";", ",").split(","):
        key = part.strip().lower()
        if not key:
            continue
        meta = STATE_SOURCES.get(key)
        if not meta:
            raise ValueError(f"Unknown state bulk source: {key}")
        if "alias" in meta:
            key = meta["alias"]
        if key not in out:
            out.append(key)
    return out


def import_state_bulk(
    states: str = "all",
    *,
    database: str = "data/arrests.db",
    limit: int = 0,
    force: bool = False,
    download: bool = True,
    force_download: bool = False,
    data_root: Path | str = Path("data/downloads"),
    enrich: bool = True,
) -> Dict[str, Dict[str, int]]:
    """Download (optional) and import one or more state DOC bulk sources."""
    data_root = Path(data_root)
    results: Dict[str, Dict[str, int]] = {}
    for key in resolve_states(states):
        meta = STATE_SOURCES[key]
        log(f"\n=== {meta['name']} ({meta['state']}) ===")
        log(f"Portal: {meta['portal']}")
        if key == "illinois":
            from scraper.state_bulk.illinois import import_illinois

            results[key] = import_illinois(
                data_root / "il_idoc",
                database=database,
                limit=limit,
                force=force,
                download=download,
                force_download=force_download,
            )
        elif key == "texas":
            from scraper.state_bulk.texas import import_texas

            results[key] = import_texas(
                data_root / "tx_tdcj",
                database=database,
                limit=limit,
                force=force,
                download=download,
                force_download=force_download,
            )
        elif key == "missouri":
            from scraper.state_bulk.missouri import import_missouri

            results[key] = import_missouri(
                data_root / "mo_doc",
                database=database,
                limit=limit,
                force=force,
                download=download,
                force_download=force_download,
            )
        elif key == "vermont":
            from scraper.state_bulk.vermont import import_vermont

            results[key] = import_vermont(
                data_root / "vt_doc",
                database=database,
                limit=limit,
                force=force,
                download=download,
                force_download=force_download,
            )
        else:
            raise ValueError(key)
        r = results[key]
        log(
            f"Done {key}: read={r.get('read', 0):,} imported={r.get('imported', 0):,} "
            f"skipped={r.get('skipped', 0):,}"
        )
        if enrich:
            _run_enrich(key, database=database)
    return results


def _run_enrich(key: str, *, database: str = "data/arrests.db") -> None:
    """Run post-import enrichment (photo backfill) for a state if available."""
    if key == "north_carolina":
        log(f"\n--- Enriching NC DAC mugshots ---")
        try:
            from scraper.nc_dac import enrich_nc_dac_photos

            stats = enrich_nc_dac_photos(database=database)
            log(f"NC enrich: {stats}")
        except Exception as e:
            log(f"NC enrich failed: {e}")
    else:
        meta = STATE_SOURCES.get(key, {})
        log(f"  (no photo enrichment available for {meta.get('state', key)})")
