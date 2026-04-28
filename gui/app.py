import queue
import threading
import customtkinter as ctk
from tkinter import messagebox

import cleaner
from categories import CATEGORIES
from gui.scan_panel import ScanPanel
from gui.log_panel import LogPanel

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#090d18"
BG_SURFACE  = "#0d1120"
ACCENT      = "#3b82f6"
SUCCESS     = "#22c55e"
TEXT_1      = "#f1f5f9"
TEXT_2      = "#64748b"
TEXT_3      = "#374151"
BORDER      = "#1c2844"


class CrispApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Crisp — Windows System Cleaner")
        self.geometry("530x730")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self._scan_results: dict[str, tuple[int, list]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._busy = False

        self._build_ui()
        self._poll_queue()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_header()
        self._build_stats_bar()
        self._build_scan_area()
        self._build_progress()
        self._build_buttons()
        self._build_log()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=BG_SURFACE, corner_radius=0, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            inner,
            text="Crisp",
            font=("Segoe UI", 26, "bold"),
            text_color=TEXT_1,
        ).pack(side="left")

        ctk.CTkLabel(
            inner,
            text="  Windows System Cleaner",
            font=("Segoe UI", 13),
            text_color=TEXT_2,
        ).pack(side="left", pady=(4, 0))

        # Admin badge (top-right)
        badge = ctk.CTkFrame(header, fg_color="#0d2b1a", corner_radius=6)
        badge.place(relx=1.0, rely=0.5, anchor="e", x=-16)
        ctk.CTkLabel(
            badge,
            text=" ✔ Admin ",
            font=("Segoe UI", 10, "bold"),
            text_color=SUCCESS,
        ).pack(padx=6, pady=3)

    def _build_stats_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(14, 0))

        self._total_label = ctk.CTkLabel(
            bar,
            text="Run a scan to check for junk files.",
            font=("Segoe UI", 12),
            text_color=TEXT_2,
        )
        self._total_label.pack(side="left")

    def _build_scan_area(self) -> None:
        self._scan_container = ctk.CTkScrollableFrame(
            self,
            height=330,
            fg_color=BG,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#2a3a5c",
        )
        self._scan_container.pack(fill="x", padx=14, pady=(10, 0))

        self._scan_panel = ScanPanel(self._scan_container, categories=CATEGORIES)
        self._scan_panel.pack(fill="x", padx=4, pady=4)

    def _build_progress(self) -> None:
        self._progress = ctk.CTkProgressBar(
            self,
            width=490,
            height=6,
            progress_color=ACCENT,
            fg_color=BORDER,
            corner_radius=3,
        )
        self._progress.set(0)
        self._progress.pack(pady=(14, 0))

        self._status_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 11),
            text_color=TEXT_2,
        )
        self._status_label.pack(pady=(5, 0))

    def _build_buttons(self) -> None:
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=12)

        self._scan_btn = ctk.CTkButton(
            btn_frame,
            text="⟳  Scan Now",
            width=170,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#1a2d4d",
            hover_color="#1e4080",
            corner_radius=10,
            command=self._start_scan,
        )
        self._scan_btn.pack(side="left", padx=8)

        self._clean_btn = ctk.CTkButton(
            btn_frame,
            text="✦  Clean Selected",
            width=170,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#0e2d1c",
            hover_color="#145c34",
            corner_radius=10,
            state="disabled",
            command=self._start_clean,
        )
        self._clean_btn.pack(side="left", padx=8)

    def _build_log(self) -> None:
        sep = ctk.CTkFrame(self, height=1, fg_color=BORDER)
        sep.pack(fill="x", padx=20, pady=(6, 0))

        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(8, 2))

        ctk.CTkLabel(
            log_header,
            text="Activity Log",
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT_2,
        ).pack(side="left")

        self._log = LogPanel(self, width=490, height=130, fg_color="#060a12")
        self._log.pack(padx=16, pady=(0, 14))

    # ── Scan ──────────────────────────────────────────────────────────────────

    # ── Scan progress animation ───────────────────────────────────────────────

    def _start_pulse(self) -> None:
        """Animate the progress bar while a scan is running."""
        if not self._busy:
            return
        v = self._progress.get()
        if not hasattr(self, "_pulse_dir"):
            self._pulse_dir = 1
        v += 0.03 * self._pulse_dir
        if v >= 0.88:
            self._pulse_dir = -1
        elif v <= 0.04:
            self._pulse_dir = 1
        self._progress.set(v)
        self.after(55, self._start_pulse)

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _start_scan(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._pulse_dir = 1
        self._scan_btn.configure(state="disabled", text="  Scanning…")
        self._clean_btn.configure(state="disabled")
        self._scan_panel.reset_sizes()
        self._total_label.configure(text="Scanning your system…", text_color=TEXT_2)
        self._progress.set(0.04)
        self._status_label.configure(text="Starting scan…")
        self._log.clear()
        self._scan_results.clear()

        # Read toggle state NOW on the UI thread before handing off to worker.
        # This prevents scanning browser caches when the user hasn't toggled them on.
        keys_to_scan = self._scan_panel.get_selected_categories()

        self._start_pulse()                                      # kick off animation
        threading.Thread(target=self._scan_worker, args=(keys_to_scan,), daemon=True).start()

    def _scan_worker(self, keys_to_scan: list[str]) -> None:
        """
        Scan each selected category in its OWN parallel thread so results
        appear card-by-card as they finish — not all-at-once after the slowest.
        """
        if not keys_to_scan:
            self._queue.put(("scan_done", 0))
            return

        total_lock  = threading.Lock()
        grand_total = [0]
        remaining   = [len(keys_to_scan)]

        # Per-category file/byte counters for the aggregated live status label
        _cat_files: dict[str, int] = {k: 0 for k in keys_to_scan}
        _cat_bytes: dict[str, int] = {k: 0 for k in keys_to_scan}
        _prog_lock = threading.Lock()

        def _make_progress_cb(cat_key: str):
            def _cb(f: int, b: int) -> None:
                with _prog_lock:
                    _cat_files[cat_key] = f
                    _cat_bytes[cat_key] = b
                    tf = sum(_cat_files.values())
                    tb = sum(_cat_bytes.values())
                self._queue.put(("scan_live", tf, tb))
            return _cb

        def _scan_one(key: str) -> None:
            size, files = 0, []
            try:
                # Run get_paths() in a thread with a 5-second timeout so that
                # hangs on network drives or disconnected volumes don't freeze
                # the scan permanently (Path.exists / iterdir can block forever
                # on Windows if the target is on an unresponsive mount).
                paths_result: list = []
                def _get_paths() -> None:
                    try:
                        paths_result.extend(CATEGORIES[key]["get_paths"]())
                    except Exception:
                        pass
                pt = threading.Thread(target=_get_paths, daemon=True)
                pt.start()
                pt.join(timeout=5.0)
                paths = paths_result  # empty list if timed-out or failed

                if paths:
                    results = cleaner.scan_all_categories(
                        {key: paths},
                        progress_cb=_make_progress_cb(key),
                        timeout_sec=15.0,
                    )
                    size, files = results.get(key, (0, []))
            except Exception:
                pass
            finally:
                # Always post result and decrement counter — guarantees
                # scan_done is eventually sent even if an error occurred.
                self._queue.put(("size", key, size, files))
                with total_lock:
                    grand_total[0] += size
                    remaining[0] -= 1
                    if remaining[0] == 0:
                        self._queue.put(("scan_done", grand_total[0]))

        for key in keys_to_scan:
            threading.Thread(target=_scan_one, args=(key,), daemon=True).start()

    # ── Clean ─────────────────────────────────────────────────────────────────

    def _start_clean(self) -> None:
        if self._busy:
            return

        selected = self._scan_panel.get_selected_categories()
        do_recycle = self._scan_panel.recycle_selected

        if not selected and not do_recycle:
            messagebox.showinfo("Nothing selected", "Toggle on at least one category.")
            return

        total = sum(self._scan_results.get(k, (0, []))[0] for k in selected)
        msg = f"This will permanently delete ~{cleaner.format_size(total)} of files."
        if do_recycle:
            msg += "\nThe Recycle Bin will also be emptied."
        msg += "\n\nProceed?"

        if not messagebox.askyesno("Confirm — Crisp", msg, icon="warning"):
            return

        self._busy = True
        self._scan_btn.configure(state="disabled")
        self._clean_btn.configure(state="disabled", text="  Cleaning…")
        self._progress.set(0)
        self._status_label.configure(text="")

        threading.Thread(
            target=self._clean_worker,
            args=(selected, do_recycle),
            daemon=True,
        ).start()

    def _clean_worker(self, selected: list[str], do_recycle: bool) -> None:
        all_files = []
        for key in selected:
            _, files = self._scan_results.get(key, (0, []))
            all_files.extend(files)

        total_files = max(len(all_files), 1)
        done = [0]

        def progress_cb(action: str, msg: str) -> None:
            done[0] += 1
            self._queue.put(("log", action, msg))
            self._queue.put(("progress", done[0] / total_files))

        freed, skipped = cleaner.clean_category(all_files, progress_cb=progress_cb)

        if do_recycle:
            self._queue.put(("log", "info", "Emptying Recycle Bin…"))
            ok = cleaner.empty_recycle_bin()
            self._queue.put((
                "log",
                "info" if ok else "skipped",
                "Recycle Bin emptied." if ok else "Recycle Bin already empty.",
            ))

        self._queue.put(("clean_done", freed, skipped))

    # ── Queue polling ─────────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        try:
            while True:
                self._handle_msg(self._queue.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    def _handle_msg(self, msg: tuple) -> None:
        kind = msg[0]

        if kind == "progress":
            self._progress.set(msg[1])

        elif kind == "scan_live":
            # Live update fired by workers every ~100 files
            _, files_found, bytes_found = msg
            self._status_label.configure(
                text=f"Scanning…   {files_found:,} files  •  {cleaner.format_size(bytes_found)} found so far"
            )

        elif kind == "size":
            _, key, size, files = msg
            self._scan_results[key] = (size, files)
            self._scan_panel.set_size(key, size, len(files))
            self._scan_panel.set_files(key, files)

        elif kind == "scan_done":
            total = msg[1]
            self._busy = False          # stop pulse animation
            self._progress.set(1.0)
            if total == 0:
                self._total_label.configure(
                    text="Your system looks clean.", text_color=SUCCESS
                )
            else:
                self._total_label.configure(
                    text=f"Found  {cleaner.format_size(total)}  of junk files",
                    text_color=SUCCESS,
                )
            self._status_label.configure(
                text="Scan complete  •  Click ▶ Preview on any category to inspect files"
            )
            self._scan_btn.configure(state="normal", text="⟳  Scan Now")
            self._clean_btn.configure(state="normal")

        elif kind == "log":
            _, action, text = msg
            self._log.log(action, text)

        elif kind == "clean_done":
            _, freed, skipped = msg
            self._progress.set(1)
            self._status_label.configure(
                text=f"Done  •  Freed {cleaner.format_size(freed)}  •  Skipped {skipped} locked files"
            )
            self._scan_btn.configure(state="normal", text="⟳  Scan Now")
            self._clean_btn.configure(state="disabled", text="✦  Clean Selected")
            self._total_label.configure(
                text="Run a scan to check for junk files.", text_color=TEXT_2
            )
            self._scan_panel.reset_sizes()
            self._scan_results.clear()
            self._busy = False
