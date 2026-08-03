import json

from core.websocket_auth import authenticate_websocket


class FakeWebSocket:
    def __init__(self, first_message=None, error=None):
        self.first_message = first_message
        self.error = error
        self.timeout = None
        self.sent = []
        self.closed = False

    def receive(self, timeout=None):
        self.timeout = timeout
        if self.error:
            raise self.error
        return self.first_message

    def send(self, message):
        self.sent.append(json.loads(message))

    def close(self):
        self.closed = True


def test_accepts_valid_token_in_auth_first_frame():
    websocket = FakeWebSocket(json.dumps({"type": "auth", "token": "valid"}))

    assert authenticate_websocket(websocket, lambda token: token == "valid")
    assert websocket.timeout == 5
    assert websocket.sent == []
    assert not websocket.closed


def test_rejects_invalid_token_and_closes_connection():
    websocket = FakeWebSocket(json.dumps({"type": "auth", "token": "wrong"}))

    assert not authenticate_websocket(websocket, lambda _token: False)
    assert websocket.sent == [{"type": "error", "message": "Unauthorized"}]
    assert websocket.closed


def test_rejects_non_auth_first_frame():
    websocket = FakeWebSocket(json.dumps({"type": "command", "command": "stop"}))

    assert not authenticate_websocket(websocket, lambda _token: True)
    assert websocket.closed


def test_authentication_timeout_closes_connection():
    websocket = FakeWebSocket(error=TimeoutError())

    assert not authenticate_websocket(websocket, lambda _token: True)
    assert websocket.closed
