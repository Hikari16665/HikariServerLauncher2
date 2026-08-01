import io
import json
import unittest
import zipfile
from unittest.mock import Mock, patch

import httpx

from core.mrpack_import import (
    _jar_mod_ids,
    _load_rules,
    _loader_info,
    _parse_rules,
    _rule_matches,
    _safe_relative,
)


class MrpackImportTests(unittest.TestCase):
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
        rule = _parse_rules(
            "id=jecharacters* game=* desc=client-only pinyin search\n"
        )[0]

        self.assertTrue(_rule_matches(rule, "jecharacters", "1.21.1", set()))
        self.assertTrue(
            _rule_matches(rule, "jecharacters-1.21-fabric-4.5.22", "1.21.1", set())
        )
        self.assertFalse(_rule_matches(rule, "jec", "1.21.1", set()))

    def test_slug_rule_matches_compact_loader_mod_id(self):
        rule = _parse_rules(
            "id=cit-resewn game=* desc=client-only custom item textures\n"
        )[0]

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
