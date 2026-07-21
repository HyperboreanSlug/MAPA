"""RecordSidebar open/export/photo/detail text actions."""
from __future__ import annotations

import os
import threading
import webbrowser
from typing import Any, Dict

from gui_app.shared.record_sidebar_photo import load_sidebar_photo, resolve_photo_path
from gui_app.shared.record_sidebar_ui import _DETAIL_KEYS, first_field
from gui_app.theme import C


class RecordSidebarActionsMixin:
    """Open links, export card, fill details, load photo."""

    def _open_source(self) -> None:
        url = str((self._record or {}).get("source_url") or "").strip()
        if url:
            webbrowser.open(url)

    def _open_photo_file(self) -> None:
        path = resolve_photo_path((self._record or {}).get("photo_path"))
        if path and path.is_file():
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
            except Exception:
                webbrowser.open(path.resolve().as_uri())

    def _export_card(self) -> None:
        if not self._record:
            return
        self.export_btn.configure(state="disabled", text="Exporting…")
        record = dict(self._record)

        def work() -> None:
            try:
                from gui_app.shared.export_card import export_record_card_to_desktop

                path = export_record_card_to_desktop(record)

                def ok() -> None:
                    if isinstance(self._record, dict):
                        if record.get("export_number") is not None:
                            self._record["export_number"] = record["export_number"]
                        if record.get("flags") is not None:
                            self._record["flags"] = record["flags"]
                    self.export_btn.configure(
                        state="normal", text="Export card to Desktop"
                    )
                    num = record.get("export_number")
                    badge = f" · export #{num}" if num else ""
                    self.verdict_status.configure(
                        text=(
                            f"Saved card → {path.name}{badge}"
                            f" · confirmed incorrect"
                        ),
                        text_color=C["success"],
                    )
                    cb = getattr(self, "_on_export_done", None)
                    if cb and isinstance(self._record, dict):
                        cb(self._record)

                self._schedule(ok)
            except Exception as exc:

                def fail() -> None:
                    self.export_btn.configure(
                        state="normal", text="Export card to Desktop"
                    )
                    self.verdict_status.configure(
                        text=f"Export failed: {exc}",
                        text_color=C["danger"],
                    )

                self._schedule(fail)

        threading.Thread(target=work, daemon=True).start()

    def _fill_text(self, record: Dict[str, Any]) -> None:
        from scraper.charge_expand import expand_charge
        from scraper.searcher import format_race_label

        lines = []
        for label, keys in _DETAIL_KEYS:
            if label == "Charges":
                value = expand_charge(record)
            else:
                value = first_field(record, keys)
            if label == "Name" and value != "—":
                value = str(value).upper()
            if label == "Race" and value != "—":
                value = format_race_label(value)
            if value != "—":
                lines.append(f"{label}: {value}")
        err = record.get("scrape_error")
        if err:
            lines.append(f"Error: {err}")
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", "\n".join(lines) or "No fields.")
        self.details.configure(state="disabled")

    def _set_photo(self, image: Any, text: str = "") -> None:
        self._image_ref = image
        # Keep label slot at the configured box size so the image is centered
        # inside a stable frame (never larger than the slot).
        try:
            w, h = self.photo_size
            self.photo.configure(width=int(w), height=int(h))
        except Exception:
            pass
        if image is None:
            self.photo.configure(image="", text=text or "No photo")
        else:
            self.photo.configure(image=image, text="")

    def _store_photo_source(self, pil_image: Any) -> None:
        """Keep full-res RGB source so resize can re-fit without re-download."""
        self._pil_source = pil_image

    def _load_photo(self, record: Dict[str, Any], token: int) -> None:
        load_sidebar_photo(
            record=record,
            token=token,
            photo_size=self.photo_size,
            load_token_fn=lambda: self._load_token,
            schedule_fn=self._schedule,
            set_photo_fn=self._set_photo,
            store_source_fn=self._store_photo_source,
        )

    def _refit_current_photo(self) -> None:
        """Re-render the current mugshot into the latest photo_size box."""
        from gui_app.shared.record_sidebar_photo import render_fitted_ctk_image

        src = getattr(self, "_pil_source", None)
        if src is None:
            if self._record:
                self._load_photo(self._record, self._load_token)
            return
        image = render_fitted_ctk_image(src, self.photo_size)
        if image is not None:
            self._set_photo(image)
        elif self._record:
            self._load_photo(self._record, self._load_token)
