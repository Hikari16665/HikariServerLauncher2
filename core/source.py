import json
import os
import shutil
import sys
from typing import Optional

from pydantic import BaseModel


class VanillaSource(BaseModel):
    type: str
    versionList: str
    server: str


class Vanilla(BaseModel):
    list: list[VanillaSource]


class PaperSource(BaseModel):
    type: str
    latest: str


class Paper(BaseModel):
    latestVersionName: str
    experimentalVersionName: str
    list: list[PaperSource]


class AprilVersion(BaseModel):
    version: str
    name: str
    link: str


class April(BaseModel):
    list: list[AprilVersion]


class MC(BaseModel):
    vanilla: Vanilla
    paper: Paper
    april: April


class ForgeSource(BaseModel):
    type: str
    metadata: str | None
    download: str | None
    supportList: str | None
    getByVersion: str | None


class Forge(BaseModel):
    list: list[ForgeSource]


class NeoForgeSource(BaseModel):
    type: str
    getByVersion: str
    download: str


class NeoForge(BaseModel):
    list: list[NeoForgeSource]


class FabricSource(BaseModel):
    type: str
    supportList: str
    loaderList: str
    installer: str


class Fabric(BaseModel):
    list: list[FabricSource]


class JavaSource(BaseModel):
    type: str
    windows: dict[str, str]
    linux: dict[str, str]


class Java(BaseModel):
    list: list[JavaSource]


class OpenFrp(BaseModel):
    pwdLogin: str
    authCode: str
    codeLogin: str
    getUserInfo: str
    getUserProxies: str
    newProxy: str
    removeProxy: str
    getNodeList: str
    editProxy: str


class Source(BaseModel):
    mc: MC
    forge: Forge
    neoforge: NeoForge
    fabric: Fabric
    java: Java
    openfrp: OpenFrp


class SourceManager:
    _instance: Optional["SourceManager"] = None
    _cache: Source | None = None
    _source_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "source.json")
    _default_source_path: str = os.path.join(
        sys._MEIPASS
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.dirname(__file__)),
        "install",
        "default_source.json",
    )

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._ensure_source_exists()
            self._load_source()
            self._initialized = True

    def _ensure_source_exists(self):
        if not os.path.exists(self._source_path):
            if os.path.exists(self._default_source_path):
                shutil.copy(self._default_source_path, self._source_path)
            else:
                raise FileNotFoundError(f"Default source not found at {self._default_source_path}")

    def _load_source(self):
        with open(self._source_path, encoding="utf-8") as f:
            data = json.load(f)
            self._cache = Source(**data)

    def get(self, use_cache: bool = True) -> Source:
        if use_cache and self._cache is not None:
            return self._cache
        self._load_source()
        return self._cache

    def get_no_cache(self) -> Source:
        return self.get(use_cache=False)

    def reload(self):
        self._cache = None
        self._load_source()
