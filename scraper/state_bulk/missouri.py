"""Missouri DOC Sunshine Law bulk import (named offenders since 1974)."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from scraper.config_types import USER_AGENT
from scraper.state_bulk.common import (
    BATCH,
    clean,
    flush_batch,
    log,
    normalize_race,
    normalize_sex,
    raw_json,
)

SOURCE = "mo_doc"
STATE = "MO"
SUNSHINE_URL = "https://docservices.mo.gov/Sunshine_Law/fak930.zip"

# Fixed-width field positions
_DOC = (0, 8)
_LAST = (8, 24)
_FIRSTMID = (24, 53)
_RACE = (53, 83)
_SEX = (83, 113)
_DOB = (113, 121)
_CASE = (121, 145)

# After case number: county(4) + optional repeat(4) + code(12) + offense
_REST_RE = re.compile(
    r"([A-Z]{4})(?:[A-Z]{4})?\d{6,12}\s*(.+?)(?:\s{2,}|$)"
)


def _fw(line: str, pos: tuple) -> Optional[str]:
    return clean(line[pos[0]:pos[1]].strip()) if len(line) > pos[0] else None


def download_missouri(
    out_dir: Path | str = Path("data/downloads/mo_doc"),
    *,
    force: bool = False,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "fak930.dat"
    if not force and target.is_file() and target.stat().st_size > 1_000_000:
        log(f"  exists {target.name} ({target.stat().st_size:,} bytes)")
        return target
    log("  downloading MO Sunshine Law fak930.zip …")
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    r = session.get(SUNSHINE_URL, timeout=300, stream=True)
    r.raise_for_status()
    buf = io.BytesIO()
    total = 0
    for chunk in r.iter_content(65536):
        total += len(chunk)
        if total > 500_000_000:
            raise ValueError("MO zip too large")
        buf.write(chunk)
    buf.seek(0)
    z = zipfile.ZipFile(buf)
    names = [n for n in z.namelist() if not n.endswith("/")]
    if not names:
        raise ValueError("Empty MO zip")
    info = z.getinfo(names[0])
    # Stop zip bombs. Check ratio and size.
    if info.file_size > 500_000_000:
        raise ValueError("MO dat too large")
    name = names[0]
    with z.open(name) as f:
        data = f.read()
    if len(data) > 500_000_000:
        raise ValueError("MO dat too large")
    target.write_bytes(data)
    log(f"  saved {target.name} ({len(data):,} bytes)")
    return target


def _parse_dob(raw: Optional[str]) -> Optional[str]:
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    y, m, d = raw[:4], raw[4:6], raw[6:8]
    if int(y) < 1900 or int(m) < 1 or int(m) > 12 or int(d) < 1 or int(d) > 31:
        return None
    return f"{y}-{m}-{d}"


def _split_first_mid(raw: Optional[str]):
    if not raw:
        return None, None
    parts = raw.split()
    if not parts:
        return None, None
    first = parts[0].title()
    mid = " ".join(p[0].upper() for p in parts[1:] if p) if len(parts) > 1 else None
    return first, mid


def map_mo_line(line: str) -> Optional[Dict[str, Any]]:
    if len(line) < 121:
        return None
    doc_id = _fw(line, _DOC)
    last = _fw(line, _LAST)
    first_raw = _fw(line, _FIRSTMID)
    race = normalize_race(_fw(line, _RACE))
    sex = normalize_sex(_fw(line, _SEX))
    dob = _parse_dob(_fw(line, _DOB))
    case = _fw(line, _CASE)
    county = None
    offense = None
    rest = line[145:] if len(line) > 145 else ""
    m = _REST_RE.search(rest)
    if m:
        county = m.group(1)
        offense = clean(m.group(2))
    first, mid = _split_first_mid(first_raw)
    if not (first or last):
        return None
    parts = [p for p in (first, mid, last) if p]
    return {
        "first_name": first,
        "middle_name": mid,
        "last_name": last.title() if last else None,
        "full_name": " ".join(parts) if parts else None,
        "sex": sex,
        "gender": sex,
        "race": race,
        "date_of_birth": dob,
        "agency": "Missouri DOC",
        "jurisdiction": "Missouri DOC",
        "state": STATE,
        "county": county,
        "charge_description": offense,
        "case_number": case,
        "booking_id": doc_id,
        "source_id": f"mo_doc:{doc_id}:{case or ''}",
        "source_url": "https://doc.mo.gov/",
        "source_system": SOURCE,
        "raw_json": raw_json({"doc_id": doc_id, "dob": dob}),
    }


def import_missouri(
    data_dir: Path | str = Path("data/downloads/mo_doc"),
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
        log("Missouri DOC: downloading Sunshine Law data …")
        path = download_missouri(data_dir, force=force_download)
    else:
        cands = list(data_dir.glob("*.dat"))
        if not cands:
            raise FileNotFoundError(f"No MO file under {data_dir}")
        path = max(cands, key=lambda p: p.stat().st_size)

    db = Database(database)
    totals = {"imported": 0, "skipped": 0, "skipped_identity": 0, "read": 0, "files": 1}
    batch: List[Dict[str, Any]] = []
    try:
        log(f"Reading {path.name} …")
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n\r")
                rec = map_mo_line(line)
                if not rec:
                    continue
                batch.append(rec)
                totals["read"] += 1
                if limit and totals["read"] >= limit:
                    break
                if len(batch) >= BATCH:
                    flush_batch(db, batch, totals, force=force)
                    if totals["read"] % 50000 == 0:
                        log(f"  … read {totals['read']:,} imported {totals['imported']:,}")
        flush_batch(db, batch, totals, force=force)
    finally:
        db.close()
    return totals
