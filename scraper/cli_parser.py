"""Argparse construction for Arrest Public Archiver CLI."""
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
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

    pnc = sub.add_parser(
        "import-nc-dac",
        help="Import NC DAC bulk .dat tables (Inmate/Offender profiles)",
    )
    pnc.add_argument(
        "--input",
        "-i",
        default="data/downloads/nc_dac",
        help="Directory with INMT4AA1.dat/.des (and optional OFNT3AA1)",
    )
    pnc.add_argument("--limit", type=int, default=0, help="Max rows (0=all)")
    pnc.add_argument(
        "--active-only",
        action="store_true",
        help="Skip rows marked INACTIVE",
    )
    pnc.add_argument(
        "--no-profile",
        action="store_true",
        help="Do not join OFNT3AA1 height/weight/hair/eyes",
    )
    pnc.add_argument("--force", action="store_true")
    pnc.add_argument("--database", "-d", default="data/arrests.db")

    psb = sub.add_parser(
        "import-state-bulk",
        help="Import named state DOC bulk downloads (Illinois, Texas, …)",
    )
    psb.add_argument(
        "--state",
        default="all",
        help="illinois, texas, or all (comma-separated OK)",
    )
    psb.add_argument("--limit", type=int, default=0, help="Max rows per source (0=all)")
    psb.add_argument(
        "--no-download",
        action="store_true",
        help="Use files already under data/downloads/{il_idoc,tx_tdcj}",
    )
    psb.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download spreadsheets even if already present",
    )
    psb.add_argument("--force", action="store_true")
    psb.add_argument("--database", "-d", default="data/arrests.db")
    psb.add_argument(
        "--data-root",
        default="data/downloads",
        help="Root for state bulk folders",
    )
    psb.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip post-import photo enrichment",
    )

    penc = sub.add_parser(
        "enrich-nc-dac",
        help="Backfill NC DAC mugshots from public OPI (by DOC number)",
    )
    penc.add_argument("--limit", type=int, default=0, help="Max DOC candidates (0=all)")
    penc.add_argument(
        "--delay",
        type=float,
        default=0.75,
        help="Seconds between OPI photo requests (default 0.75)",
    )
    penc.add_argument(
        "--active-only",
        action="store_true",
        help="Only facility / ACTIVE admin rows (higher photo hit rate)",
    )
    penc.add_argument(
        "--inmates-only",
        action="store_true",
        help="Skip probation/parole bulk ids (nc_dac_pp:)",
    )
    penc.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even when photo_path is already set",
    )
    penc.add_argument(
        "--photos",
        default="data/photos/nc_dac",
        help="Directory for saved JPEGs",
    )
    penc.add_argument("--database", "-d", default="data/arrests.db")

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
    pm.add_argument(
        "--source-system",
        type=str,
        default="all",
        help="Limit to source_system (e.g. recentlybooked)",
    )
    pm.add_argument(
        "--race",
        type=str,
        default="all",
        help="Stated race filter (merged labels: White, Black, Hispanic, …; all=no filter)",
    )
    pm.add_argument("--database", "-d", default="data/arrests.db")

    pd = sub.add_parser(
        "dedupe",
        help="Find/remove duplicates (source_url + name+DOB; merges multi-state/charge)",
    )
    pd.add_argument("--remove", action="store_true")
    pd.add_argument("--dry-run", action="store_true")
    pd.add_argument(
        "--no-merge", action="store_true",
        help="Do not merge multi-state/multi-charge fields onto keeper",
    )
    pd.add_argument("--database", "-d", default="data/arrests.db")

    pr = sub.add_parser(
        "reclassify-charges",
        help="Backfill charge_category on all existing rows",
    )
    pr.add_argument("--database", "-d", default="data/arrests.db")

    _add_recentlybooked(sub, charge_choices)
    _add_mugshot(sub)
    return p


