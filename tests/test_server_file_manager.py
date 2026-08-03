import io
import os
import tempfile
import unittest

from core.server_file_manager import (
    PathTraversalError,
    _safe_path,
    download_file,
    upload_stream,
    write_file,
)


class ServerFileManagerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.temp.name, "server")
        self.sibling = os.path.join(self.temp.name, "server_evil")
        os.makedirs(self.root)
        os.makedirs(self.sibling)

    def tearDown(self):
        self.temp.cleanup()

    def test_prefix_sibling_traversal_is_rejected(self):
        with self.assertRaises(PathTraversalError):
            _safe_path(self.root, "../server_evil/proof.txt")

    def test_windows_separator_traversal_is_rejected(self):
        with self.assertRaises(PathTraversalError):
            _safe_path(self.root, "..\\server_evil\\proof.txt")

    def test_normal_nested_path_remains_supported(self):
        result = write_file(self.root, "config/server.properties", "online-mode=true")
        self.assertNotIn("error", result)

    def test_upload_rejects_crafted_filename(self):
        for filename in ("../outside.txt", "..\\outside.txt", "/outside.txt"):
            self.assertIn("error", upload_stream(self.root, "", io.BytesIO(b"bad"), filename))

    def test_upload_and_download_are_streamable(self):
        result = upload_stream(self.root, "mods", io.BytesIO(b"jar"), "example.jar")
        self.assertNotIn("error", result)
        error, path, mime = download_file(self.root, "mods/example.jar")
        self.assertIsNone(error)
        self.assertEqual(
            os.path.normcase(os.path.realpath(path)),
            os.path.normcase(os.path.realpath(os.path.join(self.root, "mods", "example.jar"))),
        )
        self.assertIsNotNone(mime)


if __name__ == "__main__":
    unittest.main()
