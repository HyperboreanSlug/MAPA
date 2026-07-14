# Arrest Public Archiver — Source Document

**Purpose:** Find the right module quickly, load only what you need, keep every unit ≤200 lines.  
**Hard rule:** Production `.py` modules are **≤200 lines** (excluding `data/`, `__pycache__`, and `scraper/database_monolith_backup.py`).  
**Status:** Modular layout (2026-07). Prefer this file over reading whole packages.

> **Do not open** `scraper/database_monolith_backup.py` unless recovering pre-split code.  
> **Ignore** `data/`, live HTML/photos, `__pycache__/`, and temporary `_*.py` probes.

---

## How to use this document

| Need | Open first |
|------|------------|
| GUI entry / window | `gui.py` → `gui_app/shell.py` |
| Browse (filters, review) | `gui_app/tabs/browse/` |
| Live feed / full scrape / multi-host | `gui_app/tabs/recentlybooked/` + `scraper/mugshot_sources/` |
| DeepFace scan UI | `gui_app/tabs/deepface/` |
| DeepFace browse review | `gui_app/tabs/browse/deepface_reports/` |
| Surname misclass engine | `scraper/searcher*.py`, `scraper/ethnic_names*.py` |
| SQLite archive | `scraper/database/` |
| RecentlyBooked crawl | `scraper/recentlybooked/` |
| Mugshots.com crawl | `scraper/mugshotscom/` |
| Busted Newspaper (unavailable) | `scraper/bustednewspaper/` |
| Open-data Socrata/CSV | `scraper/scrapers/`, `scraper/config*.py` |
| Face models / scan pipeline | `scraper/mugshot_ethnicity/` |
| CLI | `scraper/cli.py` + `scraper/cli_*.py` |
| Tests | `tests/test_smoke.py` → `tests/smoke/` |

**Token hygiene:** Load one ≤200-line module at a time. Use package `__init__.py` only to see public exports.

---

## Architecture (overview)

```
Entry
├── gui.py / Launch Arrest Archiver.vbs / run_gui.bat
└── python -m scraper          → scraper/__main__.py → scraper.cli.main

gui_app/                       # CustomTkinter UI (lazy tabs)
scraper/                       # Domain logic, scrapers, DB, analysis
tests/                         # Smoke suite split under tests/smoke/
```

**Composition pattern:** Large classes are multi-mixin compositions. Public import paths stay stable via thin re-export modules (e.g. `scraper/searcher.py`, `gui_app/tabs/deepface/__init__.py`).

---

## Entry points

| Module | Lines (≈) | Function |
|--------|----------:|----------|
| `gui.py` | ≤200 | Desktop bootstrap: deps check, launch `ArrestArchiverApp` |
| `run_gui.bat` | — | Install core deps, start `pythonw gui.py` |
| `Launch Arrest Archiver.vbs` | — | Double-click launcher (no console) |
| `scraper/__main__.py` | ≤10 | CLI entry: `python -m scraper` |
| `scraper/__init__.py` | ≤20 | Package marker / public re-exports |

---

## `gui_app/` — Desktop UI

### Core shell

| Module | Function |
|--------|----------|
| `gui_app/__init__.py` | Package marker |
| `gui_app/shell.py` | Main window, tab host registration, DB/settings lifecycle, log drain |
| `gui_app/process_lifecycle.py` | Hard shutdown: cancel flags, quit Tk, force-exit leftover threads |
| `gui_app/theme.py` | Colors, fonts, Treeview dark styling |
| `gui_app/lazy_tabs.py` | Build tab body only on first selection |
| `gui_app/paths.py` | Project root path |
| `gui_app/resize_perf.py` | Throttle CTk redraws during live resize |
| `gui_app/widgets.py` | Re-export of tree/chart/sort helpers |
| `gui_app/widgets_tree.py` | Treeview frame, stretch, row↔record binding |
| `gui_app/widgets_charts.py` | Bar/pie chart rendering (Pillow) |
| `gui_app/widgets_sort.py` | Column-sort helpers for trees |

### Shared widgets (`gui_app/shared/`)

