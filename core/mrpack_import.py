"""Secure server-side importer for the Modrinth .mrpack format."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import time
import tomllib
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx
from remotezip import RemoteZip

from .config import ConfigKey
from .server_creator import create_server_flow
from .workspace import Server, ServerType, WorkspaceManager

API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "HikariRevivalProject/HikariServerLauncher/2.0.0"}
INCOMPATIBLE_RULES_URL = "https://hsl-config.oss-cn-beijing.aliyuncs.com/incompatible.txt"
SESSION_ROOT = Path(tempfile.gettempdir()) / "hsl2-mrpack"
MAX_PACK_SIZE = 512 * 1024 * 1024
ALLOWED_DOWNLOAD_HOSTS = {"cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com"}
def inspect_mrpack(file_storage) -> dict[str, Any]:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    _cleanup_sessions()
    session_id = uuid.uuid4().hex
    session_dir = SESSION_ROOT / session_id
    session_dir.mkdir()
    pack_path = session_dir / "pack.mrpack"
    file_storage.save(pack_path)
    if pack_path.stat().st_size > MAX_PACK_SIZE:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise ValueError("mrpack 文件超过 512 MB 限制")
    try:
        index = _read_index(pack_path)
        rules, rules_source = _load_rules()
        files = _enrich_files(index, rules)
        manifest = {
            "session_id": session_id,
            "pack": {
                "name": index["name"],
                "summary": index.get("summary", ""),
                "version_id": index["versionId"],
                "minecraft": index["dependencies"]["minecraft"],
                "loader": _loader_info(index["dependencies"]),
            },
            "files": files,
            "rules_source": rules_source,
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return manifest
    except Exception:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise


def import_mrpack_flow(task, session_id: str, selected_paths: list[str], metadata: dict[str, Any], workspace: WorkspaceManager) -> dict[str, Any]:
    session_dir = _session_dir(session_id)
    manifest = json.loads((session_dir / "manifest.json").read_text(encoding="utf-8"))
    pack_path = session_dir / "pack.mrpack"
    allowed = {item["path"]: item for item in manifest["files"] if item["supported"]}
    selected = [allowed[path] for path in dict.fromkeys(selected_paths) if path in allowed]
    loader = manifest["pack"]["loader"]
    server_type = ServerType.from_str(loader["server_type"])
    server = workspace.create_server(
        name=str(metadata.get("name") or manifest["pack"]["name"]).strip(),
        server_type=server_type,
        max_memory=int(metadata.get("max_memory", 4096)),
        extra_args=str(metadata.get("extra_args", "")),
        java_version=str(metadata.get("java_version", "21")),
    )
    try:
        create_server_flow(
            task, server.uuid, workspace, server_type,
            java_version=server.java_version,
            version=loader["install_version"],
            mc_version=manifest["pack"]["minecraft"],
        )
        _download_files(task, server, selected)
        _apply_overrides(task, pack_path, Path(server.path))
        _save_pack_metadata(server, manifest, selected)
        task.set_progress(100, "模组包服务器已准备完成")
        return {"server_uuid": server.uuid, "installed_files": len(selected), "pack": manifest["pack"]}
    except Exception:
        # A failed import must not leave a broken server in the workspace.
        workspace._servers.servers = [item for item in workspace._servers.servers if item.uuid != server.uuid]
        shutil.rmtree(server.path, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


def _read_index(pack_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(pack_path) as pack:
            if "modrinth.index.json" not in pack.namelist():
                raise ValueError("压缩包根目录缺少 modrinth.index.json")
            index = json.loads(pack.read("modrinth.index.json").decode("utf-8"))
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"无效的 mrpack 文件：{error}") from error
    if index.get("formatVersion") != 1 or index.get("game") != "minecraft":
        raise ValueError("仅支持 formatVersion=1 的 Minecraft 模组包")
    for key in ("versionId", "name", "files", "dependencies"):
        if key not in index:
            raise ValueError(f"modrinth.index.json 缺少字段：{key}")
    if not index["dependencies"].get("minecraft"):
        raise ValueError("模组包没有声明 Minecraft 版本")
    _loader_info(index["dependencies"])
    for item in index["files"]:
        _safe_relative(item.get("path", ""))
        hashes = item.get("hashes") or {}
        if not hashes.get("sha1") or not hashes.get("sha512"):
            raise ValueError(f"{item.get('path', '未知文件')} 缺少 SHA-1 或 SHA-512")
        if not item.get("downloads"):
            raise ValueError(f"{item.get('path', '未知文件')} 没有下载地址")
        if not any(_allowed_download(url) for url in item["downloads"]):
            raise ValueError(f"{item.get('path', '未知文件')} 没有受信任的 HTTPS 下载地址")
    return index


def _loader_info(dependencies: dict[str, str]) -> dict[str, str]:
    minecraft = str(dependencies.get("minecraft", ""))
    loaders = [("fabric-loader", "Fabric"), ("forge", "Forge"), ("neoforge", "NeoForge")]
    found = [(key, server_type, str(dependencies[key])) for key, server_type in loaders if dependencies.get(key)]
    if len(found) != 1:
        raise ValueError("服务器导入要求模组包明确声明一个 Fabric、Forge 或 NeoForge 加载器")
    key, server_type, version = found[0]
    install_version = f"{minecraft}|{version}"
    return {"id": key, "name": key.replace("-loader", ""), "version": version, "server_type": server_type, "install_version": install_version}


def _enrich_files(index: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hashes = [item["hashes"]["sha1"] for item in index["files"]]
    versions: dict[str, Any] = {}
    projects: dict[str, Any] = {}
    try:
        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            response = client.post(API + "/version_files", json={"hashes": hashes, "algorithm": "sha1"})
            response.raise_for_status(); versions = response.json()
            project_ids = sorted({item["project_id"] for item in versions.values()})
            if project_ids:
                response = client.get(API + "/projects", params={"ids": json.dumps(project_ids)})
                response.raise_for_status(); projects = {item["id"]: item for item in response.json()}
    except httpx.HTTPError:
        pass
    identifiers_by_hash = _collect_remote_mod_ids(index["files"])
    pack_ids = {
        str(
            projects.get(version.get("project_id"), {}).get("slug")
            or version.get("project_id")
            or ""
        ).lower()
        for version in versions.values()
    }
    for identifiers in identifiers_by_hash.values():
        pack_ids.update(identifiers)
    game = index["dependencies"]["minecraft"]
    result = []
    for number, item in enumerate(index["files"]):
        sha1 = item["hashes"]["sha1"]
        version = versions.get(sha1, {})
        project = projects.get(version.get("project_id"), {})
        mod_id = str(project.get("slug") or version.get("project_id") or Path(item["path"]).stem).lower()
        identifiers = {mod_id, *identifiers_by_hash.get(sha1, set())}
        env = item.get("env") or {}
        server_env = env.get("server", "required")
        reasons = []
        if server_env == "unsupported": reasons.append("模组包明确标记为不支持专用服务器")
        reasons.extend(
            rule["desc"]
            for rule in rules
            if any(_rule_matches(rule, identifier, game, pack_ids) for identifier in identifiers)
        )
        supported = not reasons
        result.append({
            "key": f"{number}:{sha1}", "path": item["path"], "size": item.get("fileSize", 0),
            "hashes": item["hashes"], "downloads": item["downloads"], "env": server_env,
            "project_id": version.get("project_id"), "version_id": version.get("id"), "id": mod_id,
            "mod_ids": sorted(identifiers - {mod_id}),
            "title": project.get("title") or Path(item["path"]).stem,
            "description": "；".join(reasons) if reasons else project.get("description") or "模组包中的外部文件",
            "icon_url": project.get("icon_url"), "categories": project.get("categories", []),
            "version": version.get("version_number", ""), "supported": supported,
            "selected": supported and server_env in {"required", "optional"}, "reason": "；".join(reasons),
        })
    return result


def _collect_remote_mod_ids(files: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Read loader mod IDs through HTTP ranges without downloading whole JARs."""
    candidates = {}
    for item in files:
        if not str(item.get("path", "")).lower().endswith(".jar"):
            continue
        url = next((url for url in item.get("downloads", []) if _allowed_download(url)), None)
        if url:
            candidates[item["hashes"]["sha1"]] = url
    result: dict[str, set[str]] = {}
    with ThreadPoolExecutor(max_workers=min(8, max(len(candidates), 1))) as executor:
        pending = {executor.submit(_remote_mod_ids, url): sha1 for sha1, url in candidates.items()}
        for future in as_completed(pending):
            try:
                result[pending[future]] = future.result()
            except Exception:
                result[pending[future]] = set()
    return result


