"""Public U.S. arrest/booking open-data archiver with ethnic misclassification analysis."""

from .database import Database, get_database
from .searcher import SexOffenderSearcher as ArrestSearcher, get_searcher
from .ethnic_names import EthnicNameDatabase, get_ethnic_database

__version__ = "0.2.0"

__all__ = [
    "Database",
    "get_database",
    "ArrestSearcher",
    "get_searcher",
    "EthnicNameDatabase",
    "get_ethnic_database",
    "__version__",
]
