import contextlib
import json
import logging
import os
import shutil
import sys
import threading
import time
import traceback

import javaproperties
import yaml
from flask import Flask, g, jsonify, render_template_string, request, send_file
from flask import request as ws_request
from flask_sock import Sock
from werkzeug.exceptions import RequestEntityTooLarge

from core import (
    SPCONFIGS,
    AuthManager,
    ConfigKey,
    ConfigManager,
    DockerAdapter,
    EnvironmentManager,
    JavaAdapter,
    Logger,
    ServerType,
    SourceManager,
    TaskManager,
    TaskStatus,
    WebFileDownloadAdapter,
    WorkspaceManager,
    create_server_flow,
)
from core.backup import BACKUP_FILENAME_RE, BackupManager
from core.monitor import SystemMonitor
from core.server_file_manager import (
    create_file,
    create_folder,
    delete_file,
    delete_folder,
    download_file,
    list_directory,
    read_file,
    upload_stream,
    write_file,
)
from core.server_process import ServerProcessManager, export_launch_script
from core.server_diagnostics import diagnose_server
from core.modrinth_market import (
    categories_for,
    delete_addon,
    install_version,
    list_addons,
    project_versions,
    search_projects,
    server_market_info,
    update_addon,
    version_details,
)
from core.mrpack_import import MAX_PACK_FILES, import_mrpack_flow, inspect_mrpack
from core.tui import TUI
from core.version_resolver import (
    get_april_versions,
    get_fabric_versions,
    get_forge_versions,
    get_java_versions,
    get_neoforge_versions,
    get_paper_builds,
    get_paper_versions,
    get_recommended_java_version,
    get_vanilla_versions,
)
from core.websocket_auth import authenticate_websocket


