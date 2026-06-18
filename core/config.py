import os
import shutil
import sys
from enum import Enum
from typing import Any, Optional

import yaml


def get_root_path() -> str:
    """Get project root, handling PyInstaller bundling."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))


class ConfigKey(Enum):
    APP_NAME = "app.name"
    APP_HOST = "app.host"
    APP_PORT = "app.port"
    APP_FLASK_DEBUG = "app.flask-debug"
    AUTH_ENABLED = "auth.enabled"
    AUTH_ADMIN_KEY = "auth.admin-key"
    WORKSPACE_PATH = "workspace.path"
    SERVER_JAVA_AUTO_DOWNLOAD = "server.java.auto_download"
    BACKUP_DIR = "backup.dir"
    TUI_ENABLED = "tui.enabled"

    def get(self) -> Any:
        return ConfigManager().get(self.value)

    def set(self, value: Any, save_immediately: bool = False) -> None:
        ConfigManager().set(self.value, value, save_immediately)


class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    _cache: dict[str, Any] = {}
    _config_path: str = os.path.join(
        os.getcwd()
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.dirname(__file__)),
        "config.yml",
    )
    _default_config_path: str = os.path.join(get_root_path(), "install", "default_config.yml")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._ensure_config_exists()
            self._load_config()
            self._initialized = True

    def _ensure_config_exists(self):
        if not os.path.exists(self._config_path):
            if os.path.exists(self._default_config_path):
                shutil.copy(self._default_config_path, self._config_path)
            else:
                raise FileNotFoundError(f"Default config not found at {self._default_config_path}")

    def _load_config(self):
        with open(self._config_path, encoding="utf-8") as f:
            self._cache = yaml.safe_load(f) or {}

    def _get_nested(self, data: dict[str, Any], key: str) -> Any:
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    def _set_nested(self, data: dict[str, Any], key: str, value: Any):
        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def get(self, key: str, use_cache: bool = True) -> Any:
        if use_cache:
            return self._get_nested(self._cache, key)
        else:
            with open(self._config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return self._get_nested(data, key)

    def get_no_cache(self, key: str) -> Any:
        return self.get(key, use_cache=False)

    def set(self, key: str, value: Any, save_immediately: bool = False):
        self._set_nested(self._cache, key, value)
        if save_immediately:
            self.save()

    def set_and_save(self, key: str, value: Any):
        self.set(key, value, save_immediately=True)

    def save(self):
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._cache, f, allow_unicode=True, default_flow_style=False)

    def reload(self):
        self._cache = {}
        self._load_config()
