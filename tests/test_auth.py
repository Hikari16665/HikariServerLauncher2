from flask import Flask, request

from core.auth import AuthManager, TokenManager


def test_token_manager_evicts_oldest_token(monkeypatch):
    manager = TokenManager()
    monkeypatch.setattr(manager, "MAX_ACTIVE_TOKENS", 2)
    times = iter([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    monkeypatch.setattr("core.auth.time.time", lambda: next(times))

    first = manager.generate_token()
    second = manager.generate_token()
    third = manager.generate_token()

    assert not manager.validate_token(first)
    assert manager.validate_token(second)
    assert manager.validate_token(third)


def test_http_token_must_not_be_read_from_query_string():
    app = Flask(__name__)
    manager = object.__new__(AuthManager)

    with app.test_request_context("/api/test?token=leaked"):
        assert manager._extract_token_from_request(request) is None


def test_http_token_is_read_from_bearer_header():
    app = Flask(__name__)
    manager = object.__new__(AuthManager)

    with app.test_request_context("/api/test", headers={"Authorization": "Bearer secret"}):
        assert manager._extract_token_from_request(request) == "secret"