def _get_app_path(*parts: str) -> str:
    """Get path relative to app root, handling PyInstaller bundling."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, *parts)  # type: ignore
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


# Silence Flask/werkzeug request logs
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("flask").setLevel(logging.WARNING)

VERSION = "2.0.0"

logger = Logger()
logger.banner()
logger.info(f"版本: {VERSION}")


# Global exception hook — log uncaught exceptions to file
def _global_excepthook(exc_type, exc_value, exc_tb):
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical(f"未捕获的异常:\n{tb_str}")
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _global_excepthook

logger.info("正在启动 Hikari Server Launcher...")
logger.info(f"配置文件路径: {ConfigManager()._config_path}")
logger.info(f"鉴权启用: {ConfigKey.AUTH_ENABLED.get()}")

auth = AuthManager()
logger.info("AuthManager 已初始化。")

workspace = WorkspaceManager()
logger.info("WorkspaceManager 已初始化。")
logger.info(f"工作空间路径: {workspace.workspace_path}")
logger.info(f"有效服务器: {[s.name for s in workspace.get_valid_servers()]}")

tm = TaskManager()
logger.info("TaskManager 已初始化。")

spm = ServerProcessManager()
logger.info("ServerProcessManager 已初始化。")

src = SourceManager()
logger.info("SourceManager 已初始化。")

tm.register_adapter(WebFileDownloadAdapter())
logger.info("WebFileDownloadAdapter 已注册。")

tm.register_adapter(DockerAdapter())
logger.info("DockerAdapter 已注册。")

tm.register_adapter(JavaAdapter())
logger.info("JavaAdapter 已注册。")


def check_docker_installed():
    success, result, _ = tm.create_and_run_sync("docker", "check_installed")
    if success is None:
        return
    if not success:
        logger.error("检查 Docker 安装失败。")
        logger.error(result.error if result.error else "未知错误")
        exit(1)
    data = result.data
    if not data.get("installed", False):
        logger.warning("Docker 未安装。部分功能将无法使用。")
        if result.error:
            logger.warning(result.error)


check_docker_installed()

monitor = SystemMonitor()
# Start disk usage history collector (snapshot every hour)
monitor.start_collector(lambda: [(s.path, s.name) for s in workspace.get_valid_servers()])

env = EnvironmentManager()
logger.info("EnvironmentManager 已初始化。")

logger.info("正在获取环境信息...")
logger.info("这可能需要一点时间。")
env_info = env.check(check_network=True)

logger.info("-" * 60)
logger.info("系统信息".center(60))
logger.info("-" * 60)
logger.info(f"系统类型:    {env_info.system}")
logger.info(f"系统版本:    {env_info.system_version}")
logger.info(f"架构:        {env_info.arch}")
logger.info(f"处理器:      {env_info.processor}")
logger.info(f"本地 IP:     {env_info.ip_address}")
logger.info(f"公网 IP:     {env_info.public_ip}")

if env_info.network_info:
    logger.info("-" * 60)
    logger.info("网络信息".center(60))
    logger.info("-" * 60)
    logger.info(f"NAT 类型:    {env_info.network_info.nat_type}")
    logger.info(f"外部 IP:     {env_info.network_info.external_ip}")
    logger.info(f"映射地址:    {env_info.network_info.mapped_address}")
    logger.info(f"映射端口:    {env_info.network_info.mapped_port}")
    logger.info(f"STUN 服务器: {env_info.network_info.stun_server}")
    if env_info.network_info.stun_observations:
        logger.info(f"STUN 样本数:  {len(env_info.network_info.stun_observations)}")
        for sample in env_info.network_info.stun_observations:
            logger.info(
                f"  {sample['server']}: {sample['external_ip']}:"
                f"{sample['external_port']} ({sample['nat_type']})"
            )
    if env_info.network_info.route_hops:
        logger.info(f"上游路由:    {' -> '.join(env_info.network_info.route_hops)}")
    if env_info.network_info.router_wan_ip:
        logger.info(f"路由器 WAN:  {env_info.network_info.router_wan_ip}")

    if env_info.network_info.cgnat:
        cgnat = env_info.network_info.cgnat
        logger.info("-" * 60)
        logger.info("CGNAT 检测".center(60))
        logger.info("-" * 60)
        status = {
            "confirmed": "检测到 CGNAT",
            "likely": "疑似 CGNAT",
            "not_detected": "未检测到 CGNAT",
        }.get(cgnat.verdict, "疑似 CGNAT" if cgnat.is_cgnat else "未检测到 CGNAT")
        color_func = logger.error if cgnat.is_cgnat else logger.info
        color_func(f"状态:        {status}")
        logger.info(f"置信度:      {cgnat.confidence:.2%}")
        if cgnat.reasons:
            logger.info("判定原因:")
            for i, reason in enumerate(cgnat.reasons, 1):
                logger.info(f"  {i}. {reason}")
        if cgnat.is_cgnat:
            logger.error("警告: 当前网络有可能处于 CGNAT 环境中！")
            logger.error("这可能导致游戏服务器无法被外网访问。")
            logger.error("建议使用内网穿透工具（如 frp、ngrok）。")

logger.info("-" * 60)

name = ConfigKey.APP_NAME.get()
host = ConfigKey.APP_HOST.get()
port = ConfigKey.APP_PORT.get()
flask_debug = ConfigKey.APP_FLASK_DEBUG.get()

tui = TUI()
tui.set_bind(host, port)

app = Flask(name)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify({"error": "上传内容超过 512 MB 限制"}), 413

# ── Request logging hooks ────────────────────────────────────────


@app.before_request
def _tui_before():
    g._start_time = time.time()


@app.after_request
def _tui_after(response):
    if request.path.startswith("/api/"):
        elapsed = (time.time() - g.get("_start_time", time.time())) * 1000
        tui.log_request(request.method, request.path, response.status_code, elapsed)
    # Update TUI state snapshot
    tui.update_state(
        workspace.get_all_servers(),
        tm.list_tasks(),
        dict(spm._running),
    )
    return response


# WebSocket support
try:
    sock = Sock(app)
    logger.info("WebSocket 支持已启用。")
except ImportError:
    sock = None
    logger.warning("flask-sock 未安装，WebSocket 功能不可用。")

# ── Auth endpoints ──────────────────────────────────────────────


@app.route("/api/auth", methods=["POST"])
def authenticate():
    success, token, error = auth.authenticate(request)
    if success:
        return jsonify({"success": True, "token": token, "expires_in": 43200})
    return jsonify({"success": False, "error": error}), 401


@app.route("/api/auth/verify", methods=["GET"])
def verify_token():
    token = _extract_bearer_token()
    if not token:
        return jsonify({"valid": False, "error": "Missing token"}), 400
    valid = auth.validate_token(token)
    return jsonify({"valid": valid})


@app.route("/api/auth/revoke", methods=["GET"])
def revoke_token():
    token = _extract_bearer_token()
    if not token:
        return jsonify({"success": False, "error": "Missing token"}), 400
    revoked = auth.revoke_token(token)
    return jsonify({"success": revoked})


# ── Server endpoints ────────────────────────────────────────────


@app.route("/api/servers", methods=["GET"])
def list_servers():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    servers = workspace.get_all_servers()
    return jsonify({"servers": [s.to_dict() for s in servers]})


@app.route("/api/servers/<server_uuid>", methods=["GET"])
def get_server(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404
    return jsonify({"server": server.to_dict()})


@app.route("/api/servers/<server_uuid>/diagnostics", methods=["POST"])
def run_server_diagnostics(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404
    try:
        return jsonify(diagnose_server(server))
    except Exception as error:
        logger.error(f"服务器检测失败 ({server.name}): {error}")
        logger.debug(traceback.format_exc())
        return jsonify({"error": f"服务器检测失败: {error}"}), 500


def _validate_server_settings(data: dict, require_version: bool = False) -> str | None:
    if "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return "服务器名称不能为空"
        if len(name.strip()) > 80:
            return "服务器名称不能超过 80 个字符"
    if "max_memory" in data:
        value = data.get("max_memory")
        if isinstance(value, bool) or not isinstance(value, int):
            return "最大内存必须是整数 MB"
        if value < 512 or value > 1_048_576:
            return "最大内存必须在 512 MB 到 1 TB 之间"
    if "java_version" in data and str(data.get("java_version")) not in {"8", "11", "17", "21", "25"}:
        return "不支持的 Java 版本"
    if "extra_args" in data:
        args = data.get("extra_args")
        if not isinstance(args, str) or len(args) > 4096:
            return "额外 JVM 参数不能超过 4096 个字符"
    if require_version and not str(data.get("version") or "").strip():
        return "请选择服务端版本"
    return None


@app.route("/api/servers/create", methods=["POST"])
def create_server():
    if not auth.require_auth(request):
        return jsonify({"success": False, "error": auth.get_auth_error(request)}), 401

    data: dict = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    validation_error = _validate_server_settings(data, require_version=True)
    if validation_error:
        return jsonify({"success": False, "error": validation_error}), 400

    server_type_str = data.get("server_type", ServerType.VANILLA.value)
    try:
        server_type = ServerType.from_str(server_type_str)
    except ValueError:
        return jsonify({"success": False, "error": f"Invalid server type: {server_type_str}"}), 400

    try:
        server = workspace.create_server(
            name=data.get("name", f"Server {workspace.get_server_count() + 1}"),
            server_type=server_type,
            max_memory=data.get("max_memory", 1024),
            extra_args=data.get("extra_args", ""),
            java_version=data.get("java_version", "25"),
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    # Create task for async server setup (download jar, java, etc.)
    version = data.get("version", "")
    mc_version = data.get("mc_version", "")
    java_version = data.get("java_version", "25")

    task = tm.create_composite_task(
        execute_fn=lambda t, sp: create_server_flow(
            t,
            server.uuid,
            workspace,
            server_type,
            java_version=java_version,
            version=version,
            mc_version=mc_version,
        )
    )
    task.title = f"Create {server.name}"
    task.set_step("queued", "Waiting to start", "pending")

    # Start the task in a background thread
    tm.run_task_background(task.task_id)

    return jsonify(
        {
            "success": True,
            "server": server.to_dict(),
            "task_id": task.task_id,
        }
    )


@app.route("/api/servers/<server_uuid>", methods=["DELETE"])
def delete_server(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(server.path)

    # Remove from collection
    workspace._servers.servers = [s for s in workspace._servers.servers if s.uuid != server_uuid]

    return jsonify({"success": True})


@app.route("/api/servers/<server_uuid>", methods=["PUT"])
def update_server(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    data: dict = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    validation_error = _validate_server_settings(data)
    if validation_error:
        return jsonify({"success": False, "error": validation_error}), 400

    if "name" in data:
        server.name = data["name"]
    if "max_memory" in data:
        server.max_memory = data["max_memory"]
    if "extra_args" in data:
        server.extra_args = data["extra_args"]
    if "java_version" in data:
        server.java_version = data["java_version"]

    # Persist to .hslmeta
    meta_file = os.path.join(server.path, ".hslmeta")
    with open(meta_file, encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    meta["name"] = server.name
    meta["max_memory"] = server.max_memory
    meta["extra_args"] = server.extra_args
    meta["java_version"] = server.java_version
    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    return jsonify({"success": True, "server": server.to_dict()})


# ── Server process management ───────────────────────────────────


@app.route("/api/servers/<server_uuid>/start", methods=["POST"])
def start_server(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    success, message = spm.start(server)
    if not success:
        return jsonify({"success": False, "error": message}), 400

    return jsonify({"success": True, "message": message, "status": spm.get_status(server_uuid)})


@app.route("/api/servers/<server_uuid>/stop", methods=["POST"])
def stop_server(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    success, message = spm.stop(server_uuid)
    return jsonify({"success": success, "message": message})


@app.route("/api/servers/<server_uuid>/kill", methods=["POST"])
def kill_server(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    success, message = spm.kill(server_uuid)
    return jsonify({"success": success, "message": message})


@app.route("/api/servers/<server_uuid>/command", methods=["POST"])
def send_server_command(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"success": False, "error": "Missing 'command' in body"}), 400

    success, message = spm.send_command(server_uuid, data["command"])
    if not success:
        return jsonify({"success": False, "error": message}), 400

    return jsonify({"success": True, "message": message})


@app.route("/api/servers/<server_uuid>/status", methods=["GET"])
def server_status(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    return jsonify(spm.get_status(server_uuid))


# ── File management ─────────────────────────────────────────────


@app.route("/api/servers/<server_uuid>/files", methods=["GET"])
def list_server_files(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    path = request.args.get("path", "")
    result = list_directory(server.path, path)
    if "error" in result:
        code = 400 if "not found" in result.get("error", "").lower() else 500
        return jsonify({"error": result["error"]}), code

    return jsonify(result)


@app.route("/api/servers/<server_uuid>/files", methods=["POST"])
def create_server_file(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    path = data.get("path", "")
    file_type = data.get("type", "file")
    content = data.get("content", "")

    if not path:
        return jsonify({"error": "Missing 'path'"}), 400

    if file_type == "folder":
        result = create_folder(server.path, path)
    else:
        result = create_file(server.path, path, content)

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify(result)


@app.route("/api/servers/<server_uuid>/files", methods=["PUT"])
def write_server_file(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    path = data.get("path", "")
    content = data.get("content", "")

    if not path:
        return jsonify({"error": "Missing 'path'"}), 400

    result = write_file(server.path, path, content)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify(result)


@app.route("/api/servers/<server_uuid>/files", methods=["DELETE"])
def delete_server_file(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    path = request.args.get("path", "")
    recursive = request.args.get("recursive", "false").lower() == "true"

    if not path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    full_path = os.path.join(server.path, path.replace("/", os.sep))
    if os.path.isdir(full_path):
        result = delete_folder(server.path, path, recursive=recursive)
    else:
        result = delete_file(server.path, path)

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify(result)


@app.route("/api/servers/<server_uuid>/files/read", methods=["GET"])
def read_server_file(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    result = read_file(server.path, path)
    if "error" in result:
        code = 400 if "not found" in result.get("error", "").lower() else 500
        return jsonify({"error": result["error"]}), code

    return jsonify(result)


@app.route("/api/servers/<server_uuid>/files/upload", methods=["POST"])
def upload_server_file(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No filename"}), 400

    path = request.args.get("path", "")

    result = upload_stream(server.path, path, file.stream, file.filename)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify(result)


@app.route("/api/servers/<server_uuid>/files/download", methods=["GET"])
def download_server_file(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    error, file_path, mime_type = download_file(server.path, path)
    if error:
        return jsonify({"error": error}), 400

    return send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=True,
        download_name=os.path.basename(path),
    )


# ── Version listing endpoints ───────────────────────────────────


@app.route("/api/versions/vanilla", methods=["GET"])
def get_vanilla_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    use_mirror = request.args.get("use_mirror", "false").lower() == "true"

    try:
        result = get_vanilla_versions(use_mirror=use_mirror)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/paper", methods=["GET"])
def get_paper_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    mc_version = request.args.get("mc_version", default=None)

    try:
        result = get_paper_versions(mc_version=mc_version)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/paper/builds", methods=["GET"])
def get_paper_builds_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    sub_version = request.args.get("version", default="")

    try:
        result = get_paper_builds(sub_version)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/april", methods=["GET"])
def get_april_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    try:
        result = get_april_versions()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/forge", methods=["GET"])
def get_forge_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    use_mirror = request.args.get("use_mirror", "false").lower() == "true"
    mc_version = request.args.get("mc_version", default=None)

    try:
        result = get_forge_versions(mc_version=mc_version, use_mirror=use_mirror)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/neoforge", methods=["GET"])
def get_neoforge_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    use_mirror = request.args.get("use_mirror", "false").lower() == "true"
    mc_version = request.args.get("mc_version", default=None)

    try:
        result = get_neoforge_versions(mc_version=mc_version, use_mirror=use_mirror)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/fabric", methods=["GET"])
def get_fabric_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    use_mirror = request.args.get("use_mirror", "false").lower() == "true"

    try:
        result = get_fabric_versions(use_mirror=use_mirror)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/versions/recommended-java", methods=["GET"])
def recommended_java_endpoint():

    mc_version = request.args.get("mc_version", "")
    if not mc_version:
        return jsonify({"error": "mc_version is required"}), 400
    recommended = get_recommended_java_version(mc_version)
    return jsonify({"mc_version": mc_version, "recommended_java": int(recommended)})


@app.route("/api/versions/java", methods=["GET"])
def get_java_versions_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    use_mirror = request.args.get("use_mirror", "false").lower() == "true"

    try:
        result = get_java_versions(use_mirror=use_mirror)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Backup endpoints ─────────────────────────────────────────────


@app.route("/api/servers/<server_uuid>/backups", methods=["POST"])
def create_backup(server_uuid: str):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    bm = BackupManager()
    task = tm.create_composite_task(
        execute_fn=lambda t, sp: bm.create_backup_sync(server.path, server_uuid, task=t)
    )
    task.title = f"Back up {server.name}"
    task.set_step("backup", "Archive server files", "pending")
    tm.run_task_background(task.task_id)

    return jsonify({"success": True, "task_id": task.task_id, "server_uuid": server_uuid})


@app.route("/api/servers/<server_uuid>/backups", methods=["GET"])
def list_backups(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    backups = BackupManager().list_backups(server_uuid)
    return jsonify({"backups": backups, "server_uuid": server_uuid})


@app.route("/api/servers/<server_uuid>/backups/<filename>/restore", methods=["POST"])
def restore_backup(server_uuid, filename):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    if not BACKUP_FILENAME_RE.match(filename) or ".." in filename:
        return jsonify({"error": "Invalid backup filename"}), 400

    bm = BackupManager()
    full_path = os.path.join(bm._get_backup_dir(), filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "Backup file not found"}), 404

    if spm.is_running(server_uuid):
        spm.kill(server_uuid)

    task = tm.create_composite_task(
        execute_fn=lambda t, sp: bm.restore_backup_sync(server.path, filename, task=t)
    )
    task.title = f"Restore {server.name}"
    task.set_step("restore", "Restore backup archive", "pending")
    tm.run_task_background(task.task_id)

    return jsonify(
        {
            "success": True,
            "task_id": task.task_id,
            "server_uuid": server_uuid,
            "filename": filename,
        }
    )


@app.route("/api/servers/<server_uuid>/backups/<filename>", methods=["DELETE"])
def delete_backup(server_uuid, filename):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    if not BACKUP_FILENAME_RE.match(filename) or ".." in filename:
        return jsonify({"error": "Invalid backup filename"}), 400

    deleted = BackupManager().delete_backup(filename)
    if not deleted:
        return jsonify({"error": "Backup file not found"}), 404

    return jsonify({"success": True, "filename": filename})


# ── Export launch script ─────────────────────────────────────────


@app.route("/api/servers/<server_uuid>/export", methods=["GET"])
def export_launch_script_endpoint(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    fmt = request.args.get("format", "batch").lower()
    if fmt not in ("batch", "shell"):
        return jsonify({"error": f"Unsupported format: {fmt}. Use 'batch' or 'shell'."}), 400

    try:
        script = export_launch_script(server, fmt=fmt)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {
            "server_uuid": server_uuid,
            "format": fmt,
            "script": script,
        }
    )


# ── spconfigs endpoints ─────────────────────────────────────────


def _get_nested_value(config: dict, keys: list):
    for key in keys:
        if config is None:
            return None
        if isinstance(config, dict):
            config = config.get(key, {})
        else:
            return None

    return config


def _set_nested_value(config: dict, keys: list, value):
    for key in keys[:-1]:
        if key not in config:
            config[key] = {}
        config = config[key]
    config[keys[-1]] = value


@app.route("/api/servers/<server_uuid>/spconfigs", methods=["GET"])
def get_server_spconfigs(server_uuid):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    editable = []
    for cfg_def in SPCONFIGS:
        file_path = os.path.join(server.path, *cfg_def["path"].split("/"))
        if not os.path.exists(file_path):
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                if cfg_def["type"] == "properties":
                    config_data = javaproperties.load(f)
                elif cfg_def["type"] == "yml":
                    config_data = yaml.safe_load(f) or {}
                else:
                    continue
        except Exception:
            continue

        keys_with_values = []
        for key_def in cfg_def["keys"]:
            value = _get_nested_value(config_data, key_def["key"].split("."))
            if value is not None:
                key_info = {
                    "name": key_def["name"],
                    "key": key_def["key"],
                    "description": key_def["description"],
                    "tips": key_def.get("tips", ""),
                    "type": key_def["type"],
                    "current_value": str(value),
                    "danger": key_def.get("danger", False),
                }
                if key_def.get("choices"):
                    key_info["choices"] = key_def["choices"]
                keys_with_values.append(key_info)

        if keys_with_values:
            editable.append(
                {
                    "name": cfg_def["name"],
                    "path": cfg_def["path"],
                    "description": cfg_def["description"],
                    "type": cfg_def["type"],
                    "keys": keys_with_values,
                }
            )

    return jsonify({"configs": editable})


@app.route("/api/servers/<server_uuid>/spconfigs/<path:config_path>", methods=["PUT"])
def update_server_spconfig(server_uuid, config_path):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        return jsonify({"error": "Server not found"}), 404

    data: dict = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    key = data.get("key")
    value = data.get("value")

    if not key:
        return jsonify({"success": False, "error": "Missing 'key' in body"}), 400
    if value is None:
        return jsonify({"success": False, "error": "Missing 'value' in body"}), 400

    # Find config definition
    cfg_def = None
    for c in SPCONFIGS:
        if c["path"] == config_path:
            cfg_def = c
            break

    if not cfg_def:
        return jsonify({"success": False, "error": f"Config '{config_path}' not found"}), 404

    file_path = os.path.join(server.path, *config_path.split("/"))
    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": f"Config file not found: {config_path}"}), 404

    # Find key definition to validate type
    key_def = None
    for kd in cfg_def["keys"]:
        if kd["key"] == key:
            key_def = kd
            break

    if not key_def:
        return jsonify({"success": False, "error": f"Key '{key}' not found in config"}), 404

    # Type validation
    try:
        if key_def["type"] == "int":
            value = int(value)
        elif key_def["type"] == "bool":
            if cfg_def["type"] == "properties":
                value = "true" if value in (True, "true", "True") else "false"
            else:
                value = bool(value) if isinstance(value, bool) else value in ("true", "True", True)
        elif key_def["type"] == "choice" and value not in (key_def.get("choices") or []):
            return jsonify(
                {
                    "success": False,
                    "error": f"Invalid choice '{value}'. Valid: {key_def['choices']}",
                }
            ), 400
    except (ValueError, TypeError):
        return jsonify(
            {
                "success": False,
                "error": f"Type mismatch: expected {key_def['type']}",
            }
        ), 400

    try:
        with open(file_path, encoding="utf-8") as f:
            if cfg_def["type"] == "properties":
                config_data = javaproperties.load(f)
            else:
                config_data = yaml.safe_load(f) or {}

        _set_nested_value(config_data, key.split("."), value)

        with open(file_path, "w", encoding="utf-8") as f:
            if cfg_def["type"] == "properties":
                javaproperties.dump(config_data, f)
            else:
                yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "key": key, "value": value})


# ── Task endpoints ───────────────────────────────────────────────


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    status_param = request.args.get("status", default=None)
    status = TaskStatus.from_str(status_param) if status_param else None

    return jsonify({"tasks": [t.to_dict() for t in tm.get_tasks(status)]})


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    task = tm.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task.to_dict())


# ── Java endpoints ───────────────────────────────────────────────


@app.route("/api/java/versions", methods=["GET"])
def list_java_versions():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401

    success, result, error = tm.create_and_run_sync("java", "list_installed_versions")
    if not success:
        return jsonify({"error": error}), 500

    return jsonify({"versions": result.data.get("versions", []) if result else []})


# ── WebSocket: Server Terminal ──────────────────────────────────

if sock is not None:
    @sock.route("/api/tasks/stream")
    def task_stream(ws):
        """Push task snapshots. The client never needs to poll task endpoints."""
        if not authenticate_websocket(ws, auth.validate_token):
            return

        send_lock = threading.Lock()

        def send(event):
            with send_lock:
                ws.send(json.dumps(event))

        unsubscribe = tm.subscribe(send)
        try:
            send({"type": "task_snapshot", "tasks": [t.to_dict() for t in tm.get_tasks()]})
            while ws.receive() is not None:
                pass
        except Exception:
            pass
        finally:
            unsubscribe()

    @sock.route("/api/servers/<server_uuid>/terminal")
    def server_terminal(ws, server_uuid):
        if not authenticate_websocket(ws, auth.validate_token):
            return

        server = workspace.get_server_by_uuid(server_uuid)
        if not server:
            ws.send(json.dumps({"type": "error", "message": "Server not found"}))
            ws.close()
            return

        # Send connection confirmation
        ws.send(
            json.dumps(
                {
                    "type": "status",
                    "message": f"Connected to terminal for {server.name}",
                    "server_uuid": server_uuid,
                    "server_name": server.name,
                    "running": spm.is_running(server_uuid),
                }
            )
        )

        # Send buffered history if server is running (skip on reconnect)
        skip_history = ws_request.args.get("skip_history", "0") == "1"
        if spm.is_running(server_uuid) and not skip_history:
            for line in spm.get_history(server_uuid):
                ws.send(json.dumps({"type": "log", "line": line}))

        # Register as listener for live stdout
        spm.add_listener(server_uuid, ws)

        try:
            while True:
                message = ws.receive()
                if message:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "command" and data.get("command"):
                            success, msg = spm.send_command(server_uuid, data["command"])
                            if not success:
                                ws.send(json.dumps({"type": "error", "message": msg}))
                        elif data.get("type") == "set_encoding" and data.get("encoding"):
                            new_enc = data["encoding"]
                            if new_enc in ("utf-8", "gbk", "gb2312", "gb18030", "latin-1"):
                                spm.set_encoding(server_uuid, new_enc)
                                ws.send(
                                    json.dumps(
                                        {"type": "status", "message": f"Encoding set to {new_enc}"}
                                    )
                                )
                            else:
                                ws.send(
                                    json.dumps(
                                        {
                                            "type": "error",
                                            "message": f"Unsupported encoding: {new_enc}",
                                        }
                                    )
                                )
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        finally:
            spm.remove_listener(server_uuid, ws)


# ── System monitoring endpoints ──────────────────────────────────


@app.route("/api/system/stats", methods=["GET"])
def system_stats():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    paths = [s.path for s in workspace.get_valid_servers()]
    stats = monitor.get_current_stats(paths)
    return jsonify(stats)


@app.route("/api/system/disk-history", methods=["GET"])
def system_disk_history():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    history = monitor.get_disk_history()
    return jsonify({"history": history})


@app.route("/api/system/license", methods=["GET"])
def system_license():
    license_path = _get_app_path("LICENSE")
    try:
        with open(license_path, encoding="utf-8") as f:
            text = f.read()
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Modrinth market and add-on management ─────────────────────────

@app.route("/api/mrpack/inspect", methods=["POST"])
def inspect_mrpack_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename.lower().endswith(".mrpack"):
        return jsonify({"error": "请选择 .mrpack 文件"}), 400
    try:
        return jsonify(inspect_mrpack(uploaded))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logger.error(f"解析 mrpack 失败: {error}")
        return jsonify({"error": f"解析 mrpack 失败: {error}"}), 500


@app.route("/api/mrpack/import", methods=["POST"])
def import_mrpack_endpoint():
    if not auth.require_auth(request):
        return jsonify({"error": auth.get_auth_error(request)}), 401
    data = request.get_json() or {}
    metadata = {
        "name": data.get("name"),
        "max_memory": data.get("max_memory", 4096),
        "java_version": data.get("java_version", "21"),
        "extra_args": data.get("extra_args", ""),
    }
    validation_error = _validate_server_settings(metadata)
    if validation_error:
        return jsonify({"error": validation_error}), 400
    session_id = str(data.get("session_id", ""))
    selected_paths = data.get("selected_paths") or []
    if not isinstance(selected_paths, list) or not selected_paths:
        return jsonify({"error": "selected_paths 必须为数组"}), 400
    if len(selected_paths) > MAX_PACK_FILES or not all(
        isinstance(path, str) and len(path) <= 1024 for path in selected_paths
    ):
        return jsonify({"error": "selected_paths 包含无效项目"}), 400
    task = tm.create_composite_task(
        execute_fn=lambda task, _: import_mrpack_flow(task, session_id, selected_paths, metadata, workspace)
    )
    task.title = f"导入模组包：{metadata['name']}"
    task.set_step("queued", "等待导入", "pending")
    tm.run_task_background(task.task_id)
    return jsonify({"success": True, "task_id": task.task_id})


def _market_server(server_uuid):
    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        raise LookupError("Server not found")
    return server


@app.route("/api/market/server/<server_uuid>", methods=["GET"])
def market_server_info(server_uuid):
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try: return jsonify(server_market_info(_market_server(server_uuid)))
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except ValueError as error: return jsonify({"error": str(error)}), 400


@app.route("/api/market/categories/<server_uuid>", methods=["GET"])
def market_categories(server_uuid):
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try: return jsonify({"categories": categories_for(_market_server(server_uuid))})
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except Exception as error: return jsonify({"error": str(error)}), 502


@app.route("/api/market/search", methods=["GET"])
def market_search():
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try:
        return jsonify(search_projects(_market_server(request.args.get("server_uuid", "")), request.args.get("query", ""), request.args.get("category", ""), request.args.get("index", "relevance"), request.args.get("offset", type=int, default=0), request.args.get("limit", type=int, default=20)))
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except ValueError as error: return jsonify({"error": str(error)}), 400
    except Exception as error: return jsonify({"error": str(error)}), 502


@app.route("/api/market/projects/<project_id>/versions", methods=["GET"])
def market_versions(project_id):
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try: return jsonify({"versions": project_versions(_market_server(request.args.get("server_uuid", "")), project_id)})
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except Exception as error: return jsonify({"error": str(error)}), 502


@app.route("/api/market/versions/<version_id>", methods=["GET"])
def market_version(version_id):
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try: return jsonify(version_details(_market_server(request.args.get("server_uuid", "")), version_id))
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except Exception as error: return jsonify({"error": str(error)}), 502


@app.route("/api/market/install", methods=["POST"])
def market_install():
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    data = request.get_json() or {}
    try: server = _market_server(data.get("server_uuid", "")); version_id = data["version_id"]
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except KeyError: return jsonify({"error": "Missing version_id"}), 400
    task = tm.create_composite_task(execute_fn=lambda current, _progress: install_version(current, server, version_id, bool(data.get("install_dependencies", True))))
    task.title = f"安装附加到 {server.name}"
    task.set_step("queued", "等待下载", "pending")
    tm.run_task_background(task.task_id)
    return jsonify({"success": True, "task_id": task.task_id})


@app.route("/api/servers/<server_uuid>/addons", methods=["GET"])
def server_addons(server_uuid):
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try: return jsonify(list_addons(_market_server(server_uuid)))
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except ValueError as error: return jsonify({"error": str(error)}), 400


@app.route("/api/servers/<server_uuid>/addons/<path:filename>", methods=["PUT", "DELETE"])
def server_addon(server_uuid, filename):
    if not auth.require_auth(request): return jsonify({"error": auth.get_auth_error(request)}), 401
    try:
        server = _market_server(server_uuid)
        if request.method == "DELETE": delete_addon(server, filename); return jsonify({"success": True})
        data = request.get_json() or {}; return jsonify(update_addon(server, filename, data.get("enabled"), data.get("name")))
    except LookupError as error: return jsonify({"error": str(error)}), 404
    except FileNotFoundError as error: return jsonify({"error": str(error)}), 404
    except ValueError as error: return jsonify({"error": str(error)}), 400


# ── Static / Ping ────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template_string(open(_get_app_path("index.html"), encoding="utf-8").read())


@app.route("/api/ping")
def ping():
    return "pong!"


# ── Helpers ──────────────────────────────────────────────────────


def _extract_bearer_token():
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


if __name__ == "__main__":
    # Run Flask in a daemon thread so the TUI owns the terminal
    flask_thread = threading.Thread(
        target=app.run,
        kwargs={
            "host": host,
            "port": port,
            "debug": False,
            "use_reloader": False,
        },
        daemon=True,
        name="Flask",
    )
    flask_thread.start()

    # TUI refreshes in its own daemon thread
    if ConfigKey.TUI_ENABLED.get():
        tui.start()
    else:
        logger.info("TUI 已禁用 (tui.enabled = false)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        tui.stop()
