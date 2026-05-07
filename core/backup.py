"""BackupManager — create, list, restore, and delete server backups.

Backups are zip archives stored in a configurable backup directory.
Each backup is named: <server_uuid>_YYYY-MM-DD_HH-MM-SS.zip
Files within the zip use arcnames relative to the server's own path
for portability, with "/" separators regardless of platform.
"""

import os
import re
import sys
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import ConfigKey

BACKUP_FILENAME_RE = re.compile(
    r"^[0-9a-fA-F-]+_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.zip$"
)


class BackupManager:
    _instance: Optional["BackupManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True

    def _get_backup_dir(self) -> str:
        relative = ConfigKey.BACKUP_DIR.get()
        base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(__file__))
        return os.path.join(base, relative)

    def _ensure_backup_dir(self) -> str:
        d = self._get_backup_dir()
        os.makedirs(d, exist_ok=True)
        return d

    def create_backup_sync(
        self, server_path: str, server_uuid: str, task=None
    ) -> str:
        """Create a zip backup of a server directory. Returns the filename."""
        backup_dir = self._ensure_backup_dir()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{server_uuid}_{timestamp}.zip"
        full_path = os.path.join(backup_dir, filename)

        all_files = []
        for root, _dirs, files in os.walk(server_path):
            for fn in files:
                file_path = os.path.join(root, fn)
                arcname = os.path.relpath(file_path, start=server_path).replace(
                    "\\", "/"
                )
                all_files.append((file_path, arcname))

        total = len(all_files) or 1

        with zipfile.ZipFile(
            full_path, "w", compresslevel=9, compression=zipfile.ZIP_DEFLATED
        ) as zf:
            for idx, (file_path, arcname) in enumerate(all_files):
                zf.write(file_path, arcname=arcname)
                if task and (idx + 1) % 100 == 0:
                    pct = int((idx + 1) / total * 100)
                    task.set_progress(pct, f"Backing up: {arcname}")

        if task:
            task.set_progress(100, f"Backup created: {filename}")
        return filename

    def list_backups(self, server_uuid: str) -> List[Dict[str, Any]]:
        """List backups for a server UUID."""
        backup_dir = self._get_backup_dir()
        if not os.path.exists(backup_dir):
            return []

        results = []
        prefix = f"{server_uuid}_"
        for entry in os.listdir(backup_dir):
            if entry.startswith(prefix) and BACKUP_FILENAME_RE.match(entry):
                full_path = os.path.join(backup_dir, entry)
                stat = os.stat(full_path)
                results.append(
                    {
                        "filename": entry,
                        "server_uuid": server_uuid,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                    }
                )
        results.sort(key=lambda b: b["created"], reverse=True)
        return results

    def restore_backup_sync(
        self, server_path: str, backup_filename: str, task=None
    ) -> bool:
        """Restore a backup to the server directory.

        Deletes the existing server directory contents first.
        """
        import shutil

        backup_dir = self._get_backup_dir()
        full_path = os.path.join(backup_dir, backup_filename)
        if not os.path.exists(full_path):
            raise FileNotFoundError(
                f"Backup file not found: {backup_filename}"
            )

        if task:
            task.set_progress(5, "Removing existing server files...")
        if os.path.exists(server_path):
            shutil.rmtree(server_path)
        os.makedirs(server_path, exist_ok=True)

        if task:
            task.set_progress(10, "Extracting backup...")
        with zipfile.ZipFile(full_path, "r") as zf:
            name_list = zf.namelist()
            total = len(name_list) or 1
            for idx, member in enumerate(name_list):
                zf.extract(member, server_path)
                if task and (idx + 1) % 100 == 0:
                    pct = 10 + int((idx + 1) / total * 85)
                    task.set_progress(pct, f"Restoring: {member}")

        if task:
            task.set_progress(100, "Backup restored successfully")
        return True

    def delete_backup(self, backup_filename: str) -> bool:
        """Delete a backup file. Returns True if deleted."""
        full_path = os.path.join(self._get_backup_dir(), backup_filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
