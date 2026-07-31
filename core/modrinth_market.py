"""Modrinth-backed add-on marketplace and local add-on management."""

import base64
import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx
import yaml

from .workspace import Server, ServerType

API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "HikariRevivalProject/HikariServerLauncher/2.0.0"}
ALLOWED_TYPES = {ServerType.FORGE: ("mod", "forge", "mods"), ServerType.FABRIC: ("mod", "fabric", "mods"), ServerType.PAPER: ("plugin", "paper", "plugins")}


def server_market_info(server: Server) -> dict[str, str]:
    if server.server_type not in ALLOWED_TYPES:
        raise ValueError("该服务器类型不支持 Modrinth 市场，仅支持 Forge、Fabric 和 Paper")
    project_type, loader, folder = ALLOWED_TYPES[server.server_type]
    meta = _read_yaml(os.path.join(server.path, ".hslmeta"))
    game_version = str(meta.get("mc_version") or meta.get("minecraft_version") or meta.get("version") or "")
    if game_version.startswith(("http://", "https://")):
        match = re.search(r"(?<!\d)(1\.\d+(?:\.\d+)?)(?!\d)", game_version)
        game_version = match.group(1) if match else ""
    return {"project_type": project_type, "loader": loader, "folder": folder, "game_version": game_version}


def search_projects(server: Server, query: str = "", category: str = "", index: str = "relevance", offset: int = 0, limit: int = 20) -> dict[str, Any]:
    info = server_market_info(server)
    type_facet = "all_project_types:plugin" if info["project_type"] == "plugin" else "project_type:mod"
    facets = [[type_facet], [f"categories:{info['loader']}"], ["server_side:required", "server_side:optional", "server_side:unknown"]]
    if info["game_version"]:
        facets.append([f"versions:{info['game_version']}"])
    if category:
        facets.append([f"categories:{category}"])
    data = _get("/search", params={"query": query, "facets": json.dumps(facets), "index": index, "offset": max(0, offset), "limit": min(max(limit, 1), 100)})
    data["hits"] = [item for item in data.get("hits", []) if item.get("server_side") != "unsupported"]
    data["server"] = info
    return data


def categories_for(server: Server) -> list[dict[str, Any]]:
    info = server_market_info(server)
    categories = _get("/tag/category")
    return [item for item in categories if info["project_type"] in item.get("project_type", []) and item.get("name") != info["loader"]]


def project_versions(server: Server, project_id: str) -> list[dict[str, Any]]:
    info = server_market_info(server)
    params = {"loaders": json.dumps([info["loader"]]), "include_changelog": "false"}
    if info["game_version"]:
        params["game_versions"] = json.dumps([info["game_version"]])
    versions = _get(f"/project/{project_id}/version", params=params)
    return [_normalize_version(item) for item in versions]


def version_details(server: Server, version_id: str) -> dict[str, Any]:
    version = _normalize_version(_get(f"/version/{version_id}"))
    dependencies = _dependency_tree(server, version, {version.get("project_id")})
    version["required_dependencies"] = dependencies
    return version


def install_version(task, server: Server, version_id: str, install_dependencies: bool = True) -> dict[str, Any]:
    root = version_details(server, version_id)
    queue = [(root, None)]
    if install_dependencies:
        queue = [(item["version"], item) for item in root.get("required_dependencies", [])] + queue
    installed = []
    total = len(queue)
    for index, (version, project_hint) in enumerate(queue, start=1):
        project_id = version["project_id"]
        project = project_hint or _get(f"/project/{project_id}")
        step_id = f"addon-{project_id}"
        task.set_step(step_id, f"安装 {project.get('title', version['name'])}")
        file = next((item for item in version.get("files", []) if item.get("primary")), None) or next(iter(version.get("files", [])), None)
        if not file:
            raise RuntimeError(f"版本 {version['name']} 没有可下载文件")
        folder = server_market_info(server)["folder"]
        destination_dir = os.path.join(server.path, folder)
        os.makedirs(destination_dir, exist_ok=True)
        filename = _safe_filename(file["filename"])
        destination = os.path.join(destination_dir, filename)
        _download(task, file["url"], destination, (index - 1) / total * 100, index / total * 100)
        _record_install(server, folder, filename, project, version)
        task.complete_step(step_id)
        installed.append({"project_id": project_id, "version_id": version["id"], "filename": filename})
    return {"installed": installed, "server_uuid": server.uuid}


