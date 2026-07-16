# Arrest Public Archiver — Module Map (short)

**Full catalog:** see **[SOURCE.md](SOURCE.md)** (every module, purpose, ≤200-line layout).

**Purpose:** Load only the code relevant to a task.  
**Rule:** Production `.py` files are **≤200 lines** (except `scraper/database_monolith_backup.py`).

> Do **not** open `*_monolith_backup.py` unless recovering pre-split code.  
> Ignore `data/`, `__pycache__/`, and live scraped HTML/photos.

---

## Architecture

```
Entry
├── gui.py → gui_app.shell.ArrestArchiverApp
├── Launch Arrest Archiver.vbs / run_gui.bat
└── python -m scraper → scraper.cli.main

gui_app/
├── shell.py, theme.py, widgets*.py, lazy_tabs.py, paths.py, resize_perf.py
├── auto_update.py, process_lifecycle.py
├── shared/          # record_sidebar*, export_card*
└── tabs/
    ├── browse/              # misclassify*, search, statistics, integrity
    │   └── deepface_reports/  # Browse → DeepFace hit review
    ├── recentlybooked/      # Live / Misclassify / Full Scrape (multi-host)
    ├── deepface/            # Scan + Setup
    ├── scrape.py            # Open-data only
    └── settings.py

scraper/
├── database/          # schema, inserts, queries*, dedupe*, deepface_scans*
├── mugshot_sources/   # registry + identity + load-balanced orchestrator
├── recentlybooked/    # RB crawl
├── mugshotscom/       # mugshots.com crawl
├── bustednewspaper/   # BN (SSL unavailable; fail-fast)
├── mugshot_ethnicity/ # DeepFace pipeline (setup*, scanner*, photo_quality*, …)
├── scrapers/          # Socrata / direct open-data
├── searcher*.py, ethnic_names*.py, charge_*.py
├── config*.py, cli*.py, app_settings.py, normalize.py
└── database_monolith_backup.py   # DO NOT USE in normal work
```

## Where to open first

| Task | Modules |
|------|---------|
| GUI shell | `gui_app/shell.py` |
| Browse / stated race | `gui_app/tabs/browse/misclassify*.py` |
| Live feed / multi-host | `gui_app/tabs/recentlybooked/`, `scraper/mugshot_sources/` |
| Offline HTTrack import | `scraper/recentlybooked/import_mirror.py` |
| Public DB download/upload | `scraper/db_sync*`, `scraper/db_publish_*`, `gui_app/shell_sync*` |
| Classification preserve on sync | `scraper/db_sync_preserve.py` |
| Full scrape load-balance | `mugshot_sources/partition.py`, `balanced.py`, `geo.py` |
| Surname misclass | `scraper/searcher*.py`, `ethnic_names*.py` |
| SQLite / dedupe | `scraper/database/` |
| DeepFace UI | `gui_app/tabs/deepface/` |
| DeepFace engine | `scraper/mugshot_ethnicity/` |
| CLI | `scraper/cli.py` + `cli_*.py` |

## Explicitly not ported from SOR

- NSOPW harvest  
- SOR jurisdiction report fetcher / verdict Reports  
- Cookie jar / CAPTCHA assist  

## Maintenance rule

If a file would exceed **200 lines**, extract a sibling module and keep a thin re-export for stable imports. Update **SOURCE.md** when adding packages.
