from pathlib import Path

from core import runtime_paths


def test_source_java_runtime_is_project_local():
    assert runtime_paths.java_runtime_dir() == Path(__file__).resolve().parent.parent / "java"


def test_packaged_java_runtime_uses_persistent_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        runtime_paths.sys, "_MEIPASS", str(tmp_path / "temporary-bundle"), raising=False
    )

    assert runtime_paths.java_runtime_dir() == tmp_path.resolve() / "java"
