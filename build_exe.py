"""Build a single-file executable from the CFO tracker.

Usage:
    python build_exe.py          # build a native executable (Linux here)
    python build_exe.py --clean  # remove build artifacts first

On Windows, run this same script on a Windows machine to produce
cfo-tracker.exe (a windowed, one-file executable). The .spec file is
configured with console=False so no console window appears.

Double-click the produced executable to launch the web UI, then open
http://localhost:8080 in your browser. It auto-refreshes every 60 seconds.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "cfo-tracker.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def build(clean: bool = False) -> int:
    if clean:
        for d in (DIST, BUILD):
            if d.exists():
                shutil.rmtree(d)
                print(f"Removed {d}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the CFO tracker executable")
    parser.add_argument("--clean", action="store_true", help="clean build artifacts first")
    args = parser.parse_args()
    return build(clean=args.clean)


if __name__ == "__main__":
    raise SystemExit(main())
