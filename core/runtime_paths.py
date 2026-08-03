"""Stable writable paths shared by source and packaged backend builds."""

import sys
from pathlib import Path


def data_root() -> Path:
    """Return the directory that owns config, workspaces and managed runtimes.

    PyInstaller's ``_MEIPASS`` points at bundled application files. In one-file
    mode it is temporary, and in an installed one-dir build it can be replaced
    during upgrades. The launcher's working directory is the persistent install
    data root, matching ConfigManager's packaged-build behaviour.
    """

    if getattr(sys, "frozen", False):
        return Path.cwd().resolve()
    return Path(__file__).resolve().parent.parent


def java_runtime_dir() -> Path:
    return data_root() / "java"
