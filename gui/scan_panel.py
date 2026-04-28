from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from cleaner import format_size

_MAX_FILES = 15
_TRUNC = 54

# ── Palette ───────────────────────────────────────────────────────────────────
BG_CARD     = "#0d1526"
BG_FILELIST = "#080c16"
BG_FILEROW  = "#0f1a2e"
BORDER      = "#1c2a45"
TEXT_1      = "#e2e8f0"
TEXT_2      = "#64748b"
TEXT_3      = "#374151"


def _trunc(s: str, n: int = _TRUNC) -> str:
    if len(s) <= n:
        return s
    h = (n - 1) // 2
    return s[:h] + "…" + s[-(n - h - 1):]


# ── File list panel ───────────────────────────────────────────────────────────

class FileListPanel(ctk.CTkFrame):
    """Expandable panel showing the top N files sorted by size."""

    def __init__(self, master: ctk.CTkBaseClass, accent: str, **kwargs):
        super().__init__(master, fg_color=BG_FILELIST, corner_radius=8, **kwargs)
        self._accent = accent
        self._widgets: list = []

    def populate(self, files: list[Path]) -> None:
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()

        # Header row
        total_label = ctk.CTkLabel(
            self,
            text=f"  Largest files  ({len(files):,} total — showing top {min(len(files), _MAX_FILES)})",
            font=("Segoe UI", 10),
            text_color=TEXT_2,
            anchor="w",
        )
        total_label.pack(fill="x", padx=8, pady=(8, 2))
        self._widgets.append(total_label)

        div = ctk.CTkFrame(self, height=1, fg_color=BORDER)
        div.pack(fill="x", padx=8, pady=(0, 4))
        self._widgets.append(div)

        # Sort largest first — guard against files deleted since scan
        def _size(f: Path) -> int:
            try:
                return f.stat().st_size
            except OSError:
                return 0

        ranked = sorted(files, key=_size, reverse=True)[:_MAX_FILES]

        for f in ranked:
            sz = _size(f)
            row = ctk.CTkFrame(self, fg_color=BG_FILEROW, corner_radius=4)
            row.pack(fill="x", padx=8, pady=2)
            self._widgets.append(row)

            ctk.CTkLabel(
                row,
                text=format_size(sz),
                font=("Consolas", 10, "bold"),
                text_color=self._accent,
                width=68,
                anchor="e",
            ).pack(side="right", padx=(0, 8))

            ctk.CTkLabel(
                row,
                text=_trunc(str(f)),
                font=("Consolas", 10),
                text_color=TEXT_2,
                anchor="w",
            ).pack(side="left", padx=8, pady=4)

        if len(files) > _MAX_FILES:
            more = ctk.CTkLabel(
                self,
                text=f"  … and {len(files) - _MAX_FILES:,} more files",
                font=("Segoe UI", 10),
                text_color=TEXT_3,
                anchor="w",
            )
            more.pack(fill="x", padx=8, pady=(2, 8))
            self._widgets.append(more)
        else:
            pad = ctk.CTkFrame(self, fg_color="transparent", height=6)
            pad.pack()
            self._widgets.append(pad)

    def clear(self) -> None:
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()


# ── Category card ─────────────────────────────────────────────────────────────

