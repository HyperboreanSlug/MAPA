"""Settings tab mixins."""
from __future__ import annotations

from gui_app.tabs.settings.build import SettingsBuildMixin
from gui_app.tabs.settings.persist_sync import SettingsDbSyncMixin


class SettingsTabMixin(SettingsDbSyncMixin, SettingsBuildMixin):
    """Settings: general prefs + public database download/upload."""


__all__ = ["SettingsTabMixin"]
