import io
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from core import server_creator


class FakeResponse:
    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error
        self.headers = {"content-length": str(sum(len(chunk) for chunk in chunks))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None):
        assert chunk_size
        yield from self.chunks
        if self.error:
            raise self.error


class FakeClient:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, _method, _url, follow_redirects=True):
        assert follow_redirects
        return self.response


def use_response(monkeypatch, response):
    monkeypatch.setattr(
        server_creator.httpx,
        "Client",
        lambda **_kwargs: FakeClient(response),
    )


def temporary_files(directory: Path):
    return list(directory.glob(".*.hsl-part")) + list(directory.glob(".*.hsl-attempt"))


def test_interrupted_server_download_preserves_existing_file(tmp_path, monkeypatch):
    destination = tmp_path / "server.jar"
    destination.write_bytes(b"known-good")
    use_response(monkeypatch, FakeResponse([b"partial"], RuntimeError("network lost")))

    with pytest.raises(RuntimeError, match="network lost"):
        server_creator._download_file(
            "https://example.invalid/server.jar", str(destination), Mock()
        )

    assert destination.read_bytes() == b"known-good"
    assert temporary_files(tmp_path) == []


def test_successful_server_download_atomically_replaces_file(tmp_path, monkeypatch):
    destination = tmp_path / "server.jar"
    destination.write_bytes(b"old")
    use_response(monkeypatch, FakeResponse([b"new", b" server"]))

    server_creator._download_file("https://example.invalid/server.jar", str(destination), Mock())

    assert destination.read_bytes() == b"new server"
    assert temporary_files(tmp_path) == []


def test_invalid_forge_candidate_does_not_replace_existing_installer(tmp_path, monkeypatch):
    destination = tmp_path / "forge-installer.jar"
    destination.write_bytes(b"known-good")
    use_response(monkeypatch, FakeResponse([b"not a zip archive"]))

    with pytest.raises(RuntimeError, match="All Forge installer sources failed"):
        server_creator._download_first_available(
            ["https://example.invalid/forge.jar"], str(destination), Mock()
        )

    assert destination.read_bytes() == b"known-good"
    assert temporary_files(tmp_path) == []


def test_java_archive_rejects_path_traversal(tmp_path):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../outside.txt", "escape")
    payload.seek(0)

    with zipfile.ZipFile(payload) as archive, pytest.raises(ValueError, match="不安全路径"):
        server_creator._safe_extract_java_archive(archive, tmp_path / "staging")

    assert not (tmp_path / "outside.txt").exists()


def test_java_archive_rejects_symbolic_links(tmp_path):
    payload = io.BytesIO()
    entry = zipfile.ZipInfo("jdk/bin/java")
    entry.create_system = 3
    entry.external_attr = (0o120777 << 16) | 0xA0000000
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(entry, "../../outside")
    payload.seek(0)

    with zipfile.ZipFile(payload) as archive, pytest.raises(ValueError, match="不安全路径"):
        server_creator._safe_extract_java_archive(archive, tmp_path / "staging")


def test_java_archive_extracts_single_runtime_root(tmp_path, monkeypatch):
    monkeypatch.setattr(server_creator.platform, "system", lambda: "Windows")
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("jdk-21/bin/java.exe", b"binary")
        archive.writestr("jdk-21/release", b"JAVA_VERSION=21")
    payload.seek(0)
    staging = tmp_path / "staging"
    staging.mkdir()

    with zipfile.ZipFile(payload) as archive:
        server_creator._safe_extract_java_archive(archive, staging)

    assert server_creator._find_java_archive_root(staging) == staging / "jdk-21"
