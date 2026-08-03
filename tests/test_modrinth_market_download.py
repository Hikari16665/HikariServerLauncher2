from pathlib import Path

import pytest

from core import modrinth_market


class FakeTask:
    def set_metrics(self, **_metrics):
        pass

    def set_progress(self, _progress, _message):
        pass


class FakeResponse:
    def __init__(self, chunks, content_length=None, error=None):
        self.chunks = chunks
        self.error = error
        self.headers = {}
        if content_length is not None:
            self.headers["content-length"] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self, _size):
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

    def stream(self, _method, _url):
        return self.response


def use_response(monkeypatch, response):
    monkeypatch.setattr(
        modrinth_market.httpx,
        "Client",
        lambda **_kwargs: FakeClient(response),
    )


def partial_files(directory: Path):
    return list(directory.glob("*.hsl-part")) + list(directory.glob(".*.hsl-part"))


def test_download_atomically_replaces_destination(tmp_path, monkeypatch):
    destination = tmp_path / "addon.jar"
    destination.write_bytes(b"old")
    use_response(monkeypatch, FakeResponse([b"new", b" data"], content_length=8))

    modrinth_market._download(
        FakeTask(), "https://example.invalid/addon.jar", str(destination), 0, 100
    )

    assert destination.read_bytes() == b"new data"
    assert partial_files(tmp_path) == []


def test_failed_download_preserves_existing_destination(tmp_path, monkeypatch):
    destination = tmp_path / "addon.jar"
    destination.write_bytes(b"known-good")
    use_response(monkeypatch, FakeResponse([b"partial"], error=RuntimeError("network lost")))

    with pytest.raises(RuntimeError, match="network lost"):
        modrinth_market._download(
            FakeTask(), "https://example.invalid/addon.jar", str(destination), 0, 100
        )

    assert destination.read_bytes() == b"known-good"
    assert partial_files(tmp_path) == []


def test_declared_oversized_download_is_rejected_without_replacing_file(tmp_path, monkeypatch):
    destination = tmp_path / "addon.jar"
    destination.write_bytes(b"known-good")
    use_response(
        monkeypatch,
        FakeResponse([], content_length=modrinth_market.MAX_ADDON_DOWNLOAD_BYTES + 1),
    )

    with pytest.raises(ValueError, match="2 GB"):
        modrinth_market._download(
            FakeTask(), "https://example.invalid/addon.jar", str(destination), 0, 100
        )

    assert destination.read_bytes() == b"known-good"
    assert partial_files(tmp_path) == []
