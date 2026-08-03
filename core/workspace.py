import os
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml

from .config import ConfigKey


class ServerType(Enum):
    VANILLA = "Vanilla"
    PAPER = "Paper"
    FORGE = "Forge"
    FABRIC = "Fabric"
    NEOFORGE = "NeoForge"
    APRIL = "April"

    @staticmethod
    def from_str(value: str) -> "ServerType":
        return ServerType(value)


@dataclass
class Server:
    name: str
    server_type: ServerType
    max_memory: int
    extra_args: str
    path: str
    uuid: str = ""
    java_version: str = "21"
    valid: bool = True

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "server_type": self.server_type.value,
            "max_memory": self.max_memory,
            "extra_args": self.extra_args,
            "path": self.path,
            "java_version": self.java_version,
            "valid": self.valid,
        }


@dataclass
class ServerCollection:
    servers: list[Server] = field(default_factory=list)

    def add(self, server: Server):
        self.servers.append(server)

    def get_by_name(self, name: str) -> Server | None:
        for server in self.servers:
            if server.name == name:
                return server
        return None

    def get_by_uuid(self, uuid: str) -> Server | None:
        for server in self.servers:
            if server.uuid == uuid:
                return server
        return None

    def get_by_path(self, path: str) -> Server | None:
        for server in self.servers:
            if server.path == path:
                return server
        return None

    def get_valid_servers(self) -> list[Server]:
        return [s for s in self.servers if s.valid]

    def get_invalid_servers(self) -> list[Server]:
        return [s for s in self.servers if not s.valid]

    def __iter__(self):
        return iter(self.servers)

    def __len__(self):
        return len(self.servers)


class WorkspaceManager:
    _instance: Optional["WorkspaceManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._workspace_path: str | None = None
            self._servers: ServerCollection = ServerCollection()
            self._initialized = True

    def _get_workspace_path(self) -> str:
        if self._workspace_path is None:
            relative_path = ConfigKey.WORKSPACE_PATH.get()
            base_dir = (
                sys._MEIPASS  # type: ignore
                if getattr(sys, "frozen", False)
                else os.path.dirname(os.path.dirname(__file__))
            )
            self._workspace_path = os.path.join(base_dir, relative_path)
        return self._workspace_path

    def _ensure_workspace_exists(self):
        workspace = self._get_workspace_path()
        if not os.path.exists(workspace):
            os.makedirs(workspace, exist_ok=True)

    def _parse_server_type(self, type_str: str | None) -> ServerType:
        if not type_str:
            return ServerType.VANILLA
        for st in ServerType:
            if st.value.lower() == type_str.lower():
                return st
        return ServerType.VANILLA

    def _load_server_meta(self, server_dir: str) -> Server | None:
        meta_file = os.path.join(server_dir, ".hslmeta")
        if not os.path.exists(meta_file):
            return None

        try:
            with open(meta_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return None

        server_uuid = data.get("uuid") or os.path.basename(server_dir)
        name = data.get("name") or os.path.basename(server_dir)
        server_type_str = data.get("type")
        server_type = self._parse_server_type(server_type_str)
        java_version = data.get("java_version") or "21"
        max_memory = data.get("max_memory", 1024)
        extra_args = data.get("extra_args", "")

        return Server(
            uuid=server_uuid,
            name=name,
            server_type=server_type,
            max_memory=max_memory,
            extra_args=extra_args,
            path=server_dir,
            java_version=java_version,
        )

    def _scan_workspace(self):
        self._servers = ServerCollection()
        self._ensure_workspace_exists()

        workspace = self._get_workspace_path()
        if not os.path.exists(workspace):
            return

        for entry in os.listdir(workspace):
            full_path = os.path.join(workspace, entry)
            if not os.path.isdir(full_path):
                continue

            server = self._load_server_meta(full_path)
            if server:
                self._servers.add(server)

    def refresh(self):
        self._scan_workspace()

    @property
    def workspace_path(self) -> str:
        return self._get_workspace_path()

    @property
    def servers(self) -> ServerCollection:
        if not self._servers.servers:
            self._scan_workspace()
        return self._servers

    def get_all_servers(self) -> list[Server]:
        return self.servers.servers

    def get_valid_servers(self) -> list[Server]:
        return self.servers.get_valid_servers()

    def get_server(self, name: str) -> Server | None:
        return self.servers.get_by_name(name)

    def get_server_by_uuid(self, uuid: str) -> Server | None:
        return self.servers.get_by_uuid(uuid)

    def get_server_by_path(self, path: str) -> Server | None:
        return self.servers.get_by_path(path)

    def get_server_count(self) -> int:
        return len(self.servers)

    def is_valid_server(self, name: str) -> bool:
        server = self.get_server(name)
        return server is not None and server.valid

    def create_server(
        self,
        name: str,
        server_type: ServerType,
        max_memory: int = 1024,
        extra_args: str = "",
        java_version: str = "",
    ) -> Server:
        self._ensure_workspace_exists()

        server_id = str(uuid.uuid4())
        server_dir = os.path.join(self._get_workspace_path(), server_id)

        os.makedirs(server_dir, exist_ok=True)

        meta_data = {
            "uuid": server_id,
            "name": name,
            "type": server_type.value,
            "max_memory": max_memory,
            "extra_args": extra_args,
            "java_version": java_version,
        }

        meta_file = os.path.join(server_dir, ".hslmeta")
        with open(meta_file, "w", encoding="utf-8") as f:
            yaml.dump(meta_data, f, allow_unicode=True, default_flow_style=False)

        server = Server(
            uuid=server_id,
            name=name,
            server_type=server_type,
            max_memory=max_memory,
            extra_args=extra_args,
            path=server_dir,
            java_version=java_version or "21",
            valid=True,
        )

        self._servers.add(server)

        return server

    def remove_server(self, server_uuid: str, delete_files: bool = False) -> bool:
        server = self.get_server_by_uuid(server_uuid)
        if server is None:
            return False

        if delete_files:
            workspace_path = os.path.realpath(self._get_workspace_path())
            server_path = os.path.realpath(server.path)
            if os.path.dirname(server_path) != workspace_path:
                raise ValueError("拒绝删除工作区之外的服务器目录")
            shutil.rmtree(server_path, ignore_errors=True)

        self._servers.servers = [item for item in self._servers.servers if item.uuid != server_uuid]
        return True
