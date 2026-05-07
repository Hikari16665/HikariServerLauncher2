import secrets
import time
from typing import Any, Dict, Optional, Tuple
from flask import Request

from .config import ConfigKey, ConfigManager
from .logger import Logger


class TokenManager:
    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def generate_token(self) -> str:
        token = secrets.token_urlsafe(32)
        expiry = time.time() + (12 * 60 * 60)
        self._tokens[token] = {
            "expiry": expiry,
            "created_at": time.time()
        }
        return token

    def validate_token(self, token: str) -> bool:
        if token not in self._tokens:
            return False
        if time.time() > self._tokens[token]["expiry"]:
            del self._tokens[token]
            return False
        return True

    def revoke_token(self, token: str) -> bool:
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    def cleanup_expired(self):
        current_time = time.time()
        expired = [t for t, data in self._tokens.items() if current_time > data["expiry"]]
        for t in expired:
            del self._tokens[t]


class AuthManager:
    _instance: Optional['AuthManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._token_manager = TokenManager()
            self._check_and_generate_admin_key()
            self._initialized = True

    def _check_and_generate_admin_key(self):
        admin_key = ConfigKey.AUTH_ADMIN_KEY.get()
        if admin_key == "PLACEHOLDER":
            new_key = self._generate_admin_key()
            ConfigManager().set_and_save(ConfigKey.AUTH_ADMIN_KEY.value, new_key)
            ConfigManager().reload()
            Logger().key_generated(new_key)

    def _generate_admin_key(self) -> str:
        return secrets.token_urlsafe(32)

    def authenticate(self, request: Request) -> Tuple[bool, Optional[str], Optional[str]]:
        if not ConfigKey.AUTH_ENABLED.get():
            return True, None, None

        admin_key = ConfigKey.AUTH_ADMIN_KEY.get()
        request_key = self._extract_key_from_request(request)

        if not request_key:
            return False, None, "Missing authentication key"

        if not secrets.compare_digest(request_key, admin_key):
            return False, None, "Invalid authentication key"

        token = self._token_manager.generate_token()
        return True, token, None

    def validate_token(self, token: str) -> bool:
        if not ConfigKey.AUTH_ENABLED.get():
            return True
        return self._token_manager.validate_token(token)

    def validate_request(self, request: Request) -> Tuple[bool, Optional[str]]:
        if not ConfigKey.AUTH_ENABLED.get():
            return True, None

        token = self._extract_token_from_request(request)
        if token:
            if self._token_manager.validate_token(token):
                return True, None
            else:
                return False, "Invalid or expired token"

        admin_key = ConfigKey.AUTH_ADMIN_KEY.get()
        request_key = self._extract_key_from_request(request)

        if not request_key:
            return False, "Missing authentication key or token"

        if not secrets.compare_digest(request_key, admin_key):
            return False, "Invalid authentication key"

        return True, None

    def _extract_key_from_request(self, request: Request) -> Optional[str]:
        if request.is_json and request.json:
            body = request.json
            if isinstance(body, dict):
                return body.get('auth_key') or body.get('admin_key')

        if request.form:
            return request.form.get('auth_key') or request.form.get('admin_key')

        return None

    def _extract_token_from_request(self, request: Request) -> Optional[str]:
        if request.is_json and request.json:
            body = request.json
            if isinstance(body, dict):
                token = body.get('token')
                if token:
                    return token

        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:]

        if request.args:
            return request.args.get('token')

        return None

    def require_auth(self, request: Request) -> bool:
        valid, error = self.validate_request(request)
        return valid

    def get_auth_error(self, request: Request) -> Optional[str]:
        valid, error = self.validate_request(request)
        return error

    def revoke_token(self, token: str) -> bool:
        return self._token_manager.revoke_token(token)