def _remote_mod_ids(url: str) -> set[str]:
    with RemoteZip(url, headers=HEADERS, timeout=15) as jar:
        return _jar_mod_ids(jar)


def _jar_mod_ids(jar: zipfile.ZipFile) -> set[str]:
    names = set(jar.namelist())
    result: set[str] = set()
    if "fabric.mod.json" in names:
        data = json.loads(jar.read("fabric.mod.json"))
        if data.get("id"):
            result.add(str(data["id"]).lower())
    if "quilt.mod.json" in names:
        data = json.loads(jar.read("quilt.mod.json"))
        quilt_loader = data.get("quilt_loader") or {}
        if quilt_loader.get("id"):
            result.add(str(quilt_loader["id"]).lower())
    for metadata_path in ("META-INF/mods.toml", "META-INF/neoforge.mods.toml"):
        if metadata_path not in names:
            continue
        data = tomllib.loads(jar.read(metadata_path).decode("utf-8", "replace"))
        for mod in data.get("mods") or []:
            if mod.get("modId"):
                result.add(str(mod["modId"]).lower())
    if "mcmod.info" in names:
        data = json.loads(jar.read("mcmod.info"))
        for mod in data if isinstance(data, list) else [data]:
            if mod.get("modid"):
                result.add(str(mod["modid"]).lower())
    return result


