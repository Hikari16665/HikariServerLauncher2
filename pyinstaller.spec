# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Hikari Server Launcher backend."""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all core submodules
hidden_imports = collect_submodules("core")
hidden_imports += [
    "flask",
    "flask_cors",
    "flask_sock",
    "yaml",
    "rich",
    "javaproperties",
    "regex",
    "psutil",
    "httpx",
    "pydantic",
    "base64",
    "stun",
]

# Collect data files
datas = [
    ("install", "install"),
    ("index.html", "."),
    ("source.json", "."),
    ("stun_valid_hosts.txt", "."),
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
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
    [],
    exclude_binaries=True,
    name="hsl-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="hsl-server",
)
