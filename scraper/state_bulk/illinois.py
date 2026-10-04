"""Illinois IDOC named bulk XLS: population, admissions, exits, parole."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from scraper.config_types import USER_AGENT
from scraper.state_bulk.common import (
    BATCH,
    clean,
    excel_serial_to_iso,
    flush_batch,
    log,
    normalize_race,
    normalize_sex,
    parse_last_first,
    raw_json,
)
from scraper.state_bulk.xls_io import iter_named_rows


def _capped(data: bytes, limit: int) -> bytes:
    """Stop oversize downloads. Keep memory safe."""
    if len(data) > limit:
        raise ValueError(f"Download too large: {len(data)} bytes")
    return data
SOURCE = "il_idoc"
STATE = "IL"
BASE = "https://idoc.illinois.gov"
# Crawl these index pages for every public .xls / .xlsx link
INDEX_PAGES = [
    ("population", "/reportsandstatistics/prison-population-data-sets.html"),
    ("admissions", "/reportsandstatistics/prison-admission-data-sets.html"),
    ("exits", "/reportsandstatistics/prison-exit-data-sets.html"),
    ("parole", "/reportsandstatistics/parole-population-data-sets.html"),
]


def _kind_from_path(rel: str, fallback: str) -> str:
    low = rel.lower()
    if "admission" in low:
        return "admissions"
    if "exit" in low:
        return "exits"
    if "parole" in low or "msr" in low:
        return "parole"
    if "prison-pop" in low or "prison_pop" in low or "population" in low:
        return "population"
    if "prison" in low:
        return "population"
    return fallback


def download_illinois(
    out_dir: Path | str = Path("data/downloads/il_idoc"),
    *,
    force: bool = False,
) -> List[Path]:
    """Download every named XLS linked from IDOC population data-set pages."""
    import re
    from urllib.parse import unquote

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    seen_urls: set[str] = set()
    jobs: List[tuple[str, str]] = []  # (kind, absolute_url)

    for fallback, page_rel in INDEX_PAGES:
        page_url = urljoin(BASE, page_rel)
        try:
            html = session.get(page_url, timeout=60).text
        except requests.RequestException as e:
            log(f"  WARN index {page_rel}: {e}")
            continue
        for rel in re.findall(
            r'href="([^"]+\.(?:xls|xlsx))"', html, flags=re.I
        ):
            abs_url = urljoin(BASE, unquote(rel))
            if abs_url in seen_urls:
                continue
            seen_urls.add(abs_url)
            jobs.append((_kind_from_path(rel, fallback), abs_url))

    if not jobs:
        raise RuntimeError("No Illinois XLS links found on IDOC index pages")

    log(f"  found {len(jobs)} spreadsheet links")
    paths: List[Path] = []
    for kind, url in jobs:
        name = Path(url.split("?")[0]).name
        # sanitize
        safe = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in name)
        dest = out / f"{kind}_{safe}"
        if dest.is_file() and dest.stat().st_size > 10_000 and not force:
            log(f"  exists {dest.name}")
            paths.append(dest)
            continue
        log(f"  downloading {kind}/{safe} …")
        try:
            r = session.get(url, timeout=180)
            r.raise_for_status()
            dest.write_bytes(_capped(r.content, 200_000_000))
            log(f"  saved {dest.name} ({len(r.content):,} bytes)")
            paths.append(dest)
        except requests.RequestException as e:
            log(f"  FAIL {url}: {e}")
    return paths


def _get(row: Dict[str, Any], *names: str) -> Any:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def map_il_row(row: Dict[str, Any], *, kind: str) -> Optional[Dict[str, Any]]:
    idoc = clean(_get(row, "IDOC #", "idoc #", "IDOC#"))
    first, middle, last = parse_last_first(clean(_get(row, "Name")))
    if not (first or last):
        return None
    offense = clean(
        _get(row, "Holding Offense", "holding offense", "Offense", "Current Offense")
    )
    facility = clean(
        _get(
            row,
            "Parent Institution",
            "Reception Center",
            "Holding Facility",
            "Facility",
        )
    )
    adm = excel_serial_to_iso(
        _get(row, "Current Admission Date", "Admission Date", "admission date")
    )
    dob = excel_serial_to_iso(_get(row, "Date of Birth", "date of birth"))
    release = excel_serial_to_iso(
        _get(
            row,
            "Projected Discharge Date",
            "Projected Discharge Date3",
            "Projected Mandatory Supervised Release (MSR) Date",
            "MSR/Parole Date",
        )
    )
    crime_class = clean(_get(row, "Crime Class", "crime class"))
    county = clean(_get(row, "Sentencing County", "sentencing county"))
    sex = normalize_sex(clean(_get(row, "Sex", "sex")))
    race = normalize_race(clean(_get(row, "Race", "race")))
    # Unique per kind + admission so pop/parole/adm/exit all land when present
    sid = (
        f"il_idoc:{idoc}:{kind}:{adm or ''}"
        if idoc
        else f"il_idoc:{last}:{first}:{kind}:{adm or ''}"
    )
    parts = [p for p in (first, middle, last) if p]
    base_url = (
        f"https://www.idoc.state.il.us/subsections/search/inms_print.asp?idoc={idoc}"
        if idoc
        else "https://idoc.illinois.gov/offender/inmatesearch.html"
    )
    rec: Dict[str, Any] = {
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "full_name": " ".join(parts) if parts else None,
        "sex": sex,
        "gender": sex,
        "race": race,
        "date_of_birth": dob,
        "booking_date": adm,
        "arrest_date": adm,
        "release_date": release,
        "agency": facility or "Illinois DOC",
        "jurisdiction": "Illinois DOC",
        "state": STATE,
        "county": county,
        "charge_description": offense,
        "charge_class": crime_class,
        "charge_level": crime_class,
        "booking_id": idoc,
        "source_id": sid,
        "source_url": f"{base_url}#{kind}:{adm or 'na'}",
        "source_system": SOURCE,
        "raw_json": raw_json({"kind": kind, "idoc": idoc, "admission": adm}),
    }
    return rec


def import_illinois(
    data_dir: Path | str = Path("data/downloads/il_idoc"),
    *,
    database: str = "data/arrests.db",
    limit: int = 0,
    force: bool = False,
    download: bool = True,
    force_download: bool = False,
) -> Dict[str, int]:
    from scraper.database import Database

    data_dir = Path(data_dir)
    if download:
        log("Illinois IDOC: downloading ALL public XLS sets …")
        paths = download_illinois(data_dir, force=force_download)
    else:
        paths = sorted(data_dir.glob("*.xls*"))
    if not paths:
        raise FileNotFoundError(f"No Illinois XLS under {data_dir}")

    db = Database(database)
    totals = {"imported": 0, "skipped": 0, "skipped_identity": 0, "read": 0, "files": 0}
    batch: List[Dict[str, Any]] = []
    try:
        for path in paths:
            kind = path.name.split("_", 1)[0].lower()
            if kind not in ("population", "parole", "admissions", "exits"):
                kind = "bulk"
            log(f"Reading {path.name} ({kind}) …")
            n_file = 0
            for row in iter_named_rows(path, required_headers=("Name", "Race")):
                rec = map_il_row(row, kind=kind)
                if not rec:
                    continue
                batch.append(rec)
                totals["read"] += 1
                n_file += 1
                if limit and totals["read"] >= limit:
                    break
                if len(batch) >= BATCH:
                    flush_batch(db, batch, totals, force=force)
            totals["files"] += 1
            log(f"  … {n_file:,} rows from {path.name}")
            if limit and totals["read"] >= limit:
                break
        flush_batch(db, batch, totals, force=force)
    finally:
        db.close()
    return totals
