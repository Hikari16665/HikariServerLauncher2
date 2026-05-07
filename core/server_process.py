"""ServerProcessManager — manages Minecraft server subprocesses.

Handles start / stop / kill / command / stdout broadcast to WebSocket listeners.
"""

import os
import platform
import queue
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set

from .logger import Logger
from .workspace import Server, ServerType


def _find_java_binary(java_version: str) -> Optional[str]:
    """Find the java binary for the given version."""
    java_dir = os.path.join(
        sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(__file__)),
        "java"
    )
    version_dir = os.path.join(java_dir, java_version)
    if not os.path.exists(version_dir):
        return None

    if platform.system() == "Windows":
        candidates = [
            os.path.join(version_dir, "bin", "java.exe"),
            os.path.join(version_dir, "java.exe"),
        ]
    else:
        candidates = [
            os.path.join(version_dir, "bin", "java"),
            os.path.join(version_dir, "java"),
        ]

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _build_forge_like_command(server: Server, java_binary: str, lib_path: str) -> List[str]:
    """Build a run command for Forge or NeoForge using args-file launch pattern."""
    jvm_args_path = os.path.join(server.path, "user_jvm_args.txt")
    user_jvm_args = []
    if os.path.exists(jvm_args_path):
        with open(jvm_args_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    user_jvm_args.append(line)

    args_file = None
    libraries_dir = os.path.join(server.path, "libraries", *lib_path.split("/"))
    if os.path.exists(libraries_dir):
        for entry in os.listdir(libraries_dir):
            version_dir = os.path.join(libraries_dir, entry)
            if os.path.isdir(version_dir):
                if platform.system() != "Windows":
                    candidate = os.path.join(version_dir, "unix_args.txt")
                else:
                    candidate = os.path.join(version_dir, "win_args.txt")
                if os.path.exists(candidate):
                    args_file = candidate
                    break

    cmd = [java_binary, "-Dfile.encoding=utf-8", f"-Xmx{server.max_memory}M"]
    cmd.extend(user_jvm_args)
    if args_file:
        cmd.extend(["@" + args_file])
    if server.extra_args:
        cmd.append(server.extra_args)
    return cmd


def _build_run_command(server: Server) -> List[str]:
    """Build the java run command for a server."""
    java_binary = _find_java_binary(server.java_version)
    if not java_binary:
        # Fall back to system java
        java_binary = "java"

    if server.server_type in (ServerType.VANILLA, ServerType.PAPER, ServerType.FABRIC, ServerType.APRIL):
        return [
            java_binary,
            "-Dfile.encoding=utf-8",
            f"-Xmx{server.max_memory}M",
            "-jar",
            "server.jar",
        ] + ([server.extra_args] if server.extra_args else [])

    elif server.server_type == ServerType.FORGE:
        return _build_forge_like_command(server, java_binary, "net/minecraftforge/forge")

    elif server.server_type == ServerType.NEOFORGE:
        return _build_forge_like_command(server, java_binary, "net/neoforged/neoforge")

    else:
        # Generic fallback
        return [
            java_binary,
            "-Dfile.encoding=utf-8",
            f"-Xmx{server.max_memory}M",
            "-jar",
            "server.jar",
        ]


def export_launch_script(server: Server, fmt: str = "batch") -> str:
    """Generate a launch script (.bat or .sh) for the server.

    Returns the script content as a string. Does not write to disk.
    """
    command = _build_run_command(server)
    cmd_str = " ".join(command)

    if fmt == "batch":
        return "\r\n".join([
            "@echo off",
            f'cd /d "{server.path}"',
            cmd_str,
        ])
    elif fmt == "shell":
        return "\n".join([
            "#!/bin/bash",
            f'cd "{server.path}"',
            cmd_str,
        ])
    else:
        raise ValueError(f"Unsupported format: {fmt}. Use 'batch' or 'shell'.")


class RunningServer:
    """Tracks a single running server process."""

    def __init__(self, server_uuid: str, process: subprocess.Popen, command: List[str]):
        self.server_uuid = server_uuid
        self.process = process
        self.command = command
        self.started_at = time.time()
        self._history: deque = deque(maxlen=2000)
        self._listeners: Set = set()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stdin_queue: queue.Queue = queue.Queue()
        self._stdin_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    @property
    def uptime(self) -> float:
        return time.time() - self.started_at

    def broadcast_line(self, line: str):
        """Send a line to all WebSocket listeners and store in history."""
        self._history.append(line)
        dead = set()
        for ws in self._listeners:
            try:
                import json

                ws.send(json.dumps({"type": "log", "line": line}))
            except Exception:
                dead.add(ws)
        self._listeners -= dead

    def broadcast_status(self, message: str):
        """Send a status message to all listeners."""
        import json

        dead = set()
        for ws in self._listeners:
            try:
                ws.send(json.dumps({"type": "status", "message": message}))
            except Exception:
                dead.add(ws)
        self._listeners -= dead

    def add_listener(self, ws):
        self._listeners.add(ws)

    def remove_listener(self, ws):
        self._listeners.discard(ws)

    def send_command(self, command: str):
        """Queue a command to be sent to stdin."""
        self._stdin_queue.put(command)


class ServerProcessManager:
    """Singleton that manages all running server processes."""

    _instance: Optional["ServerProcessManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._running: Dict[str, RunningServer] = {}
            self._initialized = True

    def get(self, server_uuid: str) -> Optional[RunningServer]:
        return self._running.get(server_uuid)

    def is_running(self, server_uuid: str) -> bool:
        rs = self._running.get(server_uuid)
        return rs is not None and rs.is_running

    def start(self, server: Server) -> tuple[bool, str]:
        """Spawn the server process."""
        if server.uuid in self._running:
            rs = self._running[server.uuid]
            if rs.is_running:
                return False, "Server is already running"
            # Clean up dead entry
            del self._running[server.uuid]

        command = _build_run_command(server)

        try:
            process = subprocess.Popen(
                command,
                cwd=server.path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError:
            log = Logger()
            log.error(f"服务器 {server.uuid[:8]} 启动失败: Java binary 未找到 (version {server.java_version})")
            return False, f"Java binary not found for version {server.java_version}"
        except Exception as e:
            log = Logger()
            log.error(f"服务器 {server.uuid[:8]} 启动失败: {e}")
            return False, str(e)

        rs = RunningServer(server.uuid, process, command)

        # stdout reader thread
        def _read_stdout():
            try:
                for line in iter(process.stdout.readline, ""):
                    if rs._stop_event.is_set():
                        break
                    line = line.rstrip("\n\r")
                    if line:
                        rs.broadcast_line(line)
            except Exception as e:
                log = Logger()
                log.error(f"服务器 {server.uuid[:8]} stdout 读取异常: {e}")
            finally:
                # Process ended — check exit code
                exit_code = process.poll()
                log = Logger()
                if exit_code == 0:
                    log.info(f"服务器 {server.uuid[:8]} 进程正常退出 (exit code: 0)")
                elif exit_code is not None:
                    log.error(f"服务器 {server.uuid[:8]} 进程异常退出 (exit code: {exit_code})")
                else:
                    log.warning(f"服务器 {server.uuid[:8]} 进程结束 (exit code: N/A)")
                rs.broadcast_status("Server process ended")

        rs._stdout_thread = threading.Thread(
            target=_read_stdout, daemon=True, name=f"stdout-{server.uuid[:8]}"
        )
        rs._stdout_thread.start()

        # stdin writer thread
        def _write_stdin():
            while not rs._stop_event.is_set() and process.poll() is None:
                try:
                    cmd = rs._stdin_queue.get(timeout=0.5)
                    if cmd is None:
                        break
                    process.stdin.write(cmd + "\n")
                    process.stdin.flush()
                except queue.Empty:
                    continue
                except Exception:
                    break

        rs._stdin_thread = threading.Thread(
            target=_write_stdin, daemon=True, name=f"stdin-{server.uuid[:8]}"
        )
        rs._stdin_thread.start()

        self._running[server.uuid] = rs
        rs.broadcast_status(f"Server started (PID: {process.pid})")
        return True, f"Server started (PID: {process.pid})"

    def stop(self, server_uuid: str, timeout: int = 60) -> tuple[bool, str]:
        """Gracefully stop by sending 'stop' command."""
        rs = self._running.get(server_uuid)
        if not rs or not rs.is_running:
            return False, "Server is not running"

        rs.broadcast_status("Stopping server...")
        rs.send_command("stop")

        # Wait for graceful shutdown
        wait_start = time.time()
        while time.time() - wait_start < timeout:
            if rs.process.poll() is not None:
                rs.broadcast_status("Server stopped gracefully")
                self._cleanup(server_uuid)
                return True, "Server stopped gracefully"
            time.sleep(0.5)

        # Timeout — force kill
        return self.kill(server_uuid)

    def kill(self, server_uuid: str) -> tuple[bool, str]:
        """Force kill the server process."""
        rs = self._running.get(server_uuid)
        if not rs:
            return False, "Server not found"

        if rs.process and rs.process.poll() is None:
            rs.broadcast_status("Force killing server...")
            try:
                rs.process.kill()
                rs.process.wait(timeout=5)
            except Exception:
                import psutil

                try:
                    parent = psutil.Process(rs.process.pid)
                    for child in parent.children(recursive=True):
                        child.kill()
                    parent.kill()
                except Exception:
                    pass

        self._cleanup(server_uuid)
        return True, "Server killed"

    def send_command(self, server_uuid: str, command: str) -> tuple[bool, str]:
        """Send a command to the server's stdin."""
        rs = self._running.get(server_uuid)
        if not rs or not rs.is_running:
            return False, "Server is not running"
        rs.send_command(command)
        return True, "Command sent"

    def get_status(self, server_uuid: str) -> Dict[str, Any]:
        """Get server running status."""
        rs = self._running.get(server_uuid)
        if not rs or not rs.is_running:
            return {"running": False}

        return {
            "running": True,
            "pid": rs.pid,
            "uptime": rs.uptime,
            "command": " ".join(rs.command),
        }

    def get_history(self, server_uuid: str) -> List[str]:
        """Get buffered stdout history for a server."""
        rs = self._running.get(server_uuid)
        if not rs:
            return []
        return list(rs._history)

    def add_listener(self, server_uuid: str, ws):
        """Add a WebSocket listener to a running server's stdout broadcast."""
        rs = self._running.get(server_uuid)
        if rs:
            rs.add_listener(ws)

    def remove_listener(self, server_uuid: str, ws):
        """Remove a WebSocket listener."""
        rs = self._running.get(server_uuid)
        if rs:
            rs.remove_listener(ws)

    def _cleanup(self, server_uuid: str):
        """Clean up a stopped server."""
        rs = self._running.pop(server_uuid, None)
        if rs:
            rs._stop_event.set()
            if rs._stdin_thread and rs._stdin_thread.is_alive():
                rs._stdin_queue.put(None)  # Wake up the stdin thread
            rs._listeners.clear()
