"""Vermont DOC public use file (Socrata, daily individual-level data)."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    raw_json,
)

SOURCE = "vt_doc"
STATE = "VT"
SOCRATA_CSV = (
    "https://data.vermont.gov/api/views/vf3r-u4kv/rows.csv?accessType=DOWNLOAD"
)


def download_vermont(
    out_dir: Path | str = Path("data/downloads/vt_doc"),
    *,
    force: bool = False,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "vt_doc_public.csv"
    if not force and target.is_file() and target.stat().st_size > 10_000:
        log(f"  exists {target.name} ({target.stat().st_size:,} bytes)")
        return target
    log("  downloading VT DOC public use file …")
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    r = session.get(SOCRATA_CSV, timeout=300)
    r.raise_for_status()
    target.write_bytes(r.content)
    log(f"  saved {target.name} ({len(r.content):,} bytes)")
    return target


def _get(row: Dict[str, Any], *names: str) -> Any:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def map_vt_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    first = clean(_get(row, "OffenderFirstName", "first_name", "first name", "firstname"))
    last = clean(_get(row, "OffenderLastName", "last_name", "last name", "lastname"))
    mid = clean(_get(row, "OffenderMiddleName", "middle_name", "middle name", "middle"))
    if not (first or last):
        full = clean(_get(row, "name", "full_name", "offender_name"))
        if full and "," in full:
            last, rest = full.split(",", 1)
            parts = rest.strip().split()
            first = parts[0] if parts else None
            mid = " ".join(parts[1:]) if len(parts) > 1 else None
        elif full:
            parts = full.split()
            first = parts[0] if parts else None
            last = parts[-1] if len(parts) > 1 else None
    if not (first or last):
        return None
    race = normalize_race(clean(_get(row, "Race", "race", "race_code", "race_ethnicity")))
    sex = normalize_sex(clean(_get(row, "sex", "gender", "sex_code")))
    dob = excel_serial_to_iso(_get(row, "dob", "date_of_birth", "birth_date"))
    age = clean(_get(row, "CurrentAgeInYears", "age"))
    offense = clean(_get(row, "ChargeDescription", "offense", "crime", "charge", "most_serious_offense"))
    facility = clean(_get(row, "LegalStatusAgency", "facility", "institution", "housing_facility"))
    county = clean(_get(row, "CityOfResidence", "county", "county_of_commitment"))
    admit = excel_serial_to_iso(_get(row, "BookingDate", "admission_date", "admit_date", "custody_admission_date"))
    release = excel_serial_to_iso(_get(row, "DateReleased", "release_date", "projected_release"))
    doc_id = clean(_get(row, "OffenderID", "doc_id", "offender_id", "id", "inmate_id"))
    parts = [p for p in (first, mid, last) if p]
    return {
        "first_name": first.title() if first else None,
        "middle_name": mid.title() if mid else None,
        "last_name": last.title() if last else None,
        "full_name": " ".join(parts) if parts else None,
        "sex": sex,
        "gender": sex,
        "race": race,
        "age": age,
        "booking_date": admit,
        "arrest_date": admit,
        "release_date": release,
        "agency": facility or "Vermont DOC",
        "jurisdiction": "Vermont DOC",
        "state": STATE,
        "county": county,
        "charge_description": offense,
        "booking_id": doc_id,
        "source_id": f"vt_doc:{doc_id or last}-{first}",
        "source_url": "https://data.vermont.gov/Public-Safety/DOCPublicUseFile/vf3r-u4kv",
        "source_system": SOURCE,
        "raw_json": raw_json({"dob": dob}),
    }


def import_vermont(
    data_dir: Path | str = Path("data/downloads/vt_doc"),
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
        log("Vermont DOC: downloading public use file …")
        path = download_vermont(data_dir, force=force_download)
    else:
        cands = list(data_dir.glob("*.csv"))
        if not cands:
            raise FileNotFoundError(f"No VT file under {data_dir}")
        path = max(cands, key=lambda p: p.stat().st_size)

    db = Database(database)
    totals = {"imported": 0, "skipped": 0, "skipped_identity": 0, "read": 0, "files": 1}
    batch: List[Dict[str, Any]] = []
    try:
        log(f"Reading {path.name} …")
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rec = map_vt_row(row)
                if not rec:
                    continue
                batch.append(rec)
                totals["read"] += 1
                if limit and totals["read"] >= limit:
                    break
                if len(batch) >= BATCH:
                    flush_batch(db, batch, totals, force=force)
        flush_batch(db, batch, totals, force=force)
    finally:
        db.close()
    return totals
