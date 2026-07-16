# Arrest Public Archiver

Download and archive **publicly published** U.S. arrest / booking open data (and RecentlyBooked.com public pages), then run **ethnic surname vs recorded-race** analysis and optional **DeepFace mugshot face/race** checks.

> **Primary purpose:** Find potential race/ethnicity misclassifications (e.g. Hispanic or Indian surnames recorded as White) in open arrest/booking datasets that include personal names and a race field.

> **Legal note:** Arrest ≠ conviction. Only ingest data jurisdictions already publish. Respect portal terms of use and rate limits. Do not commit CSVs, databases, mugshots, or archived HTML containing personal data to git.

## Features

- **Bulk open-data scrapers** (Socrata SODA + direct CSV)
- **RecentlyBooked.com** tab: live feed, full-site scrape, HTML + mugshot archive
- **SQLite** archive (`scraper/database/`) with merge dedupe
- **Surname misclassification** (primary) — ethnic surname + first/middle-name confidence
- **DeepFace** (optional) — local face/race gross-mismatch scan on archived mugshots
- **Charge categories** with Search / Misclassify filters
- Modular dark GUI (lazy tabs) + CLI

## Requirements

- Python 3.10+
- `pip install -r requirements.txt`
- Optional vision stack: `pip install -r requirements-vision.txt`

## Quick start

```bash
cd MAPA
pip install -r requirements.txt

python -m scraper status
python -m scraper scrape --named-only --limit 2000
python -m scraper misclassify --ethnicity hispanic
python -m scraper misclassify --ethnicity indian --charge sex_crimes

# RecentlyBooked (public HTML; polite delays)
python -m scraper recentlybooked live --import
python -m scraper recentlybooked scrape --state nj --county essex
python -m scraper recentlybooked misclassify --ethnicity hispanic

# Offline HTTrack mirror already on disk (no network)
python -m scraper recentlybooked import-mirror "I:\scrape\recentlybooked"
python -m scraper recentlybooked import-mirror "I:\scrape\recentlybooked" --state az --county apache
python -m scraper recentlybooked import-mirror "I:\scrape\recentlybooked" --limit 500

# Public database (GitHub Releases) — download on any install
# Settings → Public database, or startup auto-check when enabled.
# Upload is gated to the publisher machine only:
#   python scripts/enable_db_publish.py   # once, this machine only
#   python scripts/publish_database_release.py --use-gh
# Never copy data/db_publish.allow to other machines.
# Client downloads preserve local ethnicity_review / race_manual flags.

# DeepFace (after requirements-vision.txt)
python -m scraper mugshot setup
python -m scraper mugshot scan --source-system recentlybooked
```

### GUI

```bash
# Preferred on Windows (no console window):
#   double-click "Launch Arrest Archiver.vbs"

python gui.py
# or run_gui.bat (also used by the .vbs launcher via pythonw)
```

Tabs: **Browse** (Misclassify / Statistics / Search / Integrity / DeepFace review) · **RecentlyBooked** · **DeepFace** · **Scrape** · **Settings**.

See [MODULES.md](MODULES.md) for the module map.

### Charge categories

`sex_crimes` · `homicide` · `violent` · `weapons` · `robbery` · `burglary_be` ·  
`theft_property` · `drugs` · `dui_traffic` · `fraud_financial` · `domestic` ·  
`public_order` · `other` · `unknown`

## Data on disk (gitignored)

| Path | Contents |
|------|----------|
| `data/arrests.db` | SQLite archive |
| `data/html/recentlybooked/` | Archived booking HTML |
| `data/photos/recentlybooked/` | Downloaded mugshots |
| `data/app_settings.json` | GUI settings |

## Not included (SOR-only)

NSOPW harvest, state-registry report fetchers, and browser cookie/CAPTCHA jar are intentionally omitted.