| Module | Function |
|--------|----------|
| `record_sidebar.py` | Public `RecordSidebar` class (composition) |
| `record_sidebar_ui.py` | Layout: photo, fields, verdict buttons, actual-race combo |
| `record_sidebar_show.py` | `show` / `clear` / bind callbacks |
| `record_sidebar_photo.py` | Resolve path, async photo load |
| `record_sidebar_actions.py` | Open URL/HTML, export card, detail text |
| `record_sidebar_flags.py` | Merge `ethnicity_review` / `race_manual` into `flags` JSON |
| `verdict_persist.py` | Save + verify ethnicity_review flags to DB |
| `export_card.py` | Public API: `render_export_card`, `export_record_card_to_desktop` |
| `export_card_fields.py` | Name/location/crime/date extractors, fonts |
| `export_card_photo.py` | Mugshot load, seal watermark prep |
| `export_card_render.py` | Compose card image (including red race banner) |
| `detail_drawer.py` | Small detail drawer for Search |

### Browse tab (`gui_app/tabs/browse/`)

| Module | Function |
|--------|----------|
| `__init__.py` | `BrowseTabMixin` + sub-view registration |
| `misclassify.py` | Public `MisclassifyTabMixin` composition |
| `misclassify_constants.py` | Column labels + verification filter maps |
| `misclassify_suspect.py` | Filter rows to surname-vs-race misclass suspects |
| `misclassify_verdict.py` | Persist verification; correct → actual=stated race |
| `misclassify_build.py` | Filters UI (stated race, actual race, verification) |
| `misclassify_actions.py` | Refresh, verification save, actual-race save |
| `misclassify_export.py` | CSV export, row drop after filter change |
| `search.py` | Name/state/race/charge search UI |
| `statistics.py` | Archive stats charts |
| `integrity.py` | DB integrity / maintenance controls |
| `deepface_reports/` | Browse → DeepFace hit review package (below) |

### DeepFace Reports package (`gui_app/tabs/browse/deepface_reports/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Composes `DeepfaceReportsTabMixin` |
| `build.py` | Toolbar, metrics shell, layout |
| `build_list.py` | Hits Treeview |
| `build_review.py` | Review pane widgets |
| `data.py` | Load hits from SQLite |
| `filters.py` | Face/source/confidence filters, tree populate, metrics |
| `photo.py` | Mugshot path + canvas paint; placeholder flag |
| `review.py` | Selection + show orchestration |
| `review_fill.py` | Fill meta/photo from selected hit |
| `actions.py` | Open URL/HTML/photo, copy, verdict, next unreviewed |
| `ethnicity.py` | Ethnicity combo + handoff to “view as grid” |

### RecentlyBooked tab (`gui_app/tabs/recentlybooked/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Composes `RecentlyBookedTabMixin`; sub-tabs Live / Misclassify / Full Scrape |
| `constants.py` | Columns, source option loading, poll interval, BN hint |
| `common.py` | Name/hint/row_values, photo/race filters, split pane, append row |
| `verdicts.py` | Persist ethnicity review; apply verdict + list update |
| `live.py` | Live Feed bar UI, auto-update toggle |
| `live_sources.py` | Multi-select sources dropdown (checkboxes) |
| `live_filters.py` | Hide no-race/photo; rebuild tree; poll tick |
| `live_refresh.py` | Refresh orchestration + apply results to UI |
| `live_fetch.py` | Multi-source live poll + import + cross-source dedupe |
| `misclassify.py` | Stated-race filter UI + actual race |
| `misclassify_analyze.py` | Surname analysis worker for all mugshot hosts |
| `full_scrape.py` | Full scrape bar (source, state, county, threads, filters) |
| `full_scrape_run.py` | Validate inputs, save settings, start thread |
| `full_scrape_worker.py` | Background scrape worker body |
| `full_scrape_dispatch.py` | Dispatch RB / Mugshots.com / BN / load-balanced multi-host |
| `full_scrape_ui.py` | Per-record import + tree append |

### DeepFace tab (`gui_app/tabs/deepface/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Composes `DeepfaceTabMixin` (Scan + Setup sub-tabs) |
| `scan_build.py` | Tab shell + scan layout orchestration |
| `scan_build_form.py` | Scan option form (races, faces, confidence, source) |
| `scan_build_panels.py` | Hits tree, review pane, activity log UI |
| `scan_options.py` | Collect/save options, busy/stop/clear, log queue |
| `scan_photo.py` | Resolve/display mugshot in scan review |
| `scan_live.py` | Live preview while scanning; show hit details |
| `scan_review.py` | Verdicts, selection, next unreviewed, append hit row |
| `scan_run.py` | Start scan worker thread |
| `scan_export.py` | Scan callbacks, finish UI, CSV/JSON export |
| `setup_build.py` | Setup status/options/install buttons |
| `setup_build_weights.py` | Weight + detector checkbox UI |
| `setup_status.py` | Refresh DeepFace status + download badges |
| `setup_actions.py` | Save options, download weights, run install |
| `scroll_log.py` | Scroll binding, setup log, open log/weights dirs |

