import hashlib
import io
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import httpx

from core.mrpack_import import (
    _download_files,
    _jar_mod_ids,
    _load_rules,
    _loader_info,
    _parse_rules,
    _read_index,
    _remove_incompatible_files,
    _rule_matches,
    _safe_relative,
)
from core.workspace import Server, ServerType


class FakeDownloadResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.url = "https://cdn.modrinth.com/data/example.jar"
        self.headers = {"content-length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self, _size):
        yield self.payload


class FakeDownloadClient:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, _method, _url):
        return FakeDownloadResponse(self.payload)


class MrpackImportTests(unittest.TestCase):
    def test_index_rejects_duplicate_destination_paths(self):
        index = {
            "formatVersion": 1,
            "game": "minecraft",
            "versionId": "test",
            "name": "Test Pack",
            "dependencies": {"minecraft": "1.21.1", "fabric-loader": "0.16.10"},
            "files": [
                {
                    "path": "mods/example.jar",
                    "fileSize": 1,
                    "hashes": {"sha1": "0" * 40, "sha512": "0" * 128},
                    "downloads": ["https://cdn.modrinth.com/data/example.jar"],
                },
                {
                    "path": "mods/example.jar",
                    "fileSize": 1,
                    "hashes": {"sha1": "1" * 40, "sha512": "1" * 128},
                    "downloads": ["https://cdn.modrinth.com/data/example-2.jar"],
                },
            ],
        }
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as pack:
            pack.writestr("modrinth.index.json", json.dumps(index))

        with TemporaryDirectory() as temporary:
            path = Path(temporary, "pack.mrpack")
            path.write_bytes(archive.getvalue())
            with self.assertRaisesRegex(ValueError, "重复路径"):
                _read_index(path)

    @patch("core.mrpack_import.httpx.Client")
    def test_hash_failure_does_not_destroy_existing_mod(self, client):
        client.return_value = FakeDownloadClient(b"corrupt")
        with TemporaryDirectory() as temporary:
            server = Server(
                name="Test",
                server_type=ServerType.FABRIC,
                max_memory=2048,
                extra_args="",
                path=temporary,
                uuid="test",
            )
            destination = Path(temporary, "mods", "example.jar")
            destination.parent.mkdir()
            destination.write_bytes(b"known-good")
            item = {
                "path": "mods/example.jar",
                "title": "Example",
                "downloads": ["https://cdn.modrinth.com/data/example.jar"],
                "hashes": {"sha1": "0" * 40, "sha512": "0" * 128},
            }

            with self.assertRaisesRegex(RuntimeError, "哈希不匹配"):
                _download_files(Mock(), server, [item])

            self.assertEqual(destination.read_bytes(), b"known-good")
            self.assertEqual(list(destination.parent.glob(".*.hsl-part")), [])

    @patch("core.mrpack_import.httpx.Client")
    def test_verified_download_atomically_replaces_existing_mod(self, client):
        payload = b"verified jar bytes"
        client.return_value = FakeDownloadClient(payload)
        with TemporaryDirectory() as temporary:
            server = Server(
                name="Test",
                server_type=ServerType.FABRIC,
                max_memory=2048,
                extra_args="",
                path=temporary,
                uuid="test",
            )
            destination = Path(temporary, "mods", "example.jar")
            destination.parent.mkdir()
            destination.write_bytes(b"old")
            item = {
                "path": "mods/example.jar",
                "title": "Example",
                "downloads": ["https://cdn.modrinth.com/data/example.jar"],
                "hashes": {
                    "sha1": hashlib.sha1(payload).hexdigest(),
                    "sha512": hashlib.sha512(payload).hexdigest(),
                },
            }

            _download_files(Mock(), server, [item])

            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(list(destination.parent.glob(".*.hsl-part")), [])

    def test_loader_version_is_preserved(self):
        info = _loader_info({"minecraft": "1.21.1", "fabric-loader": "0.16.10"})
        self.assertEqual(info["server_type"], "Fabric")
        self.assertEqual(info["install_version"], "1.21.1|0.16.10")

    def test_incompatibility_rule_ranges_and_with(self):
        rules = _parse_rules(
            "id=sodium game=* desc=client only\n"
            "id=alpha game>=1.21.10 desc=new versions\n"
            "id=beta game<=1.21.1 game>=1.20.1 desc=range\n"
            "id=gamma with=sodium desc=conflict\n"
        )
        self.assertTrue(_rule_matches(rules[0], "sodium", "1.20.1", {"sodium"}))
        self.assertTrue(_rule_matches(rules[1], "alpha", "1.21.10", set()))
        self.assertTrue(_rule_matches(rules[2], "beta", "1.20.4", set()))
        self.assertTrue(_rule_matches(rules[3], "gamma", "1.20.4", {"sodium", "gamma"}))
        self.assertFalse(_rule_matches(rules[3], "gamma", "1.20.4", {"gamma"}))

    def test_incompatibility_rule_supports_project_or_filename_prefix(self):
        rule = _parse_rules("id=jecharacters* game=* desc=client-only pinyin search\n")[0]

        self.assertTrue(_rule_matches(rule, "jecharacters", "1.21.1", set()))
        self.assertTrue(_rule_matches(rule, "jecharacters-1.21-fabric-4.5.22", "1.21.1", set()))
        self.assertFalse(_rule_matches(rule, "jec", "1.21.1", set()))

    def test_slug_rule_matches_compact_loader_mod_id(self):
        rule = _parse_rules("id=cit-resewn game=* desc=client-only custom item textures\n")[0]

        self.assertTrue(_rule_matches(rule, "cit-resewn", "1.21.1", set()))
        self.assertTrue(_rule_matches(rule, "citresewn", "1.21.1", set()))
        self.assertFalse(_rule_matches(rule, "cit-resewn-compat", "1.21.1", set()))

    def test_jar_mod_ids_include_fabric_and_forge_metadata(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as jar:
            jar.writestr("fabric.mod.json", json.dumps({"id": "fabric-example"}))
            jar.writestr(
                "META-INF/mods.toml",
                '[[mods]]\nmodId="forge_example"\ndisplayName="Example"\n',
            )
        archive.seek(0)

        with zipfile.ZipFile(archive) as jar:
            self.assertEqual(
                _jar_mod_ids(jar),
                {"fabric-example", "forge_example"},
            )

    @patch("core.mrpack_import._lookup_project_identifiers", return_value={})
    def test_override_mod_is_removed_by_loader_mod_id(self, _lookup):
        rules = _parse_rules("id=cit-resewn game=* desc=client-only custom item textures\n")
        task = Mock()
        with TemporaryDirectory() as temporary:
            server = Path(temporary)
            mods = server / "mods"
            mods.mkdir()
            cit = mods / "citresewn-1.2.2.jar"
            compatible = mods / "server-example.jar"
            with zipfile.ZipFile(cit, "w") as jar:
                jar.writestr("fabric.mod.json", json.dumps({"id": "citresewn"}))
            with zipfile.ZipFile(compatible, "w") as jar:
                jar.writestr("fabric.mod.json", json.dumps({"id": "server_example"}))

            removed = _remove_incompatible_files(task, server, "1.21.1", rules)

            self.assertFalse(cit.exists())
            self.assertTrue(compatible.exists())
            self.assertEqual([item["path"] for item in removed], ["mods/citresewn-1.2.2.jar"])
            task.set_step.assert_called_once_with(
                "pack-verify-overrides",
                "复查覆盖目录中的不兼容项目",
            )
            task.complete_step.assert_called_once_with("pack-verify-overrides")

    def test_archive_path_cannot_escape_server(self):
        with self.assertRaises(ValueError):
            _safe_relative("../outside.jar")
        with self.assertRaises(ValueError):
            _safe_relative("C:/outside.jar")
        self.assertEqual(_safe_relative("mods/example.jar").as_posix(), "mods/example.jar")

    @patch("core.mrpack_import.ConfigKey")
    @patch("core.mrpack_import.httpx.get")
    def test_cloud_rules_are_used_when_online(self, get, config_key):
        config_key.MODPACK_INCOMPATIBLE_LIST_URL.get.return_value = "https://example.test/rules"
        response = Mock(content=b"id=sodium game=* desc=client only\n")
        response.raise_for_status.return_value = None
        get.return_value = response

        rules, source = _load_rules()

        self.assertEqual(source, "https://example.test/rules")
        self.assertEqual([rule["id"] for rule in rules], ["sodium"])

    @patch("core.mrpack_import.ConfigKey")
    @patch("core.mrpack_import.httpx.get")
    def test_cloud_rules_are_disabled_when_offline(self, get, config_key):
        config_key.MODPACK_INCOMPATIBLE_LIST_URL.get.return_value = "https://example.test/rules"
        get.side_effect = httpx.ConnectError("offline")

        rules, source = _load_rules()

        self.assertEqual(rules, [])
        self.assertIn("无法获取", source)

    @patch("core.mrpack_import.ConfigKey")
    @patch("core.mrpack_import.httpx.get")
    def test_default_cloud_url_supports_existing_configs(self, get, config_key):
        config_key.MODPACK_INCOMPATIBLE_LIST_URL.get.return_value = None
        response = Mock(content=b"id=sodium game=* desc=client only\n")
        response.raise_for_status.return_value = None
        get.return_value = response

        rules, source = _load_rules()

        self.assertEqual([rule["id"] for rule in rules], ["sodium"])
        self.assertEqual(
            source,
            "https://hsl-config.oss-cn-beijing.aliyuncs.com/incompatible.txt",
        )


if __name__ == "__main__":
    unittest.main()