def _add_recentlybooked(sub: argparse._SubParsersAction, charge_choices) -> None:
    prb = sub.add_parser(
        "recentlybooked",
        help="RecentlyBooked.com live feed / scrape / misclassify",
    )
    prb_sub = prb.add_subparsers(dest="rb_action", required=True)
    prb_live = prb_sub.add_parser("live", help="Fetch homepage recent bookings")
    prb_live.add_argument("--import", dest="do_import", action="store_true")
    prb_live.add_argument("--force", action="store_true")
    prb_live.add_argument("--no-photos", action="store_true")
    prb_live.add_argument("--no-html", action="store_true")
    prb_live.add_argument("--delay", type=float, default=1.0)
    prb_live.add_argument("--database", "-d", default="data/arrests.db")

    prb_sc = prb_sub.add_parser("scrape", help="Scrape state/county/all")
    prb_sc.add_argument("--state", type=str)
    prb_sc.add_argument("--county", type=str)
    prb_sc.add_argument("--all", action="store_true")
    prb_sc.add_argument("--limit-counties", type=int, default=0)
    prb_sc.add_argument("--max-pages", type=int, default=0)
    prb_sc.add_argument("--force", action="store_true")
    prb_sc.add_argument("--no-photos", action="store_true")
    prb_sc.add_argument("--no-html", action="store_true")
    prb_sc.add_argument("--delay", type=float, default=1.0)
    prb_sc.add_argument("--threads", type=int, default=1, help="Parallel workers (1–32)")
    prb_sc.add_argument("--database", "-d", default="data/arrests.db")

    prb_mc = prb_sub.add_parser("misclassify", help="Surname misclass for RB rows")
    prb_mc.add_argument("--ethnicity", default="all")
    prb_mc.add_argument(
        "--race",
        default="all",
        help="Stated race filter (White, Black, …; all=no filter)",
    )
    prb_mc.add_argument("--charge", default="all", choices=charge_choices)
    prb_mc.add_argument("--confidence", type=float, default=0.5)
    prb_mc.add_argument("--limit", type=int, default=0)
    prb_mc.add_argument("--max-display", type=int, default=30)
    prb_mc.add_argument("--export", type=str)
    prb_mc.add_argument(
        "--source-system",
        default="recentlybooked",
        help="Source system (recentlybooked, bustednewspaper, …)",
    )
    prb_mc.add_argument("--database", "-d", default="data/arrests.db")

    prb_im = prb_sub.add_parser(
        "import-mirror",
        help="Import offline HTTrack mirror of recentlybooked.com from disk",
    )
    prb_im.add_argument(
        "mirror_path",
        type=str,
        help=r"Mirror root (e.g. I:\scrape\recentlybooked or …\https@recentlybooked.com)",
    )
    prb_im.add_argument("--state", type=str, help="Limit to one state code (e.g. az)")
    prb_im.add_argument("--county", type=str, help="Limit to one county slug")
    prb_im.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max detail pages to consider (0 = all)",
    )
    prb_im.add_argument("--force", action="store_true", help="Re-import existing source_url")
    prb_im.add_argument("--no-photos", action="store_true")
    prb_im.add_argument("--no-html", action="store_true")
    prb_im.add_argument(
        "--allow-no-photo",
        action="store_true",
        help="Import rows even when no real mugshot file is available",
    )
    prb_im.add_argument("--database", "-d", default="data/arrests.db")


def _add_mugshot(sub: argparse._SubParsersAction) -> None:
    pmug = sub.add_parser("mugshot", help="DeepFace face/race scan (optional vision deps)")
    pmug_sub = pmug.add_subparsers(dest="mugshot_action", required=True)
    pmug_setup = pmug_sub.add_parser("setup", help="Install DeepFace + Race weights")
    pmug_setup.add_argument("--detector", default="retinaface")
    pmug_scan = pmug_sub.add_parser("scan", help="Gross face vs recorded-race scan")
    pmug_scan.add_argument("--confidence", type=float, default=0.85)
    pmug_scan.add_argument("--limit", type=int, default=0)
    pmug_scan.add_argument("--state", type=str)
    pmug_scan.add_argument("--source-system", type=str, default="")
    pmug_scan.add_argument("--faces", default="black,indian,asian")
    pmug_scan.add_argument("--recorded", default="WHITE")
    pmug_scan.add_argument("--force-rescan", action="store_true")
    pmug_scan.add_argument("--database", "-d", default="data/arrests.db")
    pmug_ver = pmug_sub.add_parser("verify", help="Verify surname misclass with face scores")
    pmug_ver.add_argument("--confidence", type=float, default=0.5)
    pmug_ver.add_argument("--limit", type=int, default=50)
    pmug_ver.add_argument("--source-system", type=str, default="")
    pmug_ver.add_argument("--database", "-d", default="data/arrests.db")
