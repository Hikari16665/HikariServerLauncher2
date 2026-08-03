"""Authentication handshake shared by HSL2 WebSocket endpoints."""

import json
from collections.abc import Callable
from typing import Any


def authenticate_websocket(
    websocket: Any,
    validate_token: Callable[[str], bool],
    timeout: float = 5,
) -> bool:
    """Require an auth JSON object as the first WebSocket message."""
    try:
        raw = websocket.receive(timeout=timeout)
        message = json.loads(raw or "{}")
    except (TimeoutError, TypeError, ValueError):
        message = {}

    token = message.get("token", "") if message.get("type") == "auth" else ""
    if isinstance(token, str) and token and validate_token(token):
        return True

    try:
        websocket.send(json.dumps({"type": "error", "message": "Unauthorized"}))
        websocket.close()
    except Exception:
        pass
    return False
