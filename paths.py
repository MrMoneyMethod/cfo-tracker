"""Filesystem locations for the CFO tracker.

Supports both running from source and running from a PyInstaller one-file
bundle. Read-only assets (static/, templates/) come from the bundle; writable
app data (JSON cache) goes to a user-writable directory so the executable works
after being installed (e.g. under %APPDATA% on Windows).
"""

from __future__ import annotations

import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_dir() -> str:
    """Directory containing read-only bundled assets (static, templates)."""
    if is_frozen():
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def app_dir() -> str:
    """Writable directory for per-machine app data (JSON cache)."""
    if is_frozen():
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            return os.path.join(base, "cfo-tracker")
        return os.path.join(os.path.expanduser("~"), ".cfo-tracker")
    return os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    d = os.path.join(app_dir(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def static_dir() -> str:
    return os.path.join(bundle_dir(), "static")


def templates_dir() -> str:
    return os.path.join(bundle_dir(), "templates")


# Convenience paths for the JSON cache (used by scheduler & app)
BUYS_PATH = os.path.join(data_dir(), "cfo_buys.json")
FUND_PATH = os.path.join(data_dir(), "fundamentals.json")
BACKTEST_PATH = os.path.join(data_dir(), "backtest.json")
META_PATH = os.path.join(data_dir(), "meta.json")
