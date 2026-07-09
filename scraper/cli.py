"""CLI for Arrest Public Archiver — misclassification-first."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def cmd_status(_args: argparse.Namespace) -> None:
    from .config import SOURCES

    print(f"\n{'ID':<24} {'Method':<10} {'Names?':<7} {'State':<5} Name")
    print("-" * 80)
    for s in SOURCES:
        print(
            f"{s.id:<24} {s.scrape_method:<10} "
            f"{'yes' if s.has_names else 'no':<7} {s.state:<5} {s.name}"
        )
    print("-" * 80)
    print("has_names=yes → best for ethnic misclassification analysis.\n")


def cmd_scrape(args: argparse.Namespace) -> None:
    from .config import get_bulk_sources, get_source
    from .database import Database
    from .scrapers.base import ScraperFactory

    if args.all_bulk:
        sources = get_bulk_sources()
    elif args.named_only:
        from .config import get_named_sources

        sources = get_named_sources()
    elif args.source:
        src = get_source(args.source)
        if not src:
            print(f"Unknown source: {args.source}")
            return
        sources = [src]
    else:
        print("Specify --source ID, --all-bulk, or --named-only (preferred for misclass).")
        return

    out_dir = Path(args.output or "data/downloads")
    out_dir.mkdir(parents=True, exist_ok=True)
    row_limit = int(args.limit or 0)
    do_import = not args.no_import
    db_path = args.database or "data/arrests.db"
    total_imp = 0

    for src in sources:
        print(f"\n[{src.id}] {src.name} ({src.scrape_method}) names={src.has_names}")
        try:
            scraper = ScraperFactory.create(src.id, delay=args.delay)
            try:
                records = scraper.scrape(row_limit=row_limit)
                if not records:
                    print("  No records returned")
                else:
                    path = scraper.scrape_to_file(out_dir, row_limit=row_limit)
                    # scrape_to_file re-fetches; avoid double network when we already have rows
                    # Write CSV from in-memory records instead
                    import csv as _csv
                    out_dir.mkdir(parents=True, exist_ok=True)
                    path = out_dir / f"{src.id}.csv"
                    fields = []
                    seen = set()
                    for rec in records:
                        for k in rec:
                            if k not in seen:
                                seen.add(k)
                                fields.append(k)
                    with open(path, "w", newline="", encoding="utf-8") as fh:
                        w = _csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                        w.writeheader()
                        w.writerows(records)
                    print(f"  Saved {len(records)} → {path}")
            finally:
                scraper.close()

            if do_import and records:
                db = Database(db_path)
                try:
                    r = db.import_records(records, skip_existing_urls=not args.force)
                    print(
                        f"  DB import +{r['imported']} "
                        f"(skipped {r['skipped']}) → {db_path}"
                    )
                    total_imp += r["imported"]
                finally:
                    db.close()
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone. Imported total: {total_imp}")
    if total_imp:
        print("Next: python -m scraper misclassify --ethnicity all")


def cmd_import(args: argparse.Namespace) -> None:
    from .database import Database
    from .normalize import apply_field_map, stamp_source

    db = Database(args.database or "data/arrests.db")
    path = Path(args.input)
    files = [path] if path.is_file() else sorted(path.glob("*.csv"))
    if not files:
        print(f"No CSV at {path}")
        db.close()
        return
    total = 0
    try:
        for f in files:
            with open(f, encoding="utf-8", errors="replace") as fh:
                rows = list(csv.DictReader(fh))
            recs = []
            for row in rows:
                rec = apply_field_map(row, {})
                rec = stamp_source(
                    rec,
                    source_id=f.stem,
                    state=args.state or rec.get("state") or "",
                    jurisdiction=rec.get("jurisdiction") or f.stem,
                )
                recs.append(rec)
            r = db.import_records(recs, skip_existing_urls=not args.force)
            print(f"{f.name}: +{r['imported']} (skipped {r['skipped']})")
            total += r["imported"]
    finally:
        db.close()
    print(f"Total imported: {total}")


def cmd_search(args: argparse.Namespace) -> None:
    from .charge_classifications import category_label
    from .searcher import ArrestSearcher

    s = ArrestSearcher(args.database or "data/arrests.db")
    charge = None if (args.charge or "all") == "all" else args.charge
    try:
        if args.name or charge or args.race or args.state:
            res = s.search(
                name=args.name,
                state=args.state,
                race=args.race,
                charge_category=charge,
                limit=args.limit,
            )
            print(f"Found {len(res.records)} ({res.query_time_ms:.0f} ms)")
            for r in res.records[:50]:
                name = (
                    f"{r.get('first_name') or ''} {r.get('last_name') or ''}"
                ).strip() or r.get("full_name") or "—"
                cat = r.get("charge_category") or ""
                print(
                    f"  {name:<28} race={r.get('race') or '—':<10} "
                    f"cat={category_label(cat) if cat else '—':<18} "
                    f"charge={(r.get('charge_description') or '')[:36]}"
                )
        else:
            print(f"Total records: {s.get_total_count():,}")
            print("Race distribution:")
            for d in s.get_race_distribution()[:12]:
                print(f"  {d.get('race') or '—':<20} {d.get('count'):,}")
            print("Charge categories:")
            for d in s.get_charge_category_distribution()[:15]:
                print(f"  {d.get('label') or d.get('category'):<28} {d.get('count'):,}")
    finally:
        s.close()


def cmd_misclassify(args: argparse.Namespace) -> None:
    """Primary purpose: ethnic surname vs recorded race mismatches."""
    from .charge_classifications import category_label
    from .searcher import ArrestSearcher

    s = ArrestSearcher(args.database or "data/arrests.db")
    eth = None if (args.ethnicity or "all") == "all" else args.ethnicity
    charge = None if (args.charge or "all") == "all" else args.charge
    print("\n" + "=" * 60)
    print("  Ethnic misclassification analysis (PRIMARY PURPOSE)")
    print("=" * 60)
    print(f"  DB records: {s.get_total_count():,}")
    print(f"  Ethnicity filter: {args.ethnicity}")
    print(f"  Charge filter: {args.charge}")
    print(f"  Min confidence: {args.confidence}")
    print("  Note: only rows with names are analyzed.\n")
    try:
        results, base = s.analyze_ethnicities(
            min_confidence=args.confidence,
            limit=args.limit,
            ethnicity_filter=eth,
            charge_category=charge,
            return_base_count=True,
            named_only=True,
        )
        rate = (len(results) / base * 100.0) if base else 0.0
        print(
            f"  Surname matches (base): {base:,}\n"
            f"  Potential misclassifications: {len(results):,} ({rate:.1f}% of base)\n"
        )
        for mc in results[: args.max_display]:
            rec = mc.record or {}
            name = (
                f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
            ).strip() or rec.get("full_name") or "—"
            cat = rec.get("charge_category") or ""
            print(
                f"  {name:<26} race={mc.expected_race:<10} "
                f"likely={mc.likely_ethnicity:<16} conf={mc.confidence:.2f}  "
                f"[{category_label(cat) if cat else '—'}] "
                f"{(rec.get('charge_description') or '')[:28]}"
            )
        if args.export:
            n = s.export_misclassifications(
                args.export,
                ethnicity_filter=eth,
                charge_category=charge,
                min_confidence=args.confidence,
                limit=args.limit,
            )
            print(f"\n  Exported {n} → {args.export}")
    finally:
        s.close()
    print("=" * 60 + "\n")


def cmd_reclassify(args: argparse.Namespace) -> None:
    """Backfill charge_category on existing DB rows."""
    from .database import Database

    db = Database(args.database or "data/arrests.db")
    try:
        n = db.reclassify_charges()
        dist = db.get_charge_category_distribution()
    finally:
        db.close()
    print(f"Reclassified {n:,} rows.")
    for d in dist:
        print(f"  {d['label']:<28} {d['count']:,}")


def cmd_dedupe(args: argparse.Namespace) -> None:
    from .database import Database

    db = Database(args.database or "data/arrests.db")
    try:
        if args.remove:
            r = db.remove_duplicates("source_url", dry_run=args.dry_run)
            print(r)
        else:
            groups = db.find_duplicate_groups("source_url")
            extra = sum(g["count"] - 1 for g in groups)
            print(f"Groups: {len(groups):,}  extra rows: {extra:,}")
            for g in groups[:15]:
                print(f"  {g['key'][:70]}  x{g['count']}")
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Arrest Public Archiver — download public arrest/booking open data "
            "and find ethnic surname vs race misclassifications."
        )
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="List configured sources")

    ps = sub.add_parser("scrape", help="Download bulk open-data sources")
    ps.add_argument("--source", type=str, help="Source id (see status)")
    ps.add_argument("--all-bulk", action="store_true", help="All verified bulk sources")
    ps.add_argument(
        "--named-only",
        action="store_true",
        help="Only sources with personal names (best for misclassification)",
    )
    ps.add_argument("--output", default="data/downloads")
    ps.add_argument("--limit", type=int, default=0, help="Max rows per source (0=default/all)")
    ps.add_argument("--delay", type=float, default=1.0)
    ps.add_argument("--no-import", action="store_true")
    ps.add_argument("--force", action="store_true", help="Do not skip existing source_url")
    ps.add_argument("--database", "-d", default="data/arrests.db")

    pi = sub.add_parser("import", help="Import CSV into database")
    pi.add_argument("--input", "-i", default="data/downloads")
    pi.add_argument("--state", type=str)
    pi.add_argument("--force", action="store_true")
    pi.add_argument("--database", "-d", default="data/arrests.db")

    from .charge_classifications import list_category_choices

    charge_choices = list_category_choices(include_all=True)

    pse = sub.add_parser("search", help="Search local arrest DB")
    pse.add_argument("--name", type=str)
    pse.add_argument("--state", type=str)
    pse.add_argument("--race", type=str)
    pse.add_argument(
        "--charge",
        type=str,
        default="all",
        choices=charge_choices,
        help="Charge category filter (sex_crimes, burglary_be, drugs, …)",
    )
    pse.add_argument("--limit", type=int, default=100)
    pse.add_argument("--database", "-d", default="data/arrests.db")

    pm = sub.add_parser(
        "misclassify",
        help="PRIMARY: find ethnic surname vs recorded-race mismatches",
    )
    pm.add_argument(
        "--ethnicity",
        default="all",
        choices=[
            "all", "hispanic", "asian", "indian", "indian_high_confidence",
            "african_american", "arabic", "jewish", "portuguese",
            "native_american", "european",
        ],
    )
    pm.add_argument(
        "--charge",
        type=str,
        default="all",
        choices=charge_choices,
        help="Only analyze rows in this charge category",
    )
    pm.add_argument("--confidence", type=float, default=0.5)
    pm.add_argument("--limit", type=int, default=0, help="0 = scan all named rows")
    pm.add_argument("--max-display", type=int, default=30)
    pm.add_argument("--export", type=str)
    pm.add_argument("--database", "-d", default="data/arrests.db")

    pd = sub.add_parser("dedupe", help="Find/remove duplicate source_url rows")
    pd.add_argument("--remove", action="store_true")
    pd.add_argument("--dry-run", action="store_true")
    pd.add_argument("--database", "-d", default="data/arrests.db")

    pr = sub.add_parser(
        "reclassify-charges",
        help="Backfill charge_category on all existing rows",
    )
    pr.add_argument("--database", "-d", default="data/arrests.db")

    args = p.parse_args()
    {
        "status": cmd_status,
        "scrape": cmd_scrape,
        "import": cmd_import,
        "search": cmd_search,
        "misclassify": cmd_misclassify,
        "dedupe": cmd_dedupe,
        "reclassify-charges": cmd_reclassify,
    }[args.command](args)


if __name__ == "__main__":
    main()
