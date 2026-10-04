"""Browse actions. Re-export split mixins."""
from __future__ import annotations

from gui_app.tabs.browse.misclassify_refresh import MisclassifyRefreshMixin
from gui_app.tabs.browse.misclassify_row import MisclassifyRowMixin


class MisclassifyActionsMixin(MisclassifyRefreshMixin, MisclassifyRowMixin):
    """Keep old import path. No logic here."""
