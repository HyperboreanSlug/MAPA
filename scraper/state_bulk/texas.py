"""Texas TDCJ High Value Dataset (named inmate population)."""
from __future__ import annotations

import csv
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
    parse_last_first,
    raw_json,
)

def _capped(data: bytes, limit: int) -> bytes:
    """Stop oversize downloads. Keep memory safe."""
    if len(data) > limit:
        raise ValueError(f"Download too large: {len(data)} bytes")
    return data
SOURCE = "tx_tdcj"
STATE = "TX"
# Official monthly spreadsheet + open-data mirror
TDCJ_XLSX = "https://www.tdcj.texas.gov/documents/High_Value_Data_Sets.xlsx"
SOCRATA_CSV = (
    "https://data.texas.gov/api/views/cerf-ms45/rows.csv?accessType=DOWNLOAD"
)


def download_texas(
    out_dir: Path | str = Path("data/downloads/tx_tdcj"),
    *,
    force: bool = False,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    # Prefer official XLSX
    xlsx = out / "High_Value_Data_Sets.xlsx"
    csv_path = out / "high_value.csv"
    try:
        if force or not xlsx.is_file() or xlsx.stat().st_size < 100_000:
            log("  downloading TDCJ High_Value_Data_Sets.xlsx …")
            r = session.get(TDCJ_XLSX, timeout=300)
            r.raise_for_status()
            xlsx.write_bytes(_capped(r.content, 200_000_000))
            log(f"  saved {xlsx.name} ({len(r.content):,} bytes)")
        else:
            log(f"  exists {xlsx.name}")
        return xlsx
    except Exception as e:
        log(f"  XLSX failed ({e}); trying open-data CSV …")
        if force or not csv_path.is_file() or csv_path.stat().st_size < 100_000:
            r = session.get(SOCRATA_CSV, timeout=300)
            r.raise_for_status()
            csv_path.write_bytes(_capped(r.content, 200_000_000))
            log(f"  saved {csv_path.name} ({len(r.content):,} bytes)")
        return csv_path


def _iter_rows(path: Path):
    if path.suffix.lower() in (".xlsx", ".xls"):
        from scraper.state_bulk.xls_io import iter_named_rows

        yield from iter_named_rows(path, required_headers=("Name", "Race"))
        return
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield row


def _get(row: Dict[str, Any], *names: str) -> Any:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def map_tx_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tdcj = clean(_get(row, "TDCJ Number", "tdcj number"))
    sid = clean(_get(row, "SID Number", "sid number"))
    first, middle, last = parse_last_first(clean(_get(row, "Name")))
    if not (first or last):
        return None
    offense = clean(_get(row, "TDCJ Offense", "tdcj offense"))
    facility = clean(_get(row, "Current Facility", "current facility"))
    county = clean(_get(row, "County", "county"))
    sex = normalize_sex(clean(_get(row, "Gender", "gender", "Sex")))
    race = normalize_race(clean(_get(row, "Race", "race")))
    age = clean(_get(row, "Age", "age"))
    sent = excel_serial_to_iso(_get(row, "Sentence Date", "sentence date"))
    off_date = excel_serial_to_iso(_get(row, "Offense Date", "offense date"))
    release = excel_serial_to_iso(_get(row, "Projected Release", "projected release"))
    # Drop absurd future sentinels
    if release and release.startswith(("5555", "7550", "9999")):
        release = None
    case = clean(_get(row, "Case Number", "case number"))
    years = clean(_get(row, "Sentence (Years)", "sentence (years)"))
    key = tdcj or sid or f"{last}-{first}-{sent}"
    parts = [p for p in (first, middle, last) if p]
    rec: Dict[str, Any] = {
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "full_name": " ".join(parts) if parts else None,
        "sex": sex,
        "gender": sex,
        "race": race,
        "age": age,
        "booking_date": sent or off_date,
        "arrest_date": off_date or sent,
        "release_date": release,
        "agency": facility or "Texas TDCJ",
        "jurisdiction": "Texas TDCJ",
        "state": STATE,
        "county": county,
        "charge_description": offense,
        "case_number": case,
        "booking_id": tdcj or sid,
        "statute": clean(_get(row, "Offense Code", "offense code")),
        "source_id": f"tx_tdcj:{key}",
        "source_url": (
            f"https://inmate.tdcj.texas.gov/InmateSearch/viewDetail.action?sid={sid}"
            if sid
            else "https://inmate.tdcj.texas.gov/InmateSearch/start"
        ),
        "source_system": SOURCE,
        "raw_json": raw_json(
            {
                "tdcj": tdcj,
                "sid": sid,
                "sentence_years": years,
                "parole_status": clean(_get(row, "Parole Review Status")),
            }
        ),
    }
    return rec


def import_texas(
    data_dir: Path | str = Path("data/downloads/tx_tdcj"),
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
        log("Texas TDCJ: downloading High Value Dataset …")
        path = download_texas(data_dir, force=force_download)
    else:
        cands = list(data_dir.glob("*.xlsx")) + list(data_dir.glob("*.csv"))
        if not cands:
            raise FileNotFoundError(f"No Texas file under {data_dir}")
        path = max(cands, key=lambda p: p.stat().st_size)

    db = Database(database)
    totals = {"imported": 0, "skipped": 0, "skipped_identity": 0, "read": 0, "files": 1}
    batch: List[Dict[str, Any]] = []
    try:
        log(f"Reading {path.name} …")
        for row in _iter_rows(path):
            rec = map_tx_row(row)
            if not rec:
                continue
            batch.append(rec)
            totals["read"] += 1
            if limit and totals["read"] >= limit:
                break
            if len(batch) >= BATCH:
                flush_batch(db, batch, totals, force=force)
                if totals["read"] % 20000 == 0:
                    log(
                        f"  … read {totals['read']:,} imported {totals['imported']:,}"
                    )
        flush_batch(db, batch, totals, force=force)
    finally:
        db.close()
    return totals
