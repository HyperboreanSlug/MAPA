# Arrest Public Archiver — Module Map

**Purpose:** Load only the code relevant to a task.  
**Status:** Modular redesign (lazy GUI tabs + database package + RecentlyBooked + DeepFace).

> Do **not** open `*_monolith_backup.py` unless recovering pre-split code.  
> Ignore `data/`, `__pycache__/`, and live scraped HTML/photos.

---

## Architecture

```
Entry points
├── gui.py                 # Thin bootstrap → gui_app.shell.ArrestArchiverApp
├── Launch Arrest Archiver.vbs  # Double-click: no console (calls run_gui.bat)
├── run_gui.bat            # Core deps + start pythonw gui.py, then exit
└── python -m scraper      # CLI

gui_app/
├── theme.py, widgets.py, lazy_tabs.py, paths.py, resize_perf.py
├── shell.py               # Main window + tab host
├── shared/detail_drawer.py
└── tabs/
    ├── browse/            # Misclassify, Statistics, Search, Integrity, DeepFace review
    ├── recentlybooked.py  # Live Feed / Misclassify / Full Scrape
    ├── deepface.py        # Scan + Setup
    ├── scrape.py          # Open-data Socrata/direct
    └── settings.py

scraper/
├── database/              # SQLite mixins (schema, inserts, queries, dedupe, backup, deepface_scans)
├── recentlybooked/        # HTML client, catalog, parse, photos, archive_html, scraper
├── mugshot_ethnicity/     # DeepFace face/race (optional requirements-vision.txt)
├── searcher.py, ethnic_names.py, charge_classifications.py, normalize.py
├── config.py, cli.py, app_settings.py
└── scrapers/              # socrata, direct_download, base
```

## Main lazy tabs

| Tab | Role |
|-----|------|
| Browse | Surname misclass, stats, search, integrity, DeepFace hit review |
| RecentlyBooked | Live feed, RB misclass, full-site scrape (HTML + photos) |
| DeepFace | Mugshot gross-misclass scan + model setup |
| Scrape | Open-data portals (Socrata / direct CSV) |
| Settings | DB path, backups, scrape prefs, DeepFace prefs |

## Explicitly not ported from SOR

- NSOPW harvest
- SOR jurisdiction report fetcher / verdict Reports
- Cookie jar / CAPTCHA assist

## Review routing

| Task | Open |
|------|------|
| Surname misclass accuracy | `scraper/ethnic_names.py`, `scraper/searcher.py` |
| Charge filters | `scraper/charge_classifications.py` |
| DB schema / photos / HTML paths | `scraper/database/` |
| RecentlyBooked crawl | `scraper/recentlybooked/` |
| DeepFace scan | `scraper/mugshot_ethnicity/`, `gui_app/tabs/deepface.py` |
| GUI Browse | `gui_app/tabs/browse/` |
| CLI | `scraper/cli.py` |
