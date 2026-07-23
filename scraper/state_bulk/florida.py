"""Florida DOC offender search scraper (named, with photo URLs)."""
from __future__ import annotations

import re
import string
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from scraper.config_types import USER_AGENT
from scraper.state_bulk.common import BATCH, clean, flush_batch, log, normalize_race, normalize_sex, raw_json

SOURCE = "fl_fdc"
STATE = "FL"
BASE = "https://pubapps.fdc.myflorida.com/OffenderSearch"
SEARCH_URL = f"{BASE}/Search.aspx?TypeSearch=AI"
DETAIL_URL = f"{BASE}/OffenderDetail.aspx?DCNumber="
PHOTO_URL = f"{BASE}/Photo.aspx?DCNumber="


class FDCClient:
    def __init__(self, delay: float = 1.5):
        self._s = requests.Session()
        self._s.headers["User-Agent"] = USER_AGENT
        self._delay = delay
        self._vs = ""
        self._ev = ""
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _refresh_tokens(self):
        time.sleep(self._delay)
        r = self._s.get(SEARCH_URL, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        vs = soup.select_one("#__VIEWSTATE")
        ev = soup.select_one("#__EVENTVALIDATION")
        self._vs = vs["value"] if vs else ""
        self._ev = ev["value"] if ev else ""

    def search(self, last: str, first: str) -> List[Dict[str, Any]]:
        for attempt in range(3):
            if self._cancel:
                return []
            if not self._vs:
                self._refresh_tokens()
            time.sleep(self._delay)
            data = {
                "ctl00$ContentPlaceHolder1$ScriptManager1_HiddenField": "",
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": self._vs,
                "__VIEWSTATEGENERATOR": "4046C2A2",
                "__SCROLLPOSITIONX": "0",
                "__SCROLLPOSITIONY": "0",
                "__VIEWSTATEENCRYPTED": "",
                "__EVENTVALIDATION": self._ev,
                "ctl00$ContentPlaceHolder1$txtLastName": last,
                "ctl00$ContentPlaceHolder1$txtFirstName": first,
                "ctl00$ContentPlaceHolder1$txtdcnumber": "",
                "ctl00$ContentPlaceHolder1$chkSearchaliases": "on",
                "ctl00$ContentPlaceHolder1$nophotos": "on",
                "ctl00$ContentPlaceHolder1$txtmatches": "50",
                "ctl00$ContentPlaceHolder1$btnSubmit2": "Submit Request",
            }
            try:
                r = self._s.post(SEARCH_URL, data=data, timeout=30)
                r.raise_for_status()
                return self._parse_results(r.text)
            except (requests.ConnectionError, requests.Timeout):
                time.sleep(3 * (attempt + 1))
                self._vs = ""
        return []

    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        grid = soup.select_one("#ctl00_ContentPlaceHolder1_grdList")
        if not grid:
            return []
        rows = grid.select("tr")[1:]
        out: List[Dict[str, Any]] = []
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            link = row.select_one("a[href*='DCNumber=']")
            dc_num = None
            if link:
                m = re.search(r"DCNumber=(\w+)", link.get("href", ""))
                if m:
                    dc_num = m.group(1)
            if len(cells) < 3:
                continue
            rec = self._map_row(cells, dc_num)
            if rec:
                out.append(rec)
        return out

    def _map_row(self, cells: List[str], dc_num: Optional[str]) -> Optional[Dict[str, Any]]:
        # Columns: [row#, name, DC#, race, sex, release, facility, DOB]
        name = clean(cells[1]) if len(cells) > 1 else None
        if not name:
            return None
        if not dc_num:
            dc_num = clean(cells[2]) if len(cells) > 2 else None
        race = normalize_race(clean(cells[3]) if len(cells) > 3 else None)
        sex = normalize_sex(clean(cells[4]) if len(cells) > 4 else None)
        release = clean(cells[5]) if len(cells) > 5 else None
        facility = clean(cells[6]) if len(cells) > 6 else None
        dob = clean(cells[7]) if len(cells) > 7 else None
        parts = name.split(",", 1)
        last = parts[0].strip().title()
        first = parts[1].strip().title() if len(parts) > 1 else None
        photo = f"{PHOTO_URL}{dc_num}" if dc_num else None
        return {
            "first_name": first,
            "last_name": last,
            "full_name": name.title(),
            "race": race,
            "sex": sex,
            "gender": sex,
            "agency": facility or "Florida DOC",
            "jurisdiction": "Florida DOC",
            "state": STATE,
            "release_date": release,
            "booking_id": dc_num,
            "photo_url": photo,
            "source_id": f"fl_fdc:{dc_num or name}",
            "source_url": f"{BASE}/detail.aspx?Page=Detail&DCNumber={dc_num}&TypeSearch=AI" if dc_num else SEARCH_URL,
            "source_system": SOURCE,
            "raw_json": raw_json({"dc_number": dc_num, "facility": facility, "dob": dob}),
        }


def _gen_prefixes() -> List[str]:
    """Generate last-name prefixes: A-Z, then AA-AZ, BA-BZ, ... ZZ."""
    single = list(string.ascii_uppercase)
    double = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]
    return single + double


def scrape_florida(
    *,
    database: str = "data/arrests.db",
    limit: int = 0,
    delay: float = 1.5,
    force: bool = False,
    max_prefixes: int = 0,
) -> Dict[str, int]:
    from scraper.database import Database

    client = FDCClient(delay=delay)
    db = Database(database)
    totals = {"imported": 0, "skipped": 0, "skipped_identity": 0, "read": 0, "prefixes": 0}
    batch: List[Dict[str, Any]] = []
    last_prefixes = _gen_prefixes()
    if max_prefixes:
        last_prefixes = last_prefixes[:max_prefixes]
    first_letters = list(string.ascii_uppercase)
    try:
        for last in last_prefixes:
            if client._cancel:
                break
            for first in first_letters:
                if client._cancel or (limit and totals["read"] >= limit):
                    break
                try:
                    results = client.search(last, first)
                except Exception as e:
                    log(f"  {last}/{first}: error {e}")
                    client._refresh_tokens()
                    continue
                if not results:
                    continue
                totals["prefixes"] += 1
                for rec in results:
                    batch.append(rec)
                    totals["read"] += 1
                    if limit and totals["read"] >= limit:
                        break
                if len(batch) >= BATCH:
                    flush_batch(db, batch, totals, force=force)
            if totals["prefixes"] and totals["prefixes"] % 26 == 0:
                log(f"  … last={last} read={totals['read']:,} imported={totals['imported']:,}")
            if limit and totals["read"] >= limit:
                break
        flush_batch(db, batch, totals, force=force)
    finally:
        db.close()
    log(f"FL FDC done: combos={totals['prefixes']} read={totals['read']:,} imported={totals['imported']:,}")
    return totals
