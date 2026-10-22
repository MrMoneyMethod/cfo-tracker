# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("static", "static"),
        ("templates", "templates"),
        ("data", "data"),
    ],
    hiddenimports=[
        "flask",
        "apscheduler",
        "apscheduler.schedulers.background",
        "apscheduler.executors.pool",
        "apscheduler.jobstores.memory",
        "yfinance",
        "requests",
        "bs4",
        "lxml",
        "pandas",
        "numpy",
        "dateutil",
        "multiprocessing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="cfo-tracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed (no console window) on Windows
    disabled_windowed=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)


