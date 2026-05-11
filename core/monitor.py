import threading
import time
import psutil
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable


@dataclass
class SystemStats:
    cpu_percent: float
    mem_used_gb: float
    mem_total_gb: float
    mem_percent: float
    net_sent_kbps: float
    net_recv_kbps: float
    disk_total_gb: float
    disk_used_gb: float
    timestamp: float


@dataclass
class DiskSnapshot:
    timestamp: float
    disk_total_gb: float
    disk_used_gb: float


class SystemMonitor:
    _instance: Optional["SystemMonitor"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._prev_net_io = psutil.net_io_counters()
        self._prev_net_time = time.time()
        self._disk_history: List[DiskSnapshot] = []
        self._history_lock = threading.Lock()
        self._collector_thread: Optional[threading.Thread] = None

    def get_current_stats(self, server_paths: List[str] = None) -> dict:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        net = psutil.net_io_counters()
        now = time.time()
        elapsed = now - self._prev_net_time
        if elapsed > 0 and self._prev_net_io:
            sent_kbps = (
                (net.bytes_sent - self._prev_net_io.bytes_sent) / elapsed / 1024
            )
            recv_kbps = (
                (net.bytes_recv - self._prev_net_io.bytes_recv) / elapsed / 1024
            )
        else:
            sent_kbps = 0
            recv_kbps = 0
        self._prev_net_io = net
        self._prev_net_time = now

        disk_total = 0.0
        disk_used = 0.0
        if server_paths:
            for path in server_paths:
                try:
                    usage = psutil.disk_usage(path)
                    disk_total += usage.total
                    disk_used += usage.used
                except Exception:
                    pass

        stats = SystemStats(
            cpu_percent=round(cpu, 1),
            mem_used_gb=round(mem.used / (1024**3), 2),
            mem_total_gb=round(mem.total / (1024**3), 2),
            mem_percent=round(mem.percent, 1),
            net_sent_kbps=round(sent_kbps, 2),
            net_recv_kbps=round(recv_kbps, 2),
            disk_total_gb=round(disk_total / (1024**3), 2) if disk_total > 0 else 0,
            disk_used_gb=round(disk_used / (1024**3), 2) if disk_total > 0 else 0,
            timestamp=now,
        )
        return asdict(stats)

    def get_disk_history(self) -> List[dict]:
        with self._history_lock:
            return [asdict(s) for s in self._disk_history]

    def collect_disk_snapshot(self, server_paths: List[str]):
        disk_total = 0.0
        disk_used = 0.0
        if server_paths:
            for path in server_paths:
                try:
                    usage = psutil.disk_usage(path)
                    disk_total += usage.total
                    disk_used += usage.used
                except Exception:
                    pass
        snap = DiskSnapshot(
            timestamp=time.time(),
            disk_total_gb=round(disk_total / (1024**3), 2) if disk_total > 0 else 0,
            disk_used_gb=round(disk_used / (1024**3), 2) if disk_total > 0 else 0,
        )
        with self._history_lock:
            self._disk_history.append(snap)
            if len(self._disk_history) > 168:
                self._disk_history = self._disk_history[-168:]

    def start_collector(self, get_server_paths_callback: Callable[[], List[str]]):
        if self._collector_thread and self._collector_thread.is_alive():
            return

        def _loop():
            # Take an initial snapshot immediately
            try:
                paths = get_server_paths_callback()
                self.collect_disk_snapshot(paths)
            except Exception:
                pass
            while True:
                time.sleep(3600)
                try:
                    paths = get_server_paths_callback()
                    self.collect_disk_snapshot(paths)
                except Exception:
                    pass

        self._collector_thread = threading.Thread(
            target=_loop, daemon=True, name="disk-collector"
        )
        self._collector_thread.start()
