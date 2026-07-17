"""CLI commands: misclassify, mugshot, dedupe, reclassify."""
from __future__ import annotations

import argparse


def cmd_misclassify(args: argparse.Namespace) -> None:
    """Primary purpose: ethnic surname vs recorded race mismatches."""
    from .charge_classifications import category_label
    from .searcher import ArrestSearcher

    s = ArrestSearcher(args.database or "data/arrests.db")
    eth = None if (args.ethnicity or "all") == "all" else args.ethnicity
    charge = None if (args.charge or "all") == "all" else args.charge
    src = getattr(args, "source_system", None)
    if src in (None, "", "all"):
        src = None
    race = getattr(args, "race", None)
    if race in (None, "", "all"):
        race = None
    print("\n" + "=" * 60)
    print("  Ethnic misclassification analysis (PRIMARY PURPOSE)")
    print("=" * 60)
    print(f"  DB records: {s.get_total_count():,}")
    print(f"  Ethnicity filter: {args.ethnicity}")
    print(f"  Stated race filter: {race or 'all'}")
    print(f"  Charge filter: {args.charge}")
    print(f"  Source system: {src or 'all'}")
    print(f"  Min confidence: {args.confidence}")
    print("  Note: only rows with names are analyzed.\n")
    try:
        results, base = s.analyze_ethnicities(
            min_confidence=args.confidence,
            limit=args.limit,
            ethnicity_filter=eth,
            charge_category=charge,
            source_system=src,
            race=race,
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
                source_system=src,
                race=race,
                min_confidence=args.confidence,
                limit=args.limit,
            )
            print(f"\n  Exported {n} → {args.export}")
    finally:
        s.close()
    print("=" * 60 + "\n")


def cmd_mugshot(args: argparse.Namespace) -> None:
    action = args.mugshot_action
    db_path = args.database or "data/arrests.db"

    if action == "setup":
        from .mugshot_ethnicity.setup import (
            download_selected_weights,
            ensure_deepface,
            ensure_fairface,
        )

        def _log(m: str) -> None:
            print(m)

        ff_ok = ensure_fairface(auto_install=True, warm=True, log=_log)
        df_ok = ensure_deepface(auto_install=True, warm=False, log=_log)
        if df_ok:
            download_selected_weights(
                ["Race"], detector_backend=args.detector or "retinaface", log=_log
            )
        if ff_ok or df_ok:
            print(
                f"Vision setup OK (FairFace={'yes' if ff_ok else 'no'}, "
                f"DeepFace={'yes' if df_ok else 'no'})"
            )
        else:
            print(
                "Vision setup failed — install face-race (FairFace) and/or "
                "pip install -r requirements-vision.txt"
            )
        return

    if action == "scan":
        from .mugshot_ethnicity import scan_gross_misclassifications

        def _log(m: str) -> None:
            print(m)

        faces = [x.strip() for x in (args.faces or "black,indian,asian").split(",") if x.strip()]
        recorded = [x.strip() for x in (args.recorded or "WHITE").split(",") if x.strip()]
        hits = scan_gross_misclassifications(
            db_path=db_path,
            min_confidence=float(args.confidence or 0.85),
            limit=int(args.limit or 0),
            state=args.state or None,
            source_system=args.source_system or None,
            face_labels=faces,
            recorded_races=recorded,
            force_rescan=bool(args.force_rescan),
            log=_log,
        )
        print(f"Hits: {len(hits)}")
        for h in hits[:30]:
            rec = h.record or {}
            print(
                f"  id={rec.get('id')} {rec.get('first_name')} {rec.get('last_name')} "
                f"race={h.recorded_race} face={h.predicted_label}@{h.confidence:.2f}"
            )
        return

    if action == "verify":
        from .mugshot_ethnicity import verify_misclassifications
        from .searcher import ArrestSearcher

        s = ArrestSearcher(db_path)
        try:
            mcs = s.analyze_ethnicities(
                min_confidence=float(args.confidence or 0.5),
                limit=int(args.limit or 50),
                source_system=args.source_system or None,
            )
        finally:
            s.close()
        results = verify_misclassifications(mcs, backend="auto")
        for vr in results[:30]:
            print(vr)
        return

    print(f"Unknown mugshot action: {action}")


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
            r = db.remove_duplicates_all(
                ["source_url", "name_dob"],
                dry_run=args.dry_run,
                merge_fields=not args.no_merge,
            )
            print(r)
        else:
            for strat in ("source_url", "name_dob"):
                try:
                    groups = db.find_duplicate_groups(strat)
                except ValueError:
                    continue
                extra = sum(g["count"] - 1 for g in groups)
                print(f"{strat}: groups={len(groups):,}  extra_rows={extra:,}")
                for g in groups[:8]:
                    print(f"  {str(g['key'])[:70]}  x{g['count']}")
    finally:
        db.close()