def _load_rules() -> tuple[list[dict[str, Any]], str]:
    url = ConfigKey.MODPACK_INCOMPATIBLE_LIST_URL.get() or INCOMPATIBLE_RULES_URL
    try:
        response = httpx.get(str(url), headers=HEADERS, timeout=15, follow_redirects=True)
        response.raise_for_status()
        rules = _parse_rules(response.content.decode("utf-8-sig"))
        if not rules:
            return [], "未启用（云端规则为空或格式无效）"
        return rules, str(url)
    except (httpx.HTTPError, UnicodeDecodeError):
        return [], "未启用（无法获取云端规则）"


def _parse_rules(text: str) -> list[dict[str, Any]]:
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        desc_match = re.search(r"(?:^|\s)desc=(.*)$", line)
        desc = desc_match.group(1).strip() if desc_match else "该模组被服务器不兼容列表排除"
        prefix = line[:desc_match.start()].strip() if desc_match else line
        id_match = re.search(r"(?:^|\s)id=([^\s]+)", prefix)
        if not id_match: continue
        conditions = [(op, value) for op, value in re.findall(r"(?:^|\s)game(>=|<=|>|<|=)([^\s]+)", prefix)]
        with_match = re.search(r"(?:^|\s)with=([^\s]+)", prefix)
        rules.append({"id": id_match.group(1).lower(), "games": conditions, "with": with_match.group(1).lower() if with_match else None, "desc": desc})
    return rules


def _rule_matches(rule: dict[str, Any], mod_id: str, game: str, pack_ids: set[str]) -> bool:
    if not fnmatchcase(mod_id, rule["id"]) or (
        rule["with"] and not any(fnmatchcase(pack_id, rule["with"]) for pack_id in pack_ids)
    ):
        return False
    return all(_compare_version(game, operator, value) for operator, value in rule["games"])


def _compare_version(current: str, operator: str, expected: str) -> bool:
    if expected == "*": return True
    def parts(value): return tuple(int(item) for item in re.findall(r"\d+", value))
    left, right = parts(current), parts(expected)
    return {"=": left == right, ">=": left >= right, "<=": left <= right, ">": left > right, "<": left < right}[operator]