def list_addons(server: Server) -> dict[str, Any]:
    info = server_market_info(server)
    directory = os.path.join(server.path, info["folder"])
    os.makedirs(directory, exist_ok=True)
    registry = _read_registry(server)
    addons = []
    for filename in sorted(os.listdir(directory), key=str.lower):
        path = os.path.join(directory, filename)
        if not os.path.isfile(path) or not (filename.lower().endswith(".jar") or filename.lower().endswith(".jar.disabled")):
            continue
        record = registry.get(filename.removesuffix(".disabled"), {})
        embedded = _inspect_jar(path)
        addons.append({"filename": filename, "enabled": not filename.endswith(".disabled"), "size": os.path.getsize(path), "modified": os.path.getmtime(path), "name": record.get("title") or embedded.get("name") or filename.removesuffix(".disabled").removesuffix(".jar"), "version": record.get("version_number") or embedded.get("version"), "project_id": record.get("project_id"), "version_id": record.get("version_id"), "icon_url": record.get("icon_url"), "embedded_icon": embedded.get("icon"), "description": record.get("description") or embedded.get("description", "")})
    return {"addons": addons, "folder": info["folder"], "server": info}


def update_addon(server: Server, filename: str, enabled: bool | None = None, new_name: str | None = None) -> dict[str, Any]:
    info = server_market_info(server)
    directory = os.path.join(server.path, info["folder"])
    current = _safe_addon_path(directory, filename)
    if not os.path.isfile(current):
        raise FileNotFoundError(filename)
    target_name = filename
    if enabled is not None:
        target_name = target_name.removesuffix(".disabled") if enabled else (target_name if target_name.endswith(".disabled") else target_name + ".disabled")
    if new_name:
        suffix = ".jar.disabled" if target_name.endswith(".disabled") else ".jar"
        target_name = _safe_filename(Path(new_name).stem + suffix)
    target = _safe_addon_path(directory, target_name)
    if os.path.normcase(current) != os.path.normcase(target):
        os.replace(current, target)
        registry = _read_registry(server)
        source_key = filename.removesuffix(".disabled")
        target_key = target_name.removesuffix(".disabled")
        if source_key in registry:
            registry[target_key] = registry.pop(source_key)
            with open(os.path.join(server.path, ".hsl-addons.json"), "w", encoding="utf-8") as file:
                json.dump(registry, file, ensure_ascii=False, indent=2)
    return {"filename": target_name, "enabled": not target_name.endswith(".disabled")}


def delete_addon(server: Server, filename: str) -> None:
    directory = os.path.join(server.path, server_market_info(server)["folder"])
    path = _safe_addon_path(directory, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(filename)
    os.remove(path)
    registry = _read_registry(server)
    if registry.pop(filename.removesuffix(".disabled"), None) is not None:
        with open(os.path.join(server.path, ".hsl-addons.json"), "w", encoding="utf-8") as file:
            json.dump(registry, file, ensure_ascii=False, indent=2)


def _compatible_dependency_version(server: Server, dependency: dict[str, Any]) -> dict[str, Any]:
    if dependency.get("version_id"):
        version = _get(f"/version/{dependency['version_id']}")
        if _version_compatible(server, version):
            return version
    project_id = dependency.get("project_id")
    if not project_id:
        raise ValueError("依赖缺少项目标识")
    versions = project_versions(server, project_id)
    if not versions:
        raise ValueError("没有兼容的依赖版本")
    return versions[0]


def _dependency_tree(server: Server, version: dict[str, Any], visited: set[str | None]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for dependency in version.get("dependencies") or []:
        if dependency.get("dependency_type") != "required" or not (dependency.get("project_id") or dependency.get("version_id")):
            continue
        try:
            dep_version = _compatible_dependency_version(server, dependency)
            project_id = dep_version.get("project_id")
            if not project_id or project_id in visited:
                continue
            visited.add(project_id)
            project = _get(f"/project/{project_id}")
            if project.get("server_side") == "unsupported":
                continue
            resolved.extend(_dependency_tree(server, dep_version, visited))
            resolved.append({"project_id": project["id"], "title": project["title"], "description": project.get("description", ""), "icon_url": project.get("icon_url"), "categories": project.get("categories", []), "version": _normalize_version(dep_version)})
        except (httpx.HTTPError, KeyError, ValueError):
            continue
    return resolved


def _version_compatible(server: Server, version: dict[str, Any]) -> bool:
    info = server_market_info(server)
    return info["loader"] in version.get("loaders", []) and (not info["game_version"] or info["game_version"] in version.get("game_versions", []))


def _normalize_version(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: item.get(key) for key in ("id", "project_id", "name", "version_number", "version_type", "date_published", "downloads", "game_versions", "loaders", "files", "dependencies")}
    for key in ("game_versions", "loaders", "files", "dependencies"):
        normalized[key] = normalized[key] or []
    return normalized


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(30.0, connect=15.0), follow_redirects=True) as client:
        response = client.get(API + path, params=params)
        response.raise_for_status()
        return response.json()


def _download(task, url: str, destination: str, start: float, end: float) -> None:
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(300.0, connect=30.0), follow_redirects=True) as client, client.stream("GET", url) as response:
        response.raise_for_status(); total = int(response.headers.get("content-length", 0)); downloaded = 0; started = time.monotonic()
        with open(destination, "wb") as output:
            for chunk in response.iter_bytes(65536):
                output.write(chunk); downloaded += len(chunk)
                progress = start + ((downloaded / total) * (end - start) if total else 0)
                elapsed = max(time.monotonic() - started, 0.001); speed = downloaded / elapsed
                task.set_metrics(downloaded_bytes=downloaded, total_bytes=total or None, speed_bps=round(speed), eta_seconds=round((total - downloaded) / speed) if total and speed else None)
                task.set_progress(progress, f"正在下载 {os.path.basename(destination)}")


