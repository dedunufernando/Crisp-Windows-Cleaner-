import ctypes
import os
import queue as _q
import threading as _t
import time
from pathlib import Path
from typing import Callable


AGE_THRESHOLD_HOURS = 24
_SKIPPED   = "skipped"
_DELETED   = "deleted"
_N_WORKERS = 4          # per-category pool; 4 threads is optimal for mixed HDD/SSD
SCAN_TIMEOUT_SEC = 15   # hard cutoff — return partial results after this many seconds
MAX_SCAN_DEPTH   = 15   # prevent runaway recursion through junction-point cycles


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


IS_ADMIN = _is_admin()


# ── Parallel directory scanner ─────────────────────────────────────────────────

def scan_all_categories(
    paths_by_key: dict[str, list[Path]],
    progress_cb: Callable[[int, int], None] | None = None,
    timeout_sec: float = SCAN_TIMEOUT_SEC,
) -> dict[str, tuple[int, list[Path]]]:
    """
    Scan every supplied category in a shared thread pool of _N_WORKERS workers.

    progress_cb(files_found, bytes_found) fires at most every 0.25 s.
    Always returns within timeout_sec seconds (partial results on timeout).
    """
    dir_q: _q.Queue = _q.Queue()
    lock        = _t.Lock()
    buckets: dict[str, list] = {k: [0, []] for k in paths_by_key}
    totals      = [0, 0]        # [file_count, byte_count]
    last_notify = [0.0]         # monotonic timestamp of last progress_cb fire
    _abort      = _t.Event()

    for key, paths in paths_by_key.items():
        for p in paths:
            dir_q.put((key, str(p), 0))  # (key, path, depth)

    if dir_q.empty():
        return {k: (0, []) for k in paths_by_key}

    def _worker() -> None:
        while True:
            # Short timeout so workers notice _abort within one cycle
            try:
                item = dir_q.get(timeout=0.05)
            except _q.Empty:
                if _abort.is_set():
                    return
                continue

            # Abort fired while we were waiting — discard item and exit
            if _abort.is_set():
                dir_q.task_done()
                return  # exit immediately, not continue

            key, current, depth = item
            try:
                local_files: list[Path] = []
                local_size = 0
                try:
                    with os.scandir(current) as it:
                        for e in it:
                            if _abort.is_set():
                                break
                            try:
                                if e.is_file(follow_symlinks=False):
                                    local_files.append(Path(e.path))
                                    local_size += e.stat(follow_symlinks=False).st_size
                                elif e.is_dir(follow_symlinks=False):
                                    if depth < MAX_SCAN_DEPTH and not _abort.is_set():
                                        dir_q.put((key, e.path, depth + 1))
                            except OSError:
                                pass
                except OSError:
                    pass

                if local_files or local_size:
                    notify = False
                    with lock:
                        buckets[key][0] += local_size
                        buckets[key][1].extend(local_files)
                        totals[0] += len(local_files)
                        totals[1] += local_size
                        # Time-based progress: fire at most every 0.25 s
                        now = time.monotonic()
                        if progress_cb and (now - last_notify[0]) >= 0.25:
                            last_notify[0] = now
                            notify = True
                    if notify and progress_cb:
                        progress_cb(totals[0], totals[1])
            finally:
                dir_q.task_done()  # always called, even on unexpected exceptions

    # Start worker pool
    threads = [_t.Thread(target=_worker, daemon=True) for _ in range(_N_WORKERS)]
    for t in threads:
        t.start()

    # Waiter thread fires done_evt when every task_done() has been called
    done_evt = _t.Event()
    def _waiter() -> None:
        dir_q.join()
        done_evt.set()
    _t.Thread(target=_waiter, daemon=True).start()

    # ── Wait for completion OR hard timeout ────────────────────────────────────
    done_evt.wait(timeout=timeout_sec)
    _abort.set()        # tell workers to stop — harmless if already done naturally

    # Give workers one get()-cycle to see _abort and stop adding new subdirs
    time.sleep(0.1)

    # Drain whatever items workers didn't get to — keeps task_done accounting clean
    while True:
        try:
            dir_q.get_nowait()
            dir_q.task_done()
        except _q.Empty:
            break

    # !! Do NOT join threads here — they're daemon threads and will exit on their
    #    own within one 0.05 s get()-cycle. Joining would add up to N×join_timeout
    #    seconds of dead wait time, which was the main source of slowness.

    return {k: (v[0], v[1]) for k, v in buckets.items()}


# kept for compatibility
def scan_category(paths: list[Path]) -> tuple[int, list[Path]]:
    result = scan_all_categories({"_": paths})
    return result["_"]


# ── File age check ─────────────────────────────────────────────────────────────

def _file_age_ok(path: Path) -> bool:
    try:
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        return age_hours >= AGE_THRESHOLD_HOURS
    except OSError:
        return False


# ── Clean ──────────────────────────────────────────────────────────────────────

def clean_category(
    file_list: list[Path],
    progress_cb: Callable[[str, str], None] | None = None,
    skip_age_check: bool = False,
) -> tuple[int, int]:
    freed = 0
    skipped = 0

    for f in file_list:
        if not skip_age_check and not _file_age_ok(f):
            skipped += 1
            if progress_cb:
                progress_cb(_SKIPPED, f"Too new (<24h): {f.name}")
            continue
        try:
            size = f.stat().st_size
            f.unlink()
            freed += size
            if progress_cb:
                progress_cb(_DELETED, str(f))
        except (PermissionError, OSError):
            skipped += 1
            if progress_cb:
                progress_cb(_SKIPPED, f"In use: {f.name}")

    _clean_empty_dirs(file_list)
    return freed, skipped


def _clean_empty_dirs(file_list: list[Path]) -> None:
    dirs = sorted({f.parent for f in file_list}, key=lambda p: len(p.parts), reverse=True)
    for d in dirs:
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


# ── Recycle Bin ────────────────────────────────────────────────────────────────

def empty_recycle_bin() -> bool:
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI   = 0x00000002
    try:
        return ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI
        ) == 0
    except Exception:
        return False


# ── Formatting ─────────────────────────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024**3:.1f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024**2:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"
