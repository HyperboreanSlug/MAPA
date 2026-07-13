"""Inline record preview sidebar (photo + key fields)."""

from __future__ import annotations

import io
import os
import queue
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import customtkinter as ctk
import requests

from gui_app.theme import C, FONT_BOLD, FONT_SM
from scraper.config import USER_AGENT

ACTUAL_RACE_OPTIONS = [
    "Hispanic",
    "Indian",
    "Asian",
    "African American",
    "Black",
    "White",
    "Arabic",
    "European",
    "Jewish",
    "Portuguese",
    "Native American",
    "Other",
    "Unknown",
]

_DETAIL_KEYS = (
    ("Name", ("full_name", "name")),
    ("Charges", ("charge_description",)),
    ("Race", ("race",)),
    ("Likely ethnicity", ("likely_ethnicity",)),
    ("Confidence", ("confidence", "name_confidence")),
    ("Sex", ("sex", "gender")),
    ("Age", ("age",)),
    ("State", ("state",)),
    ("County", ("county",)),
    ("Booking date", ("booking_date",)),
    ("Booking ID", ("booking_id",)),
    ("Facility", ("facility",)),
    ("Agency", ("agency",)),
    ("Height", ("height",)),
    ("Weight", ("weight",)),
    ("Hair", ("hair",)),
    ("Eyes", ("eyes",)),
    ("Source URL", ("source_url",)),
    ("Photo path", ("photo_path",)),
)


