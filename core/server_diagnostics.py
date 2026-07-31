"""Local Minecraft server diagnostics.

The scanner deliberately avoids network requests: every result is derived from the
selected server directory, so a check is fast and deterministic.
"""

from __future__ import annotations

import json
import os
import re
import time
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import javaproperties
import yaml

from .workspace import Server, ServerType


LEVELS = ("exception", "severe_warning", "warning", "info")
BUILTIN_DEPENDENCIES = {
    "minecraft", "java", "fabricloader", "fabric-loader", "forge", "neoforge",
    "fabric", "paper", "bukkit", "spigot",
}


@dataclass
class AddonMetadata:
    filename: str
    name: str
    kind: str
    addon_ids: set[str] = field(default_factory=set)
    dependencies: set[str] = field(default_factory=set)
    minecraft_constraint: Any = None
    parse_error: str | None = None


def diagnose_server(server: Server) -> dict[str, Any]:
    started = time.monotonic()
    issues: list[dict[str, Any]] = []
    root = Path(server.path)

    def add(level: str, code: str, title: str, message: str, *, file: str | None = None, details: dict[str, Any] | None = None) -> None:
        issues.append({
            "level": level,
            "code": code,
            "title": title,
            "message": message,
            "file": file,
            "details": details or {},
        })

    _check_eula(root, add)
    properties = _load_properties(root / "server.properties", add)
    if properties is not None:
        _check_properties(properties, add)
    _check_server_core(root, server, add)
    addon_count = _check_addons(root, server, add)

    order = {level: index for index, level in enumerate(LEVELS)}
    issues.sort(key=lambda item: (order[item["level"]], item["title"], item.get("file") or ""))
    summary = {level: sum(item["level"] == level for item in issues) for level in LEVELS}
    return {
        "server_uuid": server.uuid,
        "server_name": server.name,
        "checked_at": time.time(),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "addon_count": addon_count,
        "summary": summary,
        "issues": issues,
        "healthy": not any(item["level"] in {"exception", "severe_warning", "warning"} for item in issues),
    }


def _check_eula(root: Path, add) -> None:
    path = root / "eula.txt"
    accepted = False
    try:
        with path.open("rb") as file:
            accepted = str(javaproperties.load(file).get("eula", "")).strip().lower() == "true"
    except (OSError, ValueError):
        pass
    if not accepted:
        add("exception", "eula_not_accepted", "尚未签署 Minecraft EULA", "eula.txt 中必须存在 eula=true，否则服务器将拒绝启动。", file="eula.txt")


def _load_properties(path: Path, add) -> dict[str, str] | None:
    try:
        with path.open("rb") as file:
            return {str(key): str(value) for key, value in javaproperties.load(file).items()}
    except FileNotFoundError:
        add("warning", "properties_missing", "缺少 server.properties", "服务器配置文件不存在；首次启动可能尚未完成，或核心文件无法正常运行。", file="server.properties")
    except (OSError, ValueError) as error:
        add("warning", "properties_unreadable", "无法读取 server.properties", f"配置文件无法解析：{error}", file="server.properties")
    return None


def _check_properties(properties: dict[str, str], add) -> None:
    if properties.get("online-mode", "true").strip().lower() == "false":
        add("severe_warning", "offline_mode", "服务器未开启正版验证", "服务器未开启正版验证，在未安装登录插件的情况下可能会有盗号、毁服风险。", file="server.properties", details={"key": "online-mode", "value": "false"})

    if properties.get("enable-rcon", "false").strip().lower() == "true":
        password = properties.get("rcon.password", "").strip()
        if not password or password.lower() in {"password", "changeme", "minecraft", "123456"}:
            add("severe_warning", "weak_rcon_password", "RCON 密码不安全", "RCON 已启用，但密码为空或使用了常见默认值；暴露端口后可能被直接取得服务器控制权。", file="server.properties", details={"key": "rcon.password"})

    for key, limit, label in (("view-distance", 32, "视距"), ("simulation-distance", 16, "模拟距离")):
        try:
            value = int(properties.get(key, "0"))
        except ValueError:
            continue
        if value > limit:
            add("info", f"high_{key.replace('-', '_')}", f"{label}设置过大", f"{key} 当前为 {value}，超过建议关注值 {limit}，可能会造成巨大带宽压力。", file="server.properties", details={"key": key, "value": value, "threshold": limit})


