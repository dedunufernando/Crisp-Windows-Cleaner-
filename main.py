import ctypes
import sys


def _ensure_admin() -> None:
    if not ctypes.windll.shell32.IsUserAnAdmin():
        params = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit(0)


if __name__ == "__main__":
    _ensure_admin()
    from gui.app import CrispApp
    app = CrispApp()
    app.mainloop()
