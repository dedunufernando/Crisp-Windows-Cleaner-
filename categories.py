import os
from pathlib import Path


def _env(var: str) -> Path:
    val = os.environ.get(var)
    return Path(val) if val else Path(os.path.expanduser("~"))


def _exists(p: Path) -> list[Path]:
    return [p] if p.exists() else []


def get_temp_paths() -> list[Path]:
    paths = []
    tmp = _env("TEMP")
    if tmp.exists():
        paths.append(tmp)
    win_temp = Path(r"C:\Windows\Temp")
    if win_temp.exists():
        paths.append(win_temp)
    return paths


def get_prefetch_paths() -> list[Path]:
    return _exists(Path(r"C:\Windows\Prefetch"))


def get_windows_update_paths() -> list[Path]:
    return _exists(Path(r"C:\Windows\SoftwareDistribution\Download"))


def get_browser_cache_paths() -> list[Path]:
    local = _env("LOCALAPPDATA")
    appdata = _env("APPDATA")
    paths = []

    chrome = local / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    if chrome.exists():
        paths.append(chrome)

    edge = local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"
    if edge.exists():
        paths.append(edge)

    brave = local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache"
    if brave.exists():
        paths.append(brave)

    ff_base = appdata / "Mozilla" / "Firefox" / "Profiles"
    if ff_base.exists():
        for profile in ff_base.iterdir():
            cache2 = profile / "cache2"
            if cache2.exists():
                paths.append(cache2)

    return paths


CATEGORIES: dict[str, dict] = {
    "temp": {
        "label": "Temp & Prefetch",
        "sublabel": "%TEMP%  •  C:\\Windows\\Temp  •  Prefetch",
        "icon": "⚙",
        "accent": "#3b82f6",
        "default_on": True,
        "get_paths": lambda: get_temp_paths() + get_prefetch_paths(),
    },
    "updates": {
        "label": "Windows Update Cache",
        "sublabel": "SoftwareDistribution\\Download",
        "icon": "↻",
        "accent": "#f59e0b",
        "default_on": True,
        "get_paths": get_windows_update_paths,
    },
    "browser": {
        "label": "Browser Cache",
        "sublabel": "Chrome  •  Edge  •  Brave  •  Firefox",
        "icon": "◎",
        "accent": "#8b5cf6",
        "default_on": False,
        "get_paths": get_browser_cache_paths,
    },
}