def _download_files(task, server: Server, files: list[dict[str, Any]]) -> None:
    total = max(len(files), 1)
    with httpx.Client(headers=HEADERS, timeout=300, follow_redirects=True) as client:
        for index, item in enumerate(files, 1):
            relative = _safe_relative(item["path"]); destination = Path(server.path) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            task.set_step(f"pack-{index}", f"下载 {item['title']}")
            last_error = None
            for url in item["downloads"]:
                if not _allowed_download(url):
                    continue
                try:
                    with client.stream("GET", url) as response:
                        response.raise_for_status(); sha1 = hashlib.sha1(); sha512 = hashlib.sha512()
                        if not _allowed_download(str(response.url)):
                            raise ValueError("下载重定向到了不受信任的域名")
                        with destination.open("wb") as output:
                            for chunk in response.iter_bytes(65536): output.write(chunk); sha1.update(chunk); sha512.update(chunk)
                    if sha1.hexdigest() != item["hashes"]["sha1"] or sha512.hexdigest() != item["hashes"]["sha512"]:
                        raise ValueError("下载文件哈希不匹配")
                    last_error = None; break
                except (httpx.HTTPError, OSError, ValueError) as error:
                    last_error = error
                    destination.unlink(missing_ok=True)
            if last_error: raise RuntimeError(f"无法下载 {item['title']}：{last_error}")
            task.complete_step(f"pack-{index}"); task.set_progress(65 + index / total * 25, f"已安装 {index}/{len(files)} 个文件")


def _apply_overrides(task, pack_path: Path, destination: Path) -> None:
    task.set_step("pack-overrides", "应用服务器配置覆盖")
    with zipfile.ZipFile(pack_path) as pack:
        override_size = sum(entry.file_size for entry in pack.infolist() if entry.filename.startswith(("overrides/", "server-overrides/")))
        if override_size > 1024 * 1024 * 1024:
            raise ValueError("覆盖文件解压后超过 1 GB 限制")
        for prefix in ("overrides/", "server-overrides/"):
            for entry in pack.infolist():
                if entry.is_dir() or not entry.filename.startswith(prefix): continue
                relative = _safe_relative(entry.filename[len(prefix):])
                target = destination / relative; target.parent.mkdir(parents=True, exist_ok=True)
                with pack.open(entry) as source, target.open("wb") as output: shutil.copyfileobj(source, output)
    task.complete_step("pack-overrides")


def _save_pack_metadata(server: Server, manifest: dict[str, Any], selected: list[dict[str, Any]]) -> None:
    data = {"pack": manifest["pack"], "installed": [{key: item.get(key) for key in ("path", "project_id", "version_id", "id")} for item in selected]}
    Path(server.path, ".hsl-mrpack.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    registry = {}
    for item in selected:
        path = PurePosixPath(item["path"])
        if path.parent.as_posix() != "mods" or not item.get("project_id"):
            continue
        registry[path.name] = {
            "project_id": item.get("project_id"), "version_id": item.get("version_id"),
            "title": item.get("title"), "description": item.get("description", ""),
            "icon_url": item.get("icon_url"), "version_number": item.get("version"), "folder": "mods",
        }
    if registry:
        Path(server.path, ".hsl-addons.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_relative(value: str) -> Path:
    path = PurePosixPath(str(value).replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", str(value)):
        raise ValueError(f"不安全的模组包路径：{value}")
    return Path(*path.parts)


def _allowed_download(url: str) -> bool:
    parsed = urlparse(str(url))
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_DOWNLOAD_HOSTS


def _session_dir(session_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", session_id): raise ValueError("无效的导入会话")
    path = SESSION_ROOT / session_id
    if not path.is_dir(): raise FileNotFoundError("导入会话已过期，请重新上传 mrpack")
    return path


def _cleanup_sessions() -> None:
    if not SESSION_ROOT.exists(): return
    cutoff = time.time() - 6 * 3600
    for path in SESSION_ROOT.iterdir():
        if path.is_dir() and path.stat().st_mtime < cutoff: shutil.rmtree(path, ignore_errors=True)
