import os
import tempfile
import unittest
import zipfile

from core.backup import BackupManager


class BackupSafetyTests(unittest.TestCase):
    def test_archive_traversal_is_rejected_before_existing_data_is_removed(self):
        with tempfile.TemporaryDirectory() as root:
            server = os.path.join(root, "server")
            backups = os.path.join(root, "backups")
            os.makedirs(server)
            os.makedirs(backups)
            marker = os.path.join(server, "world.dat")
            with open(marker, "w", encoding="utf-8") as output:
                output.write("keep")
            archive = os.path.join(backups, "bad.zip")
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../escaped.txt", "bad")

            manager = BackupManager()
            original = manager._get_backup_dir
            manager._get_backup_dir = lambda: backups
            try:
                with self.assertRaises(ValueError):
                    manager.restore_backup_sync(server, "bad.zip")
            finally:
                manager._get_backup_dir = original

            self.assertTrue(os.path.isfile(marker))
            self.assertFalse(os.path.exists(os.path.join(root, "escaped.txt")))

    def test_valid_backup_replaces_server_after_successful_extraction(self):
        with tempfile.TemporaryDirectory() as root:
            server = os.path.join(root, "server")
            backups = os.path.join(root, "backups")
            os.makedirs(server)
            os.makedirs(backups)
            with open(os.path.join(server, "old.txt"), "w", encoding="utf-8") as output:
                output.write("old")
            archive = os.path.join(backups, "good.zip")
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("world/new.txt", "new")

            manager = BackupManager()
            original = manager._get_backup_dir
            manager._get_backup_dir = lambda: backups
            try:
                manager.restore_backup_sync(server, "good.zip")
            finally:
                manager._get_backup_dir = original

            self.assertFalse(os.path.exists(os.path.join(server, "old.txt")))
            self.assertTrue(os.path.isfile(os.path.join(server, "world", "new.txt")))


if __name__ == "__main__":
    unittest.main()