### Other tabs

| Module | Function |
|--------|----------|
| `gui_app/tabs/scrape.py` | Open-data scrape (Socrata / direct CSV; not mugshot hosts) |
| `gui_app/tabs/settings.py` | DB path, backups, scrape/RB/DeepFace prefs |

---

## `scraper/` — Domain logic

### Configuration & settings

| Module | Function |
|--------|----------|
| `config.py` | Re-export: `ArrestSource`, `SOURCES`, `get_source`, bulk/named helpers |
| `config_types.py` | `ArrestSource` dataclass, UA, delays, timeouts |
| `config_sources.py` | Tier-A open-data source definitions |
| `app_settings.py` | Load/save `data/app_settings.json` |
| `normalize.py` | Map vendor columns → canonical arrest fields |
| `charge_classifications.py` | Public charge classify API |
| `charge_rules.py` | Regex/category tables for charges |
| `charge_expand.py` | Expand jail abbreviations → full plain-language charges (details/card) |
| `charge_sanitize.py` | Reject non-charges (state names, bare case numbers); pick code/desc |
| `charge_sanitize_data.py` | State-name set and jail charge-code labels |
| `charge_admin.py` | Out-of-county / place-docket admin blobs (not offenses) |
| `charge_chrome.py` | Strip mugshots.com charges-table UI chrome; extract real offenses |
| `charge_recover.py` | Recover offense text from raw_json when charge is a stub |
| `charge_summary.py` | Standardized short labels for tables (expand then match) |
| `charge_summary_rules.py` | Compile summary rule tables |
| `charge_summary_rules_a.py` | Summary patterns (immigration through violent) |
| `charge_summary_rules_b.py` | Summary patterns (weapons through public order) |

### CLI

| Module | Function |
|--------|----------|
| `cli.py` | `main()` + argparse wiring |
| `cli_parser.py` | Build argument parser |
| `cli_cmds_data.py` | status, scrape, import, search |
| `cli_cmds_analysis.py` | misclassify, mugshot, dedupe, reclassify |
| `cli_cmds_rb.py` | recentlybooked live/scrape/misclassify |

### Search & surname analysis

| Module | Function |
|--------|----------|
| `searcher.py` | Public re-export (`ArrestSearcher`, race helpers) |
| `searcher_core.py` | `ArrestSearcher` search methods |
| `searcher_analyze.py` | `analyze_ethnicities` loop |
| `searcher_export.py` | Export misclass CSV + singleton |
| `searcher_race.py` | Canonical race keys, `format_race_label`, `_is_compatible` |
| `searcher_race_tables.py` | Alias / compatible-race tables |
| `searcher_names.py` | First/middle/last extractors; ethnicity review flags |
| `ethnic_names.py` | Public `EthnicNameDatabase` class |
| `ethnic_names_load.py` | Load JSON lists into structures |
| `ethnic_names_signals.py` | Given-name signals (Western / Indic / Slavic) |
| `ethnic_names_match.py` | Surname set membership helpers |
| `ethnic_names_classify.py` | `classify_by_name` orchestration |
| `ethnic_names_confidence.py` | Confidence scoring |
| `ethnic_names.json` | Data file (not code) |

### Database (`scraper/database/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Compose `Database` from mixins; `get_database` |
| `schema.py` | Connection, migrations, `existing_source_urls` |
| `constants.py` | Column lists, insert SQL, merge separator |
| `inserts.py` | Insert/import/update; identity-skip on import |
| `queries.py` | Thin re-export of search/stats mixins |
| `queries_search.py` | `search_records`, distinct labels |
| `queries_stats.py` | Counts, distributions, iterators |
| `csv_io.py` | CSV export helpers |
| `backup.py` | DB file backup on close |
| `dedupe.py` | Compose `DedupeMixin` |
| `dedupe_merge_fields.py` | Field union / richness helpers |
| `dedupe_merge.py` | Generic field-key dedupe (`source_url`, `name_dob`, …) |
| `dedupe_identity.py` | Name/DOB/photo identity keys |
| `dedupe_identity_find.py` | Find name+DOB+photo groups |
| `dedupe_identity_ops.py` | Remove name+DOB+photo dups, orphan photos |
| `dedupe_cross.py` | Cross-host dedupe + `existing_identity_keys` |
| `deepface_scans.py` | Facade for deepface_scans mixins |
| `deepface_scans_schema.py` | Table ensure / fingerprint |
| `deepface_scans_ops.py` | List/query hits |
| `deepface_scans_write.py` | Upsert scan rows |