class CategoryCard(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, key: str, meta: dict, **kwargs):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
            **kwargs,
        )
        self.key = key
        self._accent = meta["accent"]
        self._files: list[Path] = []
        self._expanded = False
        self._var = ctk.IntVar(value=1 if meta["default_on"] else 0)

        # ── Card top row: icon · name · switch ───────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 4))

        # Coloured dot
        ctk.CTkLabel(
            top,
            text="●",
            font=("Segoe UI", 13),
            text_color=self._accent,
            width=20,
        ).pack(side="left")

        # Category name
        ctk.CTkLabel(
            top,
            text=meta["label"],
            font=("Segoe UI", 13, "bold"),
            text_color=TEXT_1,
            anchor="w",
        ).pack(side="left", padx=(6, 0))

        # Toggle switch (right)
        self._switch = ctk.CTkSwitch(
            top,
            text="",
            variable=self._var,
            onvalue=1,
            offvalue=0,
            width=44,
            height=22,
            button_color="#1e293b",
            button_hover_color="#334155",
            progress_color=self._accent,
        )
        self._switch.pack(side="right")

        # ── Sub-label (paths hint) ────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text=meta.get("sublabel", ""),
            font=("Segoe UI", 10),
            text_color=TEXT_3,
            anchor="w",
        ).pack(fill="x", padx=40, pady=(0, 8))

        # ── Card bottom row: size · file count · preview button ──────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(0, 14))

        self._size_label = ctk.CTkLabel(
            bottom,
            text="—",
            font=("Segoe UI", 13, "bold"),
            text_color=TEXT_2,
        )
        self._size_label.pack(side="left")

        self._count_label = ctk.CTkLabel(
            bottom,
            text="",
            font=("Segoe UI", 10),
            text_color=TEXT_3,
        )
        self._count_label.pack(side="left", padx=(10, 0))

        self._preview_btn = ctk.CTkButton(
            bottom,
            text="▶  Preview",
            width=104,
            height=26,
            font=("Segoe UI", 11),
            fg_color="#111d33",
            hover_color="#1a2d4d",
            text_color=TEXT_2,
            corner_radius=6,
            state="disabled",
            command=self._toggle,
        )
        self._preview_btn.pack(side="right")

        # ── File list panel (hidden until expanded) ───────────────────────
        self._file_panel = FileListPanel(self, accent=self._accent)

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def is_selected(self) -> bool:
        return bool(self._var.get())

    def set_size(self, size_bytes: int, file_count: int) -> None:
        if size_bytes == 0:
            self._size_label.configure(text="0 B", text_color=TEXT_2)
            self._count_label.configure(text="nothing found")
        else:
            self._size_label.configure(
                text=format_size(size_bytes),
                text_color=self._accent,
            )
            self._count_label.configure(
                text=f"  •  {file_count:,} files",
                text_color=TEXT_2,
            )
        # Highlight card border when something is found
        if size_bytes > 0:
            self.configure(border_color=self._accent + "55")

    def set_files(self, files: list[Path]) -> None:
        self._files = files
        if files:
            self._preview_btn.configure(
                state="normal",
                text_color="#94a3b8",
            )

    def reset(self) -> None:
        self._size_label.configure(text="—", text_color=TEXT_2)
        self._count_label.configure(text="")
        self._files = []
        self._preview_btn.configure(state="disabled", text="▶  Preview", text_color=TEXT_2)
        self.configure(border_color=BORDER)
        if self._expanded:
            self._file_panel.pack_forget()
            self._file_panel.clear()
            self._expanded = False

    # ── Internal ──────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._file_panel.populate(self._files)
            self._file_panel.pack(fill="x", padx=12, pady=(0, 12))
            self._preview_btn.configure(text="▼  Hide")
        else:
            self._file_panel.pack_forget()
            self._file_panel.clear()
            self._preview_btn.configure(text="▶  Preview")


# ── Recycle bin card ──────────────────────────────────────────────────────────

class RecycleBinCard(ctk.CTkFrame):
    _ACCENT = "#ef4444"

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
            **kwargs,
        )
        self._var = ctk.IntVar(value=0)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(
            row,
            text="●",
            font=("Segoe UI", 13),
            text_color=self._ACCENT,
            width=20,
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text="Recycle Bin",
            font=("Segoe UI", 13, "bold"),
            text_color="#fbbf24",
            anchor="w",
        ).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(
            row,
            text="manual — off by default",
            font=("Segoe UI", 10),
            text_color="#78350f",
            anchor="w",
        ).pack(side="left", padx=(14, 0))

        self._switch = ctk.CTkSwitch(
            row,
            text="",
            variable=self._var,
            onvalue=1,
            offvalue=0,
            width=44,
            height=22,
            button_color="#1e293b",
            button_hover_color="#78350f",
            progress_color=self._ACCENT,
        )
        self._switch.pack(side="right")

    @property
    def is_selected(self) -> bool:
        return bool(self._var.get())


# ── Scan panel (container) ────────────────────────────────────────────────────

class ScanPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, categories: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._cards: dict[str, CategoryCard] = {}

        for key, meta in categories.items():
            card = CategoryCard(self, key=key, meta=meta)
            card.pack(fill="x", pady=5)
            self._cards[key] = card

        self._recycle_card = RecycleBinCard(self)
        self._recycle_card.pack(fill="x", pady=5)

    def set_size(self, key: str, size_bytes: int, file_count: int) -> None:
        if key in self._cards:
            self._cards[key].set_size(size_bytes, file_count)

    def set_files(self, key: str, files: list[Path]) -> None:
        if key in self._cards:
            self._cards[key].set_files(files)

    def reset_sizes(self) -> None:
        for card in self._cards.values():
            card.reset()

    def get_selected_categories(self) -> list[str]:
        return [k for k, c in self._cards.items() if c.is_selected]

    @property
    def recycle_selected(self) -> bool:
        return self._recycle_card.is_selected