def _check_server_core(root: Path, server: Server, add) -> None:
    candidates = list(root.glob("*.jar")) + list(root.glob("run.bat")) + list(root.glob("run.sh"))
    if server.server_type in {ServerType.FORGE, ServerType.NEOFORGE}:
        candidates += list(root.glob("libraries/**/unix_args.txt")) + list(root.glob("libraries/**/win_args.txt"))
    if not candidates:
        add("exception", "server_core_missing", "未找到服务端核心文件", "服务器目录中没有可启动的 JAR、运行脚本或 Forge/NeoForge 参数文件，服务器可能无法启动。")


def _check_addons(root: Path, server: Server, add) -> int:
    folder = "plugins" if server.server_type == ServerType.PAPER else "mods"
    directory = root / folder
    if not directory.is_dir():
        return 0
    jars = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".jar")
    metadata = [_inspect_addon(path) for path in jars]
    installed_ids: set[str] = set()
    for item in metadata:
        installed_ids.update(value.lower() for value in item.addon_ids)
        installed_ids.add(Path(item.filename).stem.lower())

    expected = {
        ServerType.FABRIC: {"fabric"},
        ServerType.FORGE: {"forge"},
        ServerType.NEOFORGE: {"forge", "neoforge"},
        ServerType.PAPER: {"plugin"},
    }.get(server.server_type)
    game_version = _minecraft_version(root)

    for item in metadata:
        if item.parse_error:
            add("warning", "invalid_addon", f"无法解析附加：{item.name}", item.parse_error, file=f"{folder}/{item.filename}")
            continue
        if expected and item.kind not in expected:
            add("warning", "wrong_addon_loader", f"附加类型不兼容：{item.name}", f"该文件被识别为 {_kind_label(item.kind)}，但当前服务器类型为 {server.server_type.value}。", file=f"{folder}/{item.filename}", details={"detected_loader": item.kind, "server_type": server.server_type.value})
        if game_version and item.minecraft_constraint and not _version_matches(game_version, item.minecraft_constraint):
            add("warning", "incompatible_minecraft_version", f"Minecraft 版本可能不兼容：{item.name}", f"该附加声明的 Minecraft 版本范围为 {item.minecraft_constraint}，当前服务器为 {game_version}。", file=f"{folder}/{item.filename}", details={"required": item.minecraft_constraint, "current": game_version})
        missing = sorted(dep for dep in item.dependencies if dep.lower() not in installed_ids and dep.lower() not in BUILTIN_DEPENDENCIES)
        if missing:
            add("warning", "missing_addon_dependencies", f"缺少前置：{item.name}", f"未找到必需前置：{', '.join(missing)}。", file=f"{folder}/{item.filename}", details={"missing": missing})
    return len(metadata)