### Multi-host mugshot registry (`scraper/mugshot_sources/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Public API re-exports |
| `registry.py` | Source catalog (RB, Mugshots.com, BN, blocked peers) |
| `identity.py` | `IdentityIndex`, `identity_keys_for_record` |
| `partition.py` | Round-robin county assignment across hosts |
| `types.py` | Callback type aliases |
| `result.py` | `MultiSourceResult` |
| `orchestrator.py` | `MultiSourceOrchestrator` core |
| `live.py` | Parallel live feeds per host |
| `balanced.py` | Load-balanced full scrape |
| `geo.py` | Discover counties; scrape one geo on one host |

### RecentlyBooked (`scraper/recentlybooked/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Package exports |
| `client.py` | Rate-limited HTTP |
| `catalog.py` | Discover states/counties (HTML + sitemap) |
| `live_feed.py` | Homepage feed fetch |
| `parse.py` | Re-export parsers |
| `parse_util.py` | Name parts, strong fields |
| `parse_detail.py` | Booking detail page |
| `parse_cards.py` | County/live listing cards |
| `photos.py` | Download mugshots; skip placeholders |
| `archive_html.py` | Save HTML under `data/html/` |
| `locked_set.py` | Thread-safe seen-URL set |
| `scraper.py` | Public `RecentlyBookedScraper` |
| `scraper_process.py` | Enrich one card (detail + photo + HTML) |
| `scraper_scrape.py` | live/county/state/all scrape methods |

### Mugshots.com (`scraper/mugshotscom/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Package exports |
| `client.py` | Rate-limited HTTP |
| `catalog.py` | US-States / county discovery |
| `parse.py` | Re-export parsers |
| `parse_detail.py` | Biographic detail page |
| `parse_charges.py` | Offense/charge extraction (never state names) |
| `parse_cards.py` | Listing + live cards |
| `photos.py` | Photo download to `data/photos/mugshotscom/` |
| `locked_set.py` | Thread-safe URL set |
| `scraper.py` | Public `MugshotsComScraper` |
| `scraper_enrich.py` | Enrich + live scrape |
| `scraper_county.py` | County/state/all scrapes |

### Busted Newspaper (`scraper/bustednewspaper/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Exports; documents SSL outage |
| `client.py` | HTTP client; fail-fast on SSL/remote disconnect |
| `client_outage.py` | `BustedNewspaperUnavailable`, outage messages |
| `catalog.py` | State/county discovery |
| `parse.py` | Re-export parsers |
| `parse_util.py` | Name/state helpers |
| `parse_detail.py` | Detail page |
| `parse_cards.py` | County cards |
| `photos.py` | Photo download |
| `scraper.py` | Public scraper class |
| `scraper_core.py` | Init/enrich/cancel helpers |
| `scraper_run.py` | County/state/all/live run loops |

### Open-data scrapers (`scraper/scrapers/`)

| Module | Function |
|--------|----------|
| `base.py` | `BaseScraper`, `ScraperFactory` |
| `socrata.py` | SODA API/CSV |
| `direct_download.py` | Direct bulk URL downloads |
| `bustednewspaper.py` | Legacy factory adapter (prefer mugshot_sources path) |

### DeepFace / mugshot ethnicity (`scraper/mugshot_ethnicity/`)