def _record_install(server: Server, folder: str, filename: str, project: dict[str, Any], version: dict[str, Any]) -> None:
    registry = _read_registry(server)
    registry[filename] = {"project_id": project.get("id") or project.get("project_id"), "version_id": version.get("id"), "title": project.get("title") or project.get("name"), "description": project.get("description", ""), "icon_url": project.get("icon_url"), "version_number": version.get("version_number"), "folder": folder}
    with open(os.path.join(server.path, ".hsl-addons.json"), "w", encoding="utf-8") as file:
        json.dump(registry, file, ensure_ascii=False, indent=2)


def _read_registry(server: Server) -> dict[str, Any]:
    try:
        with open(os.path.join(server.path, ".hsl-addons.json"), encoding="utf-8") as file: return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError): return {}


def _inspect_jar(path: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(path) as jar:
            names = set(jar.namelist()); icon_path = None
            if "fabric.mod.json" in names:
                data = json.loads(jar.read("fabric.mod.json")); result.update(name=data.get("name"), version=data.get("version"), description=data.get("description")); icon = data.get("icon"); icon_path = icon if isinstance(icon, str) else next(iter(icon.values()), None) if isinstance(icon, dict) else None
            elif "META-INF/mods.toml" in names:
                text = jar.read("META-INF/mods.toml").decode("utf-8", "replace"); result["name"] = _toml_value(text, "displayName"); result["version"] = _toml_value(text, "version"); result["description"] = _toml_value(text, "description"); icon_path = _toml_value(text, "logoFile")
            elif "plugin.yml" in names or "paper-plugin.yml" in names:
                entry = "paper-plugin.yml" if "paper-plugin.yml" in names else "plugin.yml"; data = yaml.safe_load(jar.read(entry)) or {}; result.update(name=data.get("name"), version=data.get("version"), description=data.get("description"))
            if icon_path and icon_path in names:
                raw = jar.read(icon_path)
                if len(raw) <= 512_000:
                    mime = "image/png" if icon_path.lower().endswith(".png") else "image/jpeg"
                    result["icon"] = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, yaml.YAMLError): pass
    return result


def _toml_value(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*[\"']([^\"']+)", text)
    return match.group(1) if match else None


def _read_yaml(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as file: return yaml.safe_load(file) or {}
    except (FileNotFoundError, yaml.YAMLError): return {}


def _safe_filename(value: str) -> str:
    name = os.path.basename(value).replace("\x00", "")
    if not name or name in {".", ".."}: raise ValueError("无效文件名")
    return name


def _safe_addon_path(directory: str, filename: str) -> str:
    path = os.path.abspath(os.path.join(directory, _safe_filename(filename)))
    if os.path.commonpath([os.path.abspath(directory), path]) != os.path.abspath(directory): raise ValueError("无效附加路径")
    return path
