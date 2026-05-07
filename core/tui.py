"""Terminal UI for HSL2 using Rich. Shows servers, tasks, and API log."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

MAX_LOG_ENTRIES = 100


@dataclass
class LogEntry:
    timestamp: str
    method: str
    path: str
    status: int
    duration_ms: float


class TUI:
    _instance: Optional["TUI"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.api_log: Deque[LogEntry] = deque(maxlen=MAX_LOG_ENTRIES)
        self._servers: list = []
        self._tasks: list = []
        self._processes: dict = {}
        self._host: str = "127.0.0.1"
        self._port: int = 5000
        self._live: Optional[Live] = None
        self._running: bool = False

    # ── public API called by app.py ──────────────────────────────

    def set_bind(self, host: str, port: int):
        self._host = host
        self._port = port

    def log_request(self, method: str, path: str, status: int, duration_ms: float):
        from datetime import datetime

        self.api_log.append(
            LogEntry(
                timestamp=datetime.now().strftime("%H:%M:%S"),
                method=method,
                path=path,
                status=status,
                duration_ms=round(duration_ms, 1),
            )
        )

    def update_state(self, servers, tasks, processes):
        self._servers = list(servers)
        self._tasks = list(tasks)
        self._processes = dict(processes)

    def start(self):
        """Launch the TUI in a daemon thread."""
        self._running = True
        import threading

        def _run():
            with Live(
                self._render(), console=Console(), refresh_per_second=4, screen=True
            ) as live:
                self._live = live
                while self._running:
                    time.sleep(0.25)
                    live.update(self._render())

        t = threading.Thread(target=_run, daemon=True, name="TUI")
        t.start()

    def stop(self):
        self._running = False

    # ── internal rendering ───────────────────────────────────────

    def _render(self) -> Layout:
        root = Layout()
        root.split(
            Layout(name="header", size=4),
            Layout(name="body", ratio=1),
            Layout(name="log", size=12),
        )
        root["body"].split_row(
            Layout(name="servers", ratio=1),
            Layout(name="tasks", ratio=1),
        )

        root["header"].update(self._render_header())
        root["servers"].update(self._render_servers())
        root["tasks"].update(self._render_tasks())
        root["log"].update(self._render_log())
        return root

    def _render_header(self) -> Panel:
        from .logger import Logger

        log = Logger()
        text = Text()
        text.append("Hikari Server Launcher", style="bold cyan")
        text.append(f"  v2.0.0\n", style="dim")
        text.append(
            f"http://{self._host}:{self._port}",
            style="underline white",
        )
        text.append("    ", style="")
        text.append(f"Servers: {len(self._servers)}", style="green")
        text.append("    ", style="")
        text.append(
            f"Tasks: {sum(1 for t in self._tasks if t.status.value == 'running')} active",
            style="yellow",
        )
        if log.error_count or log.warning_count:
            text.append("    ", style="")
            if log.error_count:
                text.append(f"✗ {log.error_count}", style="bold red")
            if log.error_count and log.warning_count:
                text.append(" ", style="")
            if log.warning_count:
                text.append(f"⚠ {log.warning_count}", style="yellow")
        text.append("\n")
        text.append("⚠ 不能关闭此窗口 — 关闭此窗口将退出服务端", style="bold red")
        return Panel(text, box=box.ROUNDED)

    def _render_servers(self) -> Panel:
        tbl = Table(
            title="Servers", box=box.SIMPLE, show_header=True, header_style="bold"
        )
        tbl.add_column("Name")
        tbl.add_column("Type", style="dim")
        tbl.add_column("State")
        tbl.add_column("Details", style="dim")

        for s in self._servers:
            proc = self._processes.get(s.uuid)
            if proc:
                state = Text("● on", style="green")
                details = f"PID {proc.pid}  up {proc.uptime:.0f}s"
            else:
                state = Text("○ off", style="dim")
                details = "stopped"

            safe_name = s.name[:20] if s.name else "?"
            tbl.add_row(safe_name, s.server_type.value[:8], state, details)

        if not self._servers:
            tbl.add_row("(none)", "", "", "")
        return Panel(tbl, box=box.ROUNDED)

    def _render_tasks(self) -> Panel:
        tbl = Table(
            title="Tasks", box=box.SIMPLE, show_header=True, header_style="bold"
        )
        tbl.add_column("ID", style="dim")
        tbl.add_column("State")
        tbl.add_column("Progress")
        tbl.add_column("Message")

        for t in self._tasks:
            tid = t.task_id[:8]
            st = t.status.value
            if st == "completed":
                icon = Text("✓", style="green")
            elif st == "failed":
                icon = Text("✗", style="bold red")
            elif st == "running":
                icon = Text("●", style="yellow")
            elif st == "cancelled":
                icon = Text("✗", style="dim")
            else:
                icon = Text("○", style="dim")

            pct = f"{t.progress:.0f}%" if t.progress else "-"
            msg = t.progress_message or t.error_message or ""
            tbl.add_row(tid, icon, pct, msg[:45])

        if not self._tasks:
            tbl.add_row("(none)", "", "", "")
        return Panel(tbl, box=box.ROUNDED)

    def _render_log(self) -> Panel:
        txt = Text()
        for e in list(self.api_log)[-16:]:
            color = "green" if e.status < 300 else "yellow" if e.status < 400 else "red"
            txt.append(f"{e.timestamp}  ", style="dim")
            txt.append(f"{e.method:6}", style="cyan")
            txt.append(f" {e.path[:45]:46}", style="white")
            txt.append(f" {e.status} ", style=color)
            txt.append(f"({e.duration_ms:.0f}ms)", style="dim")
            txt.append("\n")
        if not txt:
            txt = Text("(no requests yet)", style="dim italic")
        return Panel(txt, title="API Log", box=box.ROUNDED)
