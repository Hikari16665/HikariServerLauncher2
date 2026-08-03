import ipaddress
import os
import platform
import re
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

import httpx
import stun

CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")
PRIVATE_V4_NETWORKS = tuple(
    ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
IPV4_PATTERN = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
)


@dataclass
class CGNATResult:
    is_cgnat: bool
    confidence: float
    reasons: list[str]
    verdict: str = "not_detected"
    signals: dict[str, bool | int | float | str] = field(default_factory=dict)


@dataclass
class StunObservation:
    server: str
    nat_type: str
    external_ip: str
    external_port: int | None


@dataclass
class NetworkInfo:
    nat_type: str
    mapped_address: str | None = None
    mapped_port: int | None = None
    external_ip: str | None = None
    cgnat: CGNATResult | None = None
    stun_server: str | None = None
    stun_observations: list[dict] = field(default_factory=list)
    route_hops: list[str] = field(default_factory=list)
    router_wan_ip: str | None = None


@dataclass
class SystemInfo:
    system: str
    system_version: str
    arch: str
    processor: str
    ip_address: str | None = None
    public_ip: str | None = None
    network_info: NetworkInfo | None = None


class EnvironmentManager:
    _instance: Optional["EnvironmentManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._system_info: SystemInfo | None = None
            self._stun_servers = self._load_stun_servers()
            self._public_ipv4: str | None = None
            self._initialized = True

    def _load_stun_servers(self) -> list[str]:
        root = (
            sys._MEIPASS
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.dirname(__file__))
        )  # type: ignore
        stun_file = os.path.join(root, "stun_valid_hosts.txt")
        if os.path.exists(stun_file):
            with open(stun_file, encoding="utf-8") as file:
                return [line.strip() for line in file if line.strip() and not line.startswith("#")]
        return ["stun.qq.com:3478", "stun.miwifi.com:3478", "stun.l.google.com:19302"]

    @staticmethod
    def _is_cgnat_address(value: str | None) -> bool:
        if not value:
            return False
        try:
            address = ipaddress.ip_address(value)
            return address.version == 4 and address in CGNAT_NETWORK
        except ValueError:
            return False

    @staticmethod
    def _is_private_v4(value: str | None) -> bool:
        if not value:
            return False
        try:
            address = ipaddress.ip_address(value)
            return address.version == 4 and any(
                address in network for network in PRIVATE_V4_NETWORKS
            )
        except ValueError:
            return False

    @staticmethod
    def _public_ipv4_from(values: list[str | None]) -> str | None:
        for value in values:
            if not value:
                continue
            try:
                address = ipaddress.ip_address(value)
                if address.version == 4:
                    return str(address)
            except ValueError:
                continue
        return None

    def _check_cgnat(
        self,
        observations: list[StunObservation],
        public_ipv4: str | None,
        route_hops: list[str],
        router_wan_ip: str | None = None,
    ) -> CGNATResult:
        reasons: list[str] = []
        signals: dict[str, bool | int | float | str] = {}
        weights: list[float] = []

        mapped_ipv4 = self._public_ipv4_from([item.external_ip for item in observations])
        mapped_ips = {item.external_ip for item in observations if item.external_ip}
        nat_types = {item.nat_type for item in observations if item.nat_type}

        router_wan_is_shared = self._is_cgnat_address(router_wan_ip)
        router_wan_is_private = self._is_private_v4(router_wan_ip)
        router_wan_mismatch = bool(
            router_wan_ip
            and public_ipv4
            and not router_wan_is_private
            and not router_wan_is_shared
            and router_wan_ip != public_ipv4
        )
        signals["router_wan_ip"] = router_wan_ip or ""
        signals["router_wan_in_100_64_10"] = router_wan_is_shared
        signals["router_wan_private"] = router_wan_is_private
        signals["router_wan_public_mismatch"] = router_wan_mismatch
        if router_wan_is_shared:
            weights.append(0.99)
            reasons.append(f"路由器 WAN 地址 {router_wan_ip} 位于运营商共享地址段 100.64.0.0/10")
        elif router_wan_is_private:
            weights.append(0.58)
            reasons.append(f"路由器 WAN 地址 {router_wan_ip} 是私网地址，存在上游二级 NAT")
        elif router_wan_mismatch:
            weights.append(0.78)
            reasons.append(
                f"路由器 WAN 地址与互联网出口 IPv4 不一致（{router_wan_ip} / {public_ipv4}）"
            )

        mapped_is_shared = self._is_cgnat_address(mapped_ipv4)
        signals["mapped_in_100_64_10"] = mapped_is_shared
        if mapped_is_shared:
            weights.append(0.98)
            reasons.append(f"STUN 映射地址 {mapped_ipv4} 位于运营商共享地址段 100.64.0.0/10")

        public_is_non_global = False
        if public_ipv4:
            try:
                public_obj = ipaddress.ip_address(public_ipv4)
                public_is_non_global = not public_obj.is_global
            except ValueError:
                pass
        signals["http_ipv4_non_global"] = public_is_non_global
        if public_is_non_global:
            weights.append(0.9)
            reasons.append(f"HTTP 检测到的 IPv4 {public_ipv4} 不是可直接路由的公网地址")

        address_mismatch = bool(mapped_ipv4 and public_ipv4 and mapped_ipv4 != public_ipv4)
        signals["stun_http_ipv4_mismatch"] = address_mismatch
        if address_mismatch:
            weights.append(0.72)
            reasons.append(f"STUN IPv4 与 HTTP 公网 IPv4 不一致（{mapped_ipv4} / {public_ipv4}）")

        upstream_hops = route_hops[1:] if len(route_hops) > 1 else []
        shared_hops = [hop for hop in upstream_hops if self._is_cgnat_address(hop)]
        private_hops = [hop for hop in upstream_hops if self._is_private_v4(hop)]
        signals["shared_route_hops"] = len(shared_hops)
        signals["private_route_hops"] = len(private_hops)
        if shared_hops:
            weights.append(0.88)
            reasons.append(f"本地网关之后发现运营商共享地址：{', '.join(shared_hops[:3])}")
        elif len(set(private_hops)) >= 2:
            weights.append(0.48)
            reasons.append(f"本地网关之后连续经过多个私网地址：{', '.join(private_hops[:3])}")
        elif private_hops:
            weights.append(0.22)
            reasons.append(f"本地网关之后发现运营商内部私网跳点：{private_hops[0]}")

        unstable_mapping = len(mapped_ips) > 1
        signals["distinct_stun_addresses"] = len(mapped_ips)
        if unstable_mapping:
            weights.append(0.52)
            reasons.append(
                f"不同 STUN 服务器返回 {len(mapped_ips)} 个外部地址，映射可能经过多级运营商 NAT"
            )

        normalized_nat_types = {
            re.sub(r"[^a-z]+", " ", value.lower()).strip() for value in nat_types
        }
        symmetric = any("symmetric" in value for value in normalized_nat_types)
        restricted = any("restrict" in value for value in normalized_nat_types)
        signals["symmetric_nat"] = symmetric
        signals["restricted_nat"] = restricted
        if symmetric:
            weights.append(0.68)
            reasons.append(
                "检测到对称型 NAT；在移动网络和大陆运营商宽带中通常意味着多级 NAT，"
                "但少数本地路由器也可能使用这种映射方式"
            )
        elif restricted:
            weights.append(0.35)
            reasons.append("检测到端口受限 NAT")

        # Combine independent evidence without allowing weak signals to add up linearly too fast.
        confidence = 0.0
        for weight in weights:
            confidence = 1.0 - (1.0 - confidence) * (1.0 - weight)

        has_strong_carrier_signal = bool(
            mapped_is_shared
            or public_is_non_global
            or address_mismatch
            or shared_hops
            or unstable_mapping
            or router_wan_is_shared
            or router_wan_mismatch
            or (symmetric and bool(mapped_ipv4))
            or (router_wan_is_private and (symmetric or restricted or len(set(private_hops)) >= 2))
            or (len(set(private_hops)) >= 2 and (symmetric or restricted))
        )
        is_cgnat = has_strong_carrier_signal and confidence >= 0.65
        directly_confirmed = bool(
            mapped_is_shared or public_is_non_global or shared_hops or router_wan_is_shared
        )
        verdict = (
            "confirmed"
            if is_cgnat and directly_confirmed
            else "likely"
            if is_cgnat
            else "not_detected"
        )

        if not reasons:
            reasons.append("未发现运营商级 NAT 的有效证据")
        elif not is_cgnat:
            reasons.append("现有信号不足以确认 CGNAT，避免将普通家庭路由 NAT 误判为运营商 CGNAT")

        signals["stun_samples"] = len(observations)
        signals["public_ipv4"] = public_ipv4 or ""
        signals["mapped_ipv4"] = mapped_ipv4 or ""
        return CGNATResult(
            is_cgnat=is_cgnat,
            confidence=round(confidence, 4),
            reasons=reasons,
            verdict=verdict,
            signals=signals,
        )

    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("223.5.5.5", 53))
                return sock.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _get_public_ip(self) -> str | None:
        candidates: list[str] = []
        endpoints = (
            ("https://myip.ipip.net", "extract"),
            ("https://api.my-ip.io/v2/ip.json", "json"),
        )
        try:
            with httpx.Client(timeout=4.0, follow_redirects=True, trust_env=False) as client:
                for url, kind in endpoints:
                    try:
                        response = client.get(url)
                        if response.status_code != 200:
                            continue
                        if kind == "json":
                            value = response.json().get("ip")
                        elif kind == "extract":
                            matches = IPV4_PATTERN.findall(response.text)
                            value = matches[0] if matches else None
                        if not value:
                            continue
                        address = ipaddress.ip_address(value)
                        candidates.append(str(address))
                        if address.version == 4:
                            self._public_ipv4 = str(address)
                            return self._public_ipv4
                    except Exception:
                        continue
        except Exception:
            pass
        self._public_ipv4 = self._public_ipv4_from(candidates)
        return candidates[0] if candidates else None

    def _trace_route(self) -> list[str]:
        system = platform.system()
        commands: list[list[str]]
        if system == "Windows":
            commands = [["tracert", "-d", "-h", "8", "-w", "450", "223.5.5.5"]]
        else:
            commands = [
                ["tracepath", "-n", "-m", "8", "223.5.5.5"],
                ["traceroute", "-n", "-m", "8", "-w", "1", "223.5.5.5"],
            ]
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    errors="ignore",
                    timeout=7,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if system == "Windows" else 0,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
            hops: list[str] = []
            for line in result.stdout.splitlines():
                matches = IPV4_PATTERN.findall(line)
                if not matches:
                    continue
                hop = matches[-1]
                if hop not in hops and hop != "223.5.5.5":
                    hops.append(hop)
            if hops:
                return hops
        return []

    def _get_router_wan_ip(self) -> str | None:
        """Read the home router WAN address through UPnP when the router exposes it."""
        search_targets = (
            "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
            "urn:schemas-upnp-org:service:WANIPConnection:1",
            "urn:schemas-upnp-org:service:WANPPPConnection:1",
        )
        locations: list[str] = []
        for target in search_targets:
            request = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: 239.255.255.250:1900\r\n"
                'MAN: "ssdp:discover"\r\n'
                "MX: 1\r\n"
                f"ST: {target}\r\n\r\n"
            ).encode("ascii")
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                    sock.settimeout(0.8)
                    sock.sendto(request, ("239.255.255.250", 1900))
                    while True:
                        try:
                            payload = sock.recvfrom(65535)[0].decode("utf-8", errors="ignore")
                        except TimeoutError:
                            break
                        for line in payload.splitlines():
                            if line.lower().startswith("location:"):
                                location = line.split(":", 1)[1].strip()
                                if location and location not in locations:
                                    locations.append(location)
            except OSError:
                continue
            if locations:
                break

        for location in locations[:3]:
            try:
                with httpx.Client(timeout=2.0, follow_redirects=True, trust_env=False) as client:
                    description = client.get(location)
                    description.raise_for_status()
                    root = ET.fromstring(description.content)
                    for service in root.iter():
                        if not service.tag.endswith("service"):
                            continue
                        service_type = ""
                        control_url = ""
                        for child in service:
                            if child.tag.endswith("serviceType"):
                                service_type = child.text or ""
                            elif child.tag.endswith("controlURL"):
                                control_url = child.text or ""
                        if (
                            "WANIPConnection" not in service_type
                            and "WANPPPConnection" not in service_type
                        ):
                            continue
                        if not control_url:
                            continue
                        soap_body = (
                            '<?xml version="1.0"?>'
                            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
                            "<s:Body>"
                            f'<u:GetExternalIPAddress xmlns:u="{service_type}">'
                            "</u:GetExternalIPAddress>"
                            "</s:Body></s:Envelope>"
                        )
                        response = client.post(
                            urljoin(location, control_url),
                            content=soap_body.encode("utf-8"),
                            headers={
                                "Content-Type": 'text/xml; charset="utf-8"',
                                "SOAPAction": f'"{service_type}#GetExternalIPAddress"',
                            },
                        )
                        if response.status_code >= 400:
                            continue
                        body = ET.fromstring(response.content)
                        for node in body.iter():
                            if node.tag.endswith("NewExternalIPAddress") and node.text:
                                value = node.text.strip()
                                if ipaddress.ip_address(value).version == 4:
                                    return value
            except (httpx.HTTPError, ET.ParseError, ValueError, OSError):
                continue
        return None

    def _collect_stun_observations(self, source_ip: str) -> list[StunObservation]:
        observations: list[StunObservation] = []
        deadline = time.monotonic() + 8.0
        # Prefer mainland-accessible servers before global servers.
        servers = sorted(
            self._stun_servers,
            key=lambda value: (
                0
                if any(
                    name in value
                    for name in ("qq.com", "miwifi.com", "bilibili.com", "163.com", "jd.com")
                )
                else 1
            ),
        )
        for stun_server in servers[:8]:
            if time.monotonic() >= deadline:
                break
            if ":" not in stun_server:
                continue
            host, port_text = stun_server.rsplit(":", 1)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.settimeout(2.5)
                    sock.bind((source_ip, 0))
                    nat_type, result = stun.get_nat_type(
                        s=sock,
                        source_ip=source_ip,
                        source_port=sock.getsockname()[1],
                        stun_host=host,
                        stun_port=int(port_text),
                    )
                external_ip = result.get("external_ip") or result.get("ExternalIP")
                external_port = result.get("external_port") or result.get("ExternalPort")
                if isinstance(external_ip, tuple):
                    external_ip, external_port = external_ip[0], external_ip[1]
                if not external_ip:
                    continue
                observations.append(
                    StunObservation(
                        server=stun_server,
                        nat_type=str(nat_type or "Unknown"),
                        external_ip=str(external_ip),
                        external_port=int(external_port) if external_port else None,
                    )
                )
                if len(observations) >= 3:
                    break
            except Exception:
                continue
        return observations

    def _check_network(self) -> NetworkInfo | None:
        source_ip = self._get_local_ip()
        observations = self._collect_stun_observations(source_ip)
        router_wan_ip = self._get_router_wan_ip()
        route_hops = self._trace_route()
        public_ipv4 = self._public_ipv4 or self._public_ipv4_from(
            [self._system_info.public_ip if self._system_info else None]
        )
        cgnat = self._check_cgnat(observations, public_ipv4, route_hops, router_wan_ip)
        if not observations:
            return NetworkInfo(
                nat_type="Unknown",
                cgnat=cgnat,
                route_hops=route_hops,
                router_wan_ip=router_wan_ip,
            )
        primary = observations[0]
        return NetworkInfo(
            nat_type=primary.nat_type,
            mapped_address=primary.external_ip,
            mapped_port=primary.external_port,
            external_ip=primary.external_ip,
            cgnat=cgnat,
            stun_server=primary.server,
            stun_observations=[
                {
                    "server": item.server,
                    "nat_type": item.nat_type,
                    "external_ip": item.external_ip,
                    "external_port": item.external_port,
                }
                for item in observations
            ],
            route_hops=route_hops,
            router_wan_ip=router_wan_ip,
        )

    def check(self, include_public_ip: bool = True, check_network: bool = True) -> SystemInfo:
        self._system_info = SystemInfo(
            system=platform.system(),
            system_version=platform.version(),
            arch=platform.machine(),
            processor=platform.processor(),
            ip_address=self._get_local_ip(),
        )
        if include_public_ip:
            self._system_info.public_ip = self._get_public_ip()
        if check_network:
            self._system_info.network_info = self._check_network()
        return self._system_info

    def get_system_info(self) -> SystemInfo | None:
        return self._system_info

    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def is_linux() -> bool:
        return platform.system() == "Linux"