def _inspect_addon(path: Path) -> AddonMetadata:
    item = AddonMetadata(path.name, path.stem, "unknown")
    try:
        with zipfile.ZipFile(path) as jar:
            names = set(jar.namelist())
            if "fabric.mod.json" in names:
                data = json.loads(jar.read("fabric.mod.json"))
                item.kind = "fabric"; item.name = str(data.get("name") or data.get("id") or path.stem)
                if data.get("id"): item.addon_ids.add(str(data["id"]))
                depends = data.get("depends") or {}
                if isinstance(depends, dict):
                    item.dependencies.update(str(key) for key in depends if key not in {"minecraft", "java", "fabricloader"})
                    item.minecraft_constraint = depends.get("minecraft")
            elif "META-INF/neoforge.mods.toml" in names or "META-INF/mods.toml" in names:
                entry = "META-INF/neoforge.mods.toml" if "META-INF/neoforge.mods.toml" in names else "META-INF/mods.toml"
                data = tomllib.loads(jar.read(entry).decode("utf-8", "replace"))
                item.kind = "neoforge" if "neoforge" in entry else "forge"
                mods = data.get("mods") or []
                if mods:
                    item.name = str(mods[0].get("displayName") or mods[0].get("modId") or path.stem)
                    item.addon_ids.update(str(mod.get("modId")) for mod in mods if mod.get("modId"))
                for dependencies in (data.get("dependencies") or {}).values():
                    for dependency in dependencies if isinstance(dependencies, list) else []:
                        dep_id = str(dependency.get("modId") or "")
                        if not dep_id: continue
                        if dep_id == "minecraft": item.minecraft_constraint = dependency.get("versionRange")
                        elif dependency.get("mandatory", True): item.dependencies.add(dep_id)
            elif "paper-plugin.yml" in names or "plugin.yml" in names:
                entry = "paper-plugin.yml" if "paper-plugin.yml" in names else "plugin.yml"
                data = yaml.safe_load(jar.read(entry)) or {}
                item.kind = "plugin"; item.name = str(data.get("name") or path.stem)
                item.addon_ids.add(str(data.get("name") or path.stem))
                depends = data.get("depend") or []
                if isinstance(depends, str): depends = [depends]
                item.dependencies.update(str(value) for value in depends)
            else:
                item.parse_error = "JAR 中没有找到 Fabric、Forge/NeoForge 或 Paper/Bukkit 的元数据文件。"
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError) as error:
        item.parse_error = f"JAR 文件损坏或元数据格式无效：{error}"
    return item


def _minecraft_version(root: Path) -> str:
    try:
        with (root / ".hslmeta").open(encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        value = str(data.get("mc_version") or data.get("minecraft_version") or data.get("version") or "")
        match = re.search(r"(?<!\d)(1\.\d+(?:\.\d+)?)(?!\d)", value)
        return match.group(1) if match else ""
    except (OSError, yaml.YAMLError):
        return ""


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"\d+(?:\.\d+)+", value)
    return tuple(int(part) for part in match.group().split(".")) if match else ()


def _version_matches(current: str, constraint: Any) -> bool:
    if isinstance(constraint, list): return any(_version_matches(current, value) for value in constraint)
    if not isinstance(constraint, str) or not constraint.strip(): return True
    value = constraint.strip()
    if value in {"*", "x", "X"}: return True
    current_tuple = _version_tuple(current)
    range_match = re.fullmatch(r"([\[(])\s*([^,]*)\s*,\s*([^\])]*)\s*([\])])", value)
    if range_match and current_tuple:
        lower, upper = _version_tuple(range_match.group(2)), _version_tuple(range_match.group(3))
        return (not lower or current_tuple >= lower if range_match.group(1) == "[" else not lower or current_tuple > lower) and (not upper or current_tuple <= upper if range_match.group(4) == "]" else not upper or current_tuple < upper)
    alternatives = re.split(r"\s*\|\|\s*", value)
    for alternative in alternatives:
        checks = re.findall(r"(>=|<=|>|<|=|~|\^)?\s*(\d+(?:\.\d+)+)", alternative)
        if not checks: continue
        valid = True
        for operator, required in checks:
            required_tuple = _version_tuple(required)
            if operator == ">=": valid &= current_tuple >= required_tuple
            elif operator == "<=": valid &= current_tuple <= required_tuple
            elif operator == ">": valid &= current_tuple > required_tuple
            elif operator == "<": valid &= current_tuple < required_tuple
            elif operator == "~": valid &= current_tuple[:2] == required_tuple[:2] and current_tuple >= required_tuple
            elif operator == "^": valid &= current_tuple[:1] == required_tuple[:1] and current_tuple >= required_tuple
            else: valid &= current_tuple == required_tuple
        if valid: return True
    return not bool(re.search(r"\d+(?:\.\d+)+", value))


def _kind_label(kind: str) -> str:
    return {"fabric": "Fabric 模组", "forge": "Forge 模组", "neoforge": "NeoForge 模组", "plugin": "Paper/Bukkit 插件"}.get(kind, "未知附加")
