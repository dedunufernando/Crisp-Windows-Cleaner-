import customtkinter as ctk
from datetime import datetime

_MAX_ROWS = 200   # cap visible rows so the log can never grow unbounded


class LogPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._rows: list[ctk.CTkLabel] = []

    def log(self, action: str, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        if action == "deleted":
            color  = "#22c55e"
            prefix = "✓"
        elif action == "skipped":
            color  = "#f59e0b"
            prefix = "–"
        elif action == "error":
            color  = "#ef4444"
            prefix = "✗"
        else:
            color  = "#64748b"
            prefix = "·"

        label = ctk.CTkLabel(
            self,
            text=f"[{ts}] {prefix}  {message}",
            anchor="w",
            justify="left",
            font=("Consolas", 10),
            text_color=color,
            wraplength=450,
        )
        label.pack(fill="x", padx=6, pady=1)
        self._rows.append(label)

        # Trim oldest rows so widget count stays bounded
        while len(self._rows) > _MAX_ROWS:
            self._rows.pop(0).destroy()

        # Scroll to bottom — guard against private-attr changes between CTk versions
        try:
            self._parent_canvas.yview_moveto(1.0)
        except AttributeError:
            pass

    def clear(self) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()