def _first(record: Dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return "—"


def merge_ethnicity_review_flags(raw_flags: Any, verdict: str) -> str:
    """Merge ``ethnicity_review`` into the arrests.flags JSON blob."""
    import json
    from datetime import datetime, timezone

    if isinstance(raw_flags, dict):
        flags: Dict[str, Any] = dict(raw_flags)
    elif isinstance(raw_flags, str) and raw_flags.strip():
        try:
            parsed = json.loads(raw_flags)
            flags = dict(parsed) if isinstance(parsed, dict) else {"notes": raw_flags}
        except Exception:
            flags = {"notes": raw_flags}
    else:
        flags = {}
    flags["ethnicity_review"] = verdict
    flags["ethnicity_reviewed_at"] = datetime.now(timezone.utc).isoformat()
    return json.dumps(flags, ensure_ascii=False, sort_keys=True)


def _resolve_photo_path(raw: Any) -> Optional[Path]:
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        return path
    alt = Path.cwd() / path
    if alt.is_file():
        return alt
    return path if path.exists() else None


class RecordSidebar:
    """Right-hand photo + details pane bound to a tree selection."""

    def __init__(self, parent: Any, *, photo_size: tuple[int, int] = (320, 320)) -> None:
        self.photo_size = photo_size
        self.frame = ctk.CTkFrame(parent, fg_color=C["panel"], width=380, corner_radius=10)
        self.frame.grid_propagate(False)
        self.frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.frame, text="Details", font=FONT_BOLD, text_color=C["text"]
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        self.photo = ctk.CTkLabel(
            self.frame,
            text="Select a record",
            text_color=C["muted"],
            width=photo_size[0],
            height=photo_size[1],
            fg_color=C["elevated"],
            corner_radius=8,
        )
        self.photo.grid(row=1, column=0, padx=10, pady=(2, 6), sticky="nsew")

        btn_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))
        btn_row.grid_columnconfigure((0, 1), weight=1)
        self.open_btn = ctk.CTkButton(
            btn_row,
            text="Open source URL",
            command=self._open_source,
            state="disabled",
            height=30,
        )
        self.open_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.open_photo_btn = ctk.CTkButton(
            btn_row,
            text="Open photo",
            command=self._open_photo_file,
            state="disabled",
            height=30,
        )
        self.open_photo_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.export_btn = ctk.CTkButton(
            self.frame,
            text="Export card to Desktop",
            command=self._export_card,
            state="disabled",
            height=30,
            fg_color=C["accent_dim"],
            hover_color=C["accent"],
            text_color=C["text"],
        )
        self.export_btn.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 4))

        verdict_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        verdict_row.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 4))
        verdict_row.grid_columnconfigure((0, 1), weight=1)
        self.correct_btn = ctk.CTkButton(
            verdict_row,
            text="Classified correctly",
            fg_color=C["success"],
            hover_color="#68b888",
            text_color="#0c0c0e",
            command=lambda: self._emit_verdict("correct"),
            state="disabled",
            height=30,
        )
        self.correct_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.incorrect_btn = ctk.CTkButton(
            verdict_row,
            text="Classified incorrectly",
            fg_color=C["danger"],
            hover_color="#c96a6a",
            text_color="#0c0c0e",
            command=lambda: self._emit_verdict("incorrect"),
            state="disabled",
            height=30,
        )
        self.incorrect_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.race_banner = ctk.CTkLabel(
            self.frame,
            text="Marked race: —",
            font=FONT_BOLD,
            text_color=C["text"],
            fg_color=C["accent_dim"],
            corner_radius=8,
            height=40,
            anchor="center",
        )
        self.race_banner.grid(row=5, column=0, sticky="ew", padx=12, pady=(2, 4))

        self.verdict_status = ctk.CTkLabel(
            self.frame, text="", font=FONT_SM, text_color=C["muted"], anchor="w"
        )
        self.verdict_status.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 2))

        actual_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        actual_row.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 4))
        actual_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            actual_row, text="Actual race", font=FONT_SM, text_color=C["muted"]
        ).grid(row=0, column=0, sticky="w")
        self.actual_race = ctk.CTkComboBox(
            actual_row,
            values=list(ACTUAL_RACE_OPTIONS),
            command=self._emit_actual_race,
            state="disabled",
        )
        self.actual_race.set("Unknown")
        self.actual_race.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.details = ctk.CTkTextbox(
            self.frame,
            fg_color=C["bg"],
            text_color=C["text"],
            font=FONT_SM,
            wrap="word",
            activate_scrollbars=True,
            height=140,
        )
        self.details.grid(row=8, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.details.insert("end", "Select a row to preview mugshot and booking fields.")
        self.details.configure(state="disabled")

        # Photo grows; details keep leftover space (row index after insert).
        self.frame.grid_rowconfigure(1, weight=3)
        self.frame.grid_rowconfigure(8, weight=2)

        self._image_ref: Any = None
        self._load_token = 0
        self._after: Optional[Callable[..., Any]] = None
        self._record: Optional[Dict[str, Any]] = None
        self._on_verdict: Optional[Callable[[Dict[str, Any], str], None]] = None
        self._on_actual_race: Optional[Callable[[Dict[str, Any], str], None]] = None
        self._ui_q: queue.Queue[Callable[[], None]] = queue.Queue()
        self._pumping = False
        self._syncing_actual = False
        self._resize_after: Any = None
        self.frame.bind("<Configure>", self._on_sidebar_configure)

    def bind_after(self, after_fn: Callable[..., Any]) -> None:
        """Provide the host window's ``after`` for thread-safe UI updates."""
        self._after = after_fn
        if not self._pumping:
            self._pumping = True
            self._pump_ui()

    def bind_verdict(
        self, callback: Optional[Callable[[Dict[str, Any], str], None]]
    ) -> None:
        """``callback(record, 'correct'|'incorrect')`` when a review button is pressed."""
        self._on_verdict = callback

    def bind_actual_race(
        self, callback: Optional[Callable[[Dict[str, Any], str], None]]
    ) -> None:
        """``callback(record, actual_race)`` when the Actual race dropdown changes."""
        self._on_actual_race = callback

    def _emit_verdict(self, verdict: str) -> None:
        if not self._record or not self._on_verdict:
            return
        self._on_verdict(dict(self._record), verdict)

    def _emit_actual_race(self, choice: str) -> None:
        if self._syncing_actual or not self._record or not self._on_actual_race:
            return
        actual = (choice or self.actual_race.get() or "").strip() or "Unknown"
        self._record["likely_ethnicity"] = actual
        self._on_actual_race(dict(self._record), actual)
        self._fill_text(self._record)

    @staticmethod
    def review_label(record: Optional[Dict[str, Any]]) -> str:
        flags = (record or {}).get("flags")
        if isinstance(flags, str):
            try:
                import json

                flags = json.loads(flags)
            except Exception:
                flags = {}
        if not isinstance(flags, dict):
            return ""
        review = str(flags.get("ethnicity_review") or "").strip().lower()
        if review == "correct":
            return "Marked: classified correctly"
        if review == "incorrect":
            return "Marked: classified incorrectly"
        return ""

    def _pump_ui(self) -> None:
        """Drain worker callbacks on the Tk main thread."""
        try:
            while True:
                fn = self._ui_q.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        if self._after:
            self._after(50, self._pump_ui)

    def _schedule(self, fn: Callable[[], None]) -> None:
        self._ui_q.put(fn)

    def _on_sidebar_configure(self, _event=None) -> None:
        if not self._after:
            return
        if self._resize_after is not None:
            try:
                self.frame.after_cancel(self._resize_after)
            except Exception:
                pass
        self._resize_after = self.frame.after(120, self._apply_photo_slot_size)

    def _apply_photo_slot_size(self) -> None:
        self._resize_after = None
        size = self._target_photo_size()
        if size == self.photo_size:
            return
        self.photo_size = size
        self.photo.configure(width=size[0], height=size[1])
        if self._record:
            self._load_photo(self._record, self._load_token)

    def _target_photo_size(self) -> tuple[int, int]:
        """Largest square that fits the photo row without crushing controls."""
        try:
            fw = int(self.frame.winfo_width())
            fh = int(self.frame.winfo_height())
        except Exception:
            return self.photo_size
        if fw < 80 or fh < 80:
            return self.photo_size
        # Reserve space for header + buttons + banner + actual race + details.
        side = min(fw - 20, max(180, fh - 360))
        side = max(200, min(side, 480))
        return (side, side)

    @staticmethod
    def _marked_race_text(record: Optional[Dict[str, Any]]) -> str:
        from scraper.searcher import format_race_label

        if not record:
            return "Marked race: —"
        label = format_race_label(str(record.get("race") or "").strip())
        if not label or label == "—":
            label = "Unknown"
        return f"Marked race: {label}"

    def clear(self, message: str = "Select a record") -> None:
        self._load_token += 1
        self._record = None
        self._image_ref = None
        self.photo.configure(image="", text=message)
        self.open_btn.configure(state="disabled")
        self.open_photo_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")
        self.correct_btn.configure(state="disabled")
        self.incorrect_btn.configure(state="disabled")
        self.actual_race.configure(state="disabled")
        self.race_banner.configure(text="Marked race: —")
        self.verdict_status.configure(text="", text_color=C["muted"])
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", message)
        self.details.configure(state="disabled")

    def show(self, record: Optional[Dict[str, Any]]) -> None:
        if not record:
            self.clear()
            return
        self._record = dict(record)
        self._load_token += 1
        token = self._load_token
        self.photo_size = self._target_photo_size()
        self.photo.configure(width=self.photo_size[0], height=self.photo_size[1])
        self._fill_text(self._record)
        self.race_banner.configure(text=self._marked_race_text(self._record))
        has_url = bool(str(self._record.get("source_url") or "").strip())
        self.open_btn.configure(state="normal" if has_url else "disabled")
        photo_path = _resolve_photo_path(self._record.get("photo_path"))
        self.open_photo_btn.configure(
            state="normal" if photo_path and photo_path.is_file() else "disabled"
        )
        self.export_btn.configure(state="normal")
        enabled = "normal" if self._on_verdict else "disabled"
        self.correct_btn.configure(state=enabled)
        self.incorrect_btn.configure(state=enabled)
        label = self.review_label(self._record)
        if "incorrect" in label:
            self.verdict_status.configure(text=label, text_color=C["danger"])
        elif "correct" in label:
            self.verdict_status.configure(text=label, text_color=C["success"])
        else:
            self.verdict_status.configure(text=label or "", text_color=C["muted"])
        likely = (
            str(
                self._record.get("likely_ethnicity")
                or self._record.get("race")
                or "Unknown"
            ).strip()
            or "Unknown"
        )
        opts = list(ACTUAL_RACE_OPTIONS)
        if likely not in opts:
            opts = [likely] + opts
        self._syncing_actual = True
        try:
            self.actual_race.configure(
                values=opts,
                state="normal" if self._on_actual_race else "disabled",
            )
            self.actual_race.set(likely)
        finally:
            self._syncing_actual = False
        self._load_photo(self._record, token)

    def _open_source(self) -> None:
        url = str((self._record or {}).get("source_url") or "").strip()
        if url:
            webbrowser.open(url)

    def _open_photo_file(self) -> None:
        path = _resolve_photo_path((self._record or {}).get("photo_path"))
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
                    self.export_btn.configure(
                        state="normal", text="Export card to Desktop"
                    )
                    self.verdict_status.configure(
                        text=f"Saved card → {path.name}",
                        text_color=C["success"],
                    )

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
        from scraper.searcher import format_race_label

        lines = []
        for label, keys in _DETAIL_KEYS:
            value = _first(record, keys)
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
        if image is None:
            self.photo.configure(image="", text=text or "No photo")
        else:
            self.photo.configure(image=image, text="")

    def _load_photo(self, record: Dict[str, Any], token: int) -> None:
        path = _resolve_photo_path(record.get("photo_path"))
        url = str(record.get("photo_url") or "").strip()
        self._set_photo(None, "Loading photo…")

        def work() -> None:
            # Decode off-thread; construct CTkImage on the UI thread via queue.
            pil_rgb = None
            message = "No photo"
            try:
                from PIL import Image

                data: Optional[bytes] = None
                if path and path.is_file():
                    data = path.read_bytes()
                elif url:
                    resp = requests.get(
                        url,
                        timeout=25,
                        headers={
                            "User-Agent": USER_AGENT,
                            "Accept": "image/webp,image/*,*/*;q=0.8",
                            "Referer": "https://recentlybooked.com/",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.content
                if data:
                    img = Image.open(io.BytesIO(data))
                    if getattr(img, "n_frames", 1) > 1:
                        img.seek(0)
                    pil_rgb = img.convert("RGB")
                    pil_rgb.thumbnail(self.photo_size)
                elif not url:
                    message = "No photo URL"
            except Exception as exc:
                message = f"Photo unavailable ({type(exc).__name__}: {exc})"

            def apply() -> None:
                if token != self._load_token:
                    return
                if pil_rgb is None:
                    self._set_photo(None, message)
                    return
                try:
                    size: Tuple[int, int] = (pil_rgb.width, pil_rgb.height)
                    image = ctk.CTkImage(
                        light_image=pil_rgb, dark_image=pil_rgb, size=size
                    )
                    self._set_photo(image)
                except Exception as exc:
                    self._set_photo(
                        None, f"Photo display failed ({type(exc).__name__})"
                    )

            self._schedule(apply)

        threading.Thread(target=work, daemon=True).start()
