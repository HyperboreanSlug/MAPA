"""Static tables for charge sanitization (state names, jail codes)."""
from __future__ import annotations

# US full state names (and DC) — never valid as a charge description alone.
STATE_NAMES = frozenset(
    {
        "alabama",
        "alaska",
        "arizona",
        "arkansas",
        "california",
        "colorado",
        "connecticut",
        "delaware",
        "district of columbia",
        "florida",
        "georgia",
        "hawaii",
        "idaho",
        "illinois",
        "indiana",
        "iowa",
        "kansas",
        "kentucky",
        "louisiana",
        "maine",
        "maryland",
        "massachusetts",
        "michigan",
        "minnesota",
        "mississippi",
        "missouri",
        "montana",
        "nebraska",
        "nevada",
        "new hampshire",
        "new jersey",
        "new mexico",
        "new york",
        "north carolina",
        "north dakota",
        "ohio",
        "oklahoma",
        "oregon",
        "pennsylvania",
        "rhode island",
        "south carolina",
        "south dakota",
        "tennessee",
        "texas",
        "utah",
        "vermont",
        "virginia",
        "washington",
        "west virginia",
        "wisconsin",
        "wyoming",
    }
)

# Two-letter codes are never valid as a lone charge.
STATE_ABBREVS = frozenset(
    {
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "dc",
        "fl", "ga", "hi", "id", "il", "in", "ia", "ks",
        "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
        "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny",
        "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
        "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
        "wi", "wy",
    }
)

NA_VALUES = frozenset(
    {
        "",
        "n/a",
        "na",
        "none",
        "null",
        "unknown",
        "no data",
        "no data to display",
        "not available",
        "—",
        "-",
    }
)

# Common jail charge codes → plain language (when description is unusable).
CODE_LABELS = {
    "WARR": "Warrant",
    "WARRANT": "Warrant",
    "BW": "Bench Warrant",
    "FTA": "Failure to Appear",
    "FTP": "Failure to Pay",
    "HOLD": "Hold",
    "BOND": "Bond",
    "PROB": "Probation",
    "PV": "Probation Violation",
    "ICE": "Immigration Hold",
    "IMM": "Immigration Hold",
    "COURT ORDER": "Court Order",
    "CO": "Court Order",
}
