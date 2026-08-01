import io
import json
import unittest
import zipfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.server_diagnostics import AddonMetadata, _inspect_jar_archive
from core.server_process import _with_nogui
from core.modrinth_market import _dependency_tree, _installed_compatible_projects
from core.workspace import Server, ServerType


def make_jar(files: dict[str, str | bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as jar:
        for path, content in files.items():
            jar.writestr(path, content)
    return output.getvalue()


class AddonInspectionTests(unittest.TestCase):
    def test_nogui_is_appended_exactly_once(self):
        self.assertEqual(_with_nogui(["java", "-jar", "server.jar"])[-1], "nogui")
        command = ["java", "-jar", "server.jar", "nogui"]
        self.assertEqual(_with_nogui(command).count("nogui"), 1)

    def test_multi_environment_and_nested_jar_dependencies(self):
        nested = make_jar({
            "META-INF/mods.toml": '[[mods]]\nmodId="nested_lib"\ndisplayName="Nested"\n',
        })
        outer = make_jar({
            "fabric.mod.json": json.dumps({
                "id": "dualmod",
                "name": "Dual",
                "depends": {"minecraft": ">=1.20", "nested_lib": "*"},
            }),
            "plugin.yml": "name: DualPlugin\ndepend: [Vault]\n",
            "META-INF/jars/nested.jar": nested,
        })

        metadata = AddonMetadata("dual.jar", "dual")
        with zipfile.ZipFile(io.BytesIO(outer)) as jar:
            _inspect_jar_archive(jar, metadata, embedded=False, depth=0)

        self.assertEqual(metadata.kinds, {"fabric", "plugin"})
        self.assertIn("dualmod", metadata.addon_ids)
        self.assertIn("DualPlugin", metadata.addon_ids)
        self.assertIn("nested_lib", metadata.embedded_ids)
        self.assertEqual(metadata.dependencies["fabric"], {"nested_lib"})
        self.assertEqual(metadata.dependencies["plugin"], {"Vault"})

    def test_installed_compatible_dependency_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mods").mkdir()
            (root / "mods" / "library.jar").write_bytes(b"installed")
            (root / ".hslmeta").write_text("mc_version: 1.20.1\n", encoding="utf-8")
            (root / ".hsl-addons.json").write_text(json.dumps({
                "library.jar": {"project_id": "library", "version_id": "library-v1"},
            }), encoding="utf-8")
            server = Server("Test", ServerType.FABRIC, 2048, "", directory, uuid="test")
            installed_version = {"id": "library-v1", "project_id": "library", "loaders": ["fabric"], "game_versions": ["1.20.1"]}

            with patch("core.modrinth_market._get", return_value=installed_version):
                installed = _installed_compatible_projects(server)
                dependencies = _dependency_tree(server, {"dependencies": [{"dependency_type": "required", "project_id": "library", "version_id": "library-v1"}]}, set(), installed)

            self.assertEqual(installed, {"library"})
            self.assertEqual(dependencies, [])


if __name__ == "__main__":
    unittest.main()
