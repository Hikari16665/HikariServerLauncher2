import os
import platform
import socket
import sys
import ipaddress
from dataclasses import dataclass
from typing import Optional, Dict

import httpx
import stun


@dataclass
class CGNATResult:
    is_cgnat: bool
    confidence: float  # 0.0-1.0
    reasons: list[str]


@dataclass
class NetworkInfo:
    nat_type: str
    mapped_address: Optional[str] = None
    mapped_port: Optional[int] = None
    external_ip: Optional[str] = None
    cgnat: Optional[CGNATResult] = None
    stun_server: Optional[str] = None


@dataclass
class SystemInfo:
    system: str
    system_version: str
    arch: str
    processor: str
    ip_address: Optional[str] = None
    public_ip: Optional[str] = None
    network_info: Optional[NetworkInfo] = None


class EnvironmentManager:
    _instance: Optional['EnvironmentManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._system_info: Optional[SystemInfo] = None
            self._stun_servers = self._load_stun_servers()
            self._initialized = True

    def _load_stun_servers(self) -> list[str]:
        if getattr(sys, "frozen", False):
            root = sys._MEIPASS
        else:
            root = os.path.dirname(os.path.dirname(__file__))
        stun_file = os.path.join(root, "stun_valid_hosts.txt")
        if os.path.exists(stun_file):
            with open(stun_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip() and not line.startswith("#")]
        return ["stun.l.google.com:19302"]

    def _check_cgnat(self, external_ip: Optional[str], public_ip: Optional[str], nat_type: str) -> CGNATResult:
        reasons = []
        score = 0.0
        max_score = 0.0

        max_score += 1.0
        if external_ip:
            try:
                ip_obj = ipaddress.ip_address(external_ip)
                if ip_obj.version == 4:
                    cgnat_ranges = [
                        "100.64.0.0/10",
                        "172.16.0.0/12",
                        "192.168.0.0/16",
                        "10.0.0.0/8",
                    ]
                    for cidr in cgnat_ranges:
                        if ip_obj in ipaddress.ip_network(cidr):
                            score += 1.0
                            reasons.append(f"IPv4 {external_ip} 在私有/CGNAT 范围 {cidr}")
                            break
                elif ip_obj.version == 6:
                    if ip_obj.is_private or ip_obj.ipv4_mapped:
                        score += 1.0
                        reasons.append(f"IPv6 {external_ip} 是私有地址或 IPv4 映射地址")
            except Exception:
                pass

        max_score += 1.0
        if public_ip and external_ip:
            try:
                public_obj = ipaddress.ip_address(public_ip)
                external_obj = ipaddress.ip_address(external_ip)
                if public_obj.version != external_obj.version:
                    score += 1.0
                    reasons.append(f"公网IP类型与STUN类型不一致 ({public_ip} vs {external_ip})")
            except Exception:
                pass

        max_score += 0.5
        if public_ip:
            try:
                ip_obj = ipaddress.ip_address(public_ip)
                if ip_obj.version == 6:
                    score += 0.3
                    reasons.append("拥有 IPv6 地址，可能同时使用 CGNAT IPv4")
            except Exception:
                pass

        max_score += 0.5
        if nat_type in ("Restricted", "Restrict Port", "Symmetric"):
            score += 0.5
            reasons.append(f"NAT 类型为 {nat_type}，通常出现在运营商网络中")

        confidence = score / max_score if max_score > 0 else 0.0
        is_cgnat = confidence >= 0.4

        return CGNATResult(is_cgnat=is_cgnat, confidence=confidence, reasons=reasons)

    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _get_public_ip(self) -> Optional[str]:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get("https://api.my-ip.io/v2/ip.json")
                return resp.json().get("ip") if resp.status_code == 200 else None
        except Exception:
            return None

    def _check_network(self) -> Optional[NetworkInfo]:
        source_ip = self._get_local_ip()
        
        for stun_server in self._stun_servers:
            try:
                if ":" not in stun_server:
                    continue
                host, port = stun_server.rsplit(":", 1)
                
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((source_ip, 0))
                    
                    nat_type, result = stun.get_nat_type(
                        s=s,
                        source_ip=source_ip,
                        source_port=s.getsockname()[1],
                        stun_host=host,
                        stun_port=int(port)
                    )

                    ext_ip = result.get('external_ip') or result.get('ExternalIP')
                    ext_port = result.get('external_port') or result.get('ExternalPort')
                    
                    if isinstance(ext_ip, tuple):
                        ext_ip, ext_port = ext_ip[0], ext_ip[1]

                    cgnat = self._check_cgnat(ext_ip, self._system_info.public_ip if self._system_info else None, nat_type)

                    return NetworkInfo(
                        nat_type=nat_type,
                        mapped_address=ext_ip,
                        mapped_port=ext_port,
                        external_ip=ext_ip,
                        cgnat=cgnat,
                        stun_server=stun_server
                    )
            except Exception:
                continue
        return None

    def check(self, include_public_ip: bool = True, check_network: bool = True) -> SystemInfo:
        self._system_info = SystemInfo(
            system=platform.system(),
            system_version=platform.version(),
            arch=platform.machine(),
            processor=platform.processor(),
            ip_address=self._get_local_ip()
        )

        if include_public_ip:
            self._system_info.public_ip = self._get_public_ip()

        if check_network:
            self._system_info.network_info = self._check_network()

        return self._system_info

    def get_system_info(self) -> Optional[SystemInfo]:
        return self._system_info

    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def is_linux() -> bool:
        return platform.system() == "Linux"
