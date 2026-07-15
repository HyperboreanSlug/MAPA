"""Ethnic name database for misclassification detection.

Methodology (important):
  * Surname alone is NEVER enough for high confidence on ambiguous names
    (e.g. Gill, Perera, Silva) that appear across multiple ethnic groups.
  * First names are scored together with surnames. Anglo first names
    (Amy, John, …) tank confidence for weak/ambiguous Indian surnames.
  * Hispanic first names (Alberto, Carlos, …) with Luso/Hispanic-overlapping
    surnames (Perera, Silva, …) prefer Hispanic / low Indian confidence.
  * Distinctive high-confidence Indian surnames (Patel, Singh, …) stay strong
    unless the first name strongly contradicts.
  * Asian: name analysis alone must not mark White as Asian unless the
    surname is *only Asian* (see ethnic_names_asian_unique.py) — not Lee/Park
    and not multi-family (e.g. Hispanic+Filipino, German+Bach).
  * Black: name analysis alone must not mark White as Black unless both
    first and last are Black-only (see ethnic_names_black_unique.py) —
    distinctive AA given name + uniquely Black/African surname (not
    DeShawn Washington; yes Jamal Adebayo).
"""
from __future__ import annotations


from scraper.ethnic_names_classify import EthnicNamesClassifyMixin
from scraper.ethnic_names_confidence import EthnicNamesConfidenceMixin
from scraper.ethnic_names_load import EthnicNamesLoadMixin
from scraper.ethnic_names_match import EthnicNamesMatchMixin
from scraper.ethnic_names_signals import EthnicNamesSignalsMixin


class EthnicNameDatabase(
    EthnicNamesConfidenceMixin,
    EthnicNamesClassifyMixin,
    EthnicNamesMatchMixin,
    EthnicNamesSignalsMixin,
    EthnicNamesLoadMixin,
):
    """Loads and queries ethnic surname + first-name databases."""


_ethnic_db = None


def get_ethnic_database() -> EthnicNameDatabase:
    """Get the singleton ethnic name database."""
    global _ethnic_db
    if _ethnic_db is None:
        _ethnic_db = EthnicNameDatabase()
    return _ethnic_db
