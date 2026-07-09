# Arrest Public Archiver

Download and archive **publicly published** U.S. arrest / booking open data, then run **ethnic surname vs recorded-race misclassification** analysis.

> **Primary purpose:** Find potential race/ethnicity misclassifications (e.g. Hispanic or Indian surnames recorded as White) in open arrest/booking datasets that include personal names and a race field.

> **Legal note:** Arrest ≠ conviction. Only ingest data jurisdictions already publish. Respect portal terms of use and rate limits. Do not commit CSVs or databases containing personal data to git. Records may be incomplete, sealed, or wrong.

There is **no national bulk named-arrest feed**. Coverage is city/county open-data portals (Socrata, etc.). Prefer sources marked **names=yes** for misclassification work.

## Features

- **Bulk open-data scrapers** (Socrata SODA + direct CSV)
- **SQLite** archive with import / enhanced dedupe (merge multi-state + multi-charge)
- **Misclassification analysis** (primary) — same ethnic surname + **first-name confidence** as SOR archiver
- **Charge categories** (sex crimes, B&E, drugs, …) with filters
- **Statistics** tab: misclassified-as **Black / White / Other**, by ethnicity, by charge
- **Search**, integrity, CLI + dark GUI (sortable columns)
- Source catalog with `has_names` flag

## Requirements

- Python 3.10+
- `pip install -r requirements.txt`

## Quick start

```bash
cd arrest-public-archiver
pip install -r requirements.txt

# List sources (prefer has_names=yes for misclass)
python -m scraper status

# Download named open-data feeds + import to DB
python -m scraper scrape --named-only --limit 2000

# PRIMARY: ethnic misclassification (optional charge filter)
python -m scraper misclassify --ethnicity hispanic
python -m scraper misclassify --ethnicity indian --charge sex_crimes
python -m scraper misclassify --charge burglary_be --export data/misclass_be.csv

# Search by name and/or charge category
python -m scraper search --name Garcia
python -m scraper search --charge sex_crimes
python -m scraper search --charge drugs --limit 50

# Backfill categories on old rows; dedupe
python -m scraper reclassify-charges
python -m scraper dedupe
```

### Charge categories

Keyword classifier on charge text (stored as `charge_category`):

`sex_crimes` · `homicide` · `violent` · `weapons` · `robbery` · `burglary_be` (B&E) ·  
`theft_property` · `drugs` · `dui_traffic` · `fraud_financial` · `domestic` ·  
`public_order` · `other` · `unknown`

Use `--charge` / GUI **Charge** combo on Misclassify and Search.

### GUI

```bash
python gui.py
```

Tabs: **Misclassify** (first) · Scrape · Search · Integrity · Settings.

## MVP open-data sources

| ID | Jurisdiction | Names | Notes |
|----|--------------|-------|--------|
| `montgomery_md_arrests` | Montgomery Co, MD | yes | Strong misclass feed |
| `king_wa_bookings` | King Co, WA jail bookings | yes | Strong misclass feed |
| `la_arrests` | Los Angeles PD | often no | Race/charge stats; field map may need live tweak |
| `chicago_arrests` | Chicago PD | often limited | Public export may omit names |
| `seattle_arrests` | Seattle PD | check | Open arrest data |
| `sf_arrests` | San Francisco | check | Often incident-centric |

Field maps live in `scraper/config.py` and may need adjustment after a live schema pull.

## Architecture

```
scraper/config.py          source catalog
scraper/scrapers/socrata.py  SODA pagination
scraper/database.py        arrests table
scraper/searcher.py        misclassification (primary)
scraper/ethnic_names.*     surname lists
gui.py                     CustomTkinter UI
```

## Related project

Sex offender registry counterpart: [sor-public-archiver](https://github.com/HyperboreanSlug/sor-public-archiver).

## License

MIT — see `LICENSE`.