| Module | Function |
|--------|----------|
| `__init__.py` | Public scan/verify/setup exports |
| `models.py` | Dataclasses / face label constants |
| `labels.py` | Normalize face labels; contradict recorded race |
| `scorer.py` | Score one image via backend |
| `backends.py` | Re-export backend factory |
| `backends_base.py` | Protocol + MockBackend |
| `backends_deepface.py` | DeepFace Race backend |
| `backends_clip.py` | Optional CLIP backend |
| `photo_quality.py` | Re-export placeholder API |
| `photo_quality_hashes.py` | Known stub MD5 sets |
| `photo_quality_heuristics.py` | Silhouette / CrimeWatch heuristics |
| `photo_quality_api.py` | `is_placeholder_photo`, `bytes_non_mugshot_reason` |
| `photo_quality_resolve.py` | Resolve photo paths on disk |
| `scanner.py` | Re-export gross misclass scan |
| `scanner_helpers.py` | Race target matching helpers |
| `scanner_load.py` | Load records to scan |
| `scanner_candidates.py` | Build candidate list |
| `scanner_loop.py` | Scan orchestration |
| `scanner_loop_body.py` | Per-photo scan body |
| `verify.py` | Re-export verify API |
| `verify_record.py` | Single-record face+name verify |
| `verify_batch.py` | Batch over misclass list |
| `setup.py` | Re-export setup API |
| `setup_common.py` | Shared logging / env |
| `setup_runtime.py` | DeepFace import probes |
| `setup_pip.py` | Pip install helpers |
| `setup_install.py` | `ensure_deepface` install path |
| `setup_warm.py` | Weight download + model warm |
| `setup_warm_detector.py` | Detector warm-up |
| `weights_catalog.py` | Re-export catalog API |
| `weights_data.py` | Static detector/weight metadata |
| `weights_models.py` | Model option definitions |
| `weights_status.py` | Local download status / labels |

---

## Tests

| Module | Function |
|--------|----------|
| `tests/test_smoke.py` | Aggregator; loads `tests.smoke.*` |
| `tests/smoke/_path.py` | Ensure repo root on `sys.path` |
| `tests/smoke/database_core.py` | Import, search, dedupe |
| `tests/smoke/misclass_analyze.py` | Primary misclass paths |
| `tests/smoke/charge_filter.py` | Charge categories |
| `tests/smoke/normalize.py` | Field map |
| `tests/smoke/photo_quality.py` | Placeholder detection |
| `tests/smoke/recentlybooked_parse.py` | HTML fixtures |
| `tests/smoke/schema_v3.py` | Photo/HTML paths + deepface_scans |
| `tests/fixtures/*.html` | Parse fixtures (not code) |

---

## Data layout (runtime, not source)

| Path | Contents |
|------|----------|
| `data/arrests.db` | SQLite archive |
| `data/app_settings.json` | UI/scrape prefs |
| `data/html/recentlybooked/` | Archived booking HTML |
| `data/photos/recentlybooked/` | Mugshots (RB) |
| `data/photos/mugshotscom/` | Mugshots (mugshots.com) |
| `data/photos/bustednewspaper/` | Mugshots (BN, if ever reachable) |

---

## Design rules (for future edits)

1. **≤200 lines per module.** If a change would push past 200, extract a sibling module first.
2. **Stable public imports.** Add helpers under private modules; re-export only intentional API.
3. **Mixins compose on `ArrestArchiverApp`.** Don’t instantiate tab mixins alone without the shell.
4. **Scrapers never write DB directly** when used from GUI—callers import via `Database.import_records`.
5. **Cross-host identity** lives in `mugshot_sources.identity` + `database.dedupe_cross`; don’t invent a third key scheme.
6. **BN is fail-fast unavailable** until SSL is fixed outside the app (`bustednewspaper/client_outage.py`).
7. **Primary product purpose:** surname ethnicity vs stated race (`searcher` + `ethnic_names`), not open-data bulk alone.

---

## Quick “where do I change X?”

| Change | Module(s) |
|--------|-----------|
| Race banner on export card | `export_card_render.py` |
| Placeholder mugshot detection | `photo_quality_*.py` |
| Live Feed source checkboxes | `recentlybooked/live_sources.py` |
| Multi-host county split | `mugshot_sources/partition.py`, `balanced.py` |
| Skip duplicate person on import | `database/inserts.py` + `identity_keys_for_record` |
| Black+European not flagged | `searcher_race.py` (`_is_compatible`) |
| Stated race filter (browse) | `browse/misclassify_build.py` + `queries_search.py` |
| DeepFace default faces/recorded | `deepface/scan_build_form.py`, settings |
| Add a new mugshot host | `mugshot_sources/registry.py` + new package like `mugshotscom/` + `geo.py` dispatch |
| New open-data city | `config_sources.py` + field map |

---

## Verification checklist

```text
python -c "from gui_app.shell import ArrestArchiverApp; from scraper.database import Database; from scraper.searcher import ArrestSearcher; print('ok')"
python -m unittest tests.test_smoke -v
# Expect: Ran 19 tests … OK
# Expect: no production .py > 200 lines (except database_monolith_backup.py)
```

---

## Module count

Approximately **220** Python modules under the repo root (post-split), all production units ≤200 lines. Prefer navigating by this document rather than opening packages wholesale.
