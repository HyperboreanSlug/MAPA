"""CLI commands: status, scrape, import, search."""
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
    print("has_names=yes -> best for ethnic misclassification analysis.\n")


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


def cmd_import_nc_dac(args: argparse.Namespace) -> None:
    from scraper.nc_dac.import_bulk import import_nc_dac_dir

    r = import_nc_dac_dir(
        args.input,
        database=args.database or "data/arrests.db",
        limit=int(args.limit or 0),
        force=bool(args.force),
        enrich_profile=not bool(args.no_profile),
        active_only=bool(getattr(args, "active_only", False)),
    )
    print(
        f"NC DAC import done: inmates_read={r['read']:,} "
        f"pp_read={r.get('supervision_read', 0):,} "
        f"imported={r['imported']:,} "
        f"(pp {r.get('supervision_imported', 0):,}) "
        f"skipped={r['skipped']:,} inactive={r.get('skipped_inactive', 0):,} "
        f"no_name={r.get('no_name', 0):,}"
    )


def cmd_import_state_bulk(args: argparse.Namespace) -> None:
    from scraper.state_bulk.import_all import import_state_bulk

    results = import_state_bulk(
        args.state or "all",
        database=args.database or "data/arrests.db",
        limit=int(args.limit or 0),
        force=bool(args.force),
        download=not bool(getattr(args, "no_download", False)),
        force_download=bool(getattr(args, "force_download", False)),
        data_root=getattr(args, "data_root", None) or "data/downloads",
        enrich=not bool(getattr(args, "no_enrich", False)),
    )
    total_imp = sum(r.get("imported", 0) for r in results.values())
    total_read = sum(r.get("read", 0) for r in results.values())
    print(
        f"State bulk done: sources={len(results)} read={total_read:,} "
        f"imported={total_imp:,}"
    )


def cmd_enrich_nc_dac(args: argparse.Namespace) -> None:
    from scraper.nc_dac.enrich_photos import enrich_nc_dac_photos

    r = enrich_nc_dac_photos(
        database=args.database or "data/arrests.db",
        output_root=args.photos or "data/photos/nc_dac",
        limit=int(args.limit or 0),
        delay=float(args.delay or 0.75),
        force=bool(args.force),
        active_only=bool(getattr(args, "active_only", False)),
        inmates_only=bool(getattr(args, "inmates_only", False)),
        missing_only=not bool(args.force),
    )
    print(
        f"NC DAC photo enrich: docs={r['docs_done']:,} "
        f"fetched={r['fetched']:,} cached={r['cached']:,} "
        f"no_photo={r['no_photo']:,} errors={r['errors']:,} "
        f"rows_updated={r['updated_rows']:,}"
    )


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
