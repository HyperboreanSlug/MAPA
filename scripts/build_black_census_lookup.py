"""Rebuild scraper/ethnic_names_census_bw.json from the Census 2010 surname file.

Download: https://www2.census.gov/topics/genealogy/2010surnames/names.zip
Usage: python scripts/build_black_census_lookup.py <path-to-Names_2010Census.csv>
"""
import csv
import json
import os
import sys


def _fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main(csv_path: str) -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cen = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w, b = _fl(row["pctwhite"]), _fl(row["pctblack"])
            if w is not None and b is not None:
                cen[row["name"].lower()] = [w, b]

    with open(os.path.join(root, "scraper", "ethnic_names.json"), encoding="utf-8") as f:
        data = json.load(f)
    names = {n.lower() for n in data.get("african_american_surnames", [])}
    for region in data.get("african_surnames", {}).values():
        names.update(n.lower() for n in region)

    out = {n: cen[n] for n in sorted(names) if n in cen}
    dest = os.path.join(root, "scraper", "ethnic_names_census_bw.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, sort_keys=True)
    print(f"wrote {dest}: {len(out)} surnames ({len(names) - len(out)} not in census)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
