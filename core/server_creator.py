import os
import platform
import sys
from urllib.parse import urlencode

import httpx

from .config import ConfigKey
from .source import SourceManager
from .workspace import ServerType, WorkspaceManager


def create_server_flow(
    task,
    server_uuid: str,
    workspace: WorkspaceManager,
    server_type: ServerType,
    java_version: str = "21",
    version: str = "",
    mc_version: str = "",
) -> dict:
    """
    Multi-step server creation flow for CompositeTask.

    Steps:
    1. Check/install Java
    2. Download server.jar
    3. Write eula.txt
    """
    server = workspace.get_server_by_uuid(server_uuid)
    if not server:
        raise ValueError(f"Server {server_uuid} not found")

    source_mgr = SourceManager()
    source = source_mgr.get()

    # Step 1: Ensure Java is installed
    task.set_step("java", f"Prepare Java {java_version}")
    task.set_progress(5, f"Checking Java {java_version}…")

    java_dir = os.path.join(
        sys._MEIPASS  # type: ignore
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.dirname(__file__)),
        "java",
    )
    os.makedirs(java_dir, exist_ok=True)

    java_binary = _find_java_binary(java_version, java_dir)
    if not java_binary:
        if not ConfigKey.SERVER_JAVA_AUTO_DOWNLOAD.get():
            raise RuntimeError(
                f"Java {java_version} is not installed and auto_download is disabled"
            )
        task.set_progress(10, f"Downloading Java {java_version}…")
        java_binary = _download_java(java_version, java_dir, source, task)
        task.set_progress(50, f"Java {java_version} installed")
    else:
        task.set_progress(30, f"Java {java_version} already installed")
    task.complete_step("java")

    # Step 2: Download server.jar / installer
    needs_installer = server_type in (ServerType.FORGE, ServerType.NEOFORGE)
    if needs_installer:
        installer_name = (
            "forge-installer.jar" if server_type == ServerType.FORGE else "neoforge-installer.jar"
        )
        installer_path = os.path.join(server.path, installer_name)
        server_jar_path = os.path.join(server.path, "server.jar")
    else:
        installer_name = None
        installer_path = os.path.join(server.path, "server.jar")
        server_jar_path = installer_path

    task.set_step("server-download", f"Download {server_type.value} {version or 'server'}")
    task.set_progress(40, f"Downloading {server_type.value} server…")
    if server_type == ServerType.FORGE:
        candidates = _forge_installer_candidates(version, source)
        if not candidates:
            raise RuntimeError(f"Could not resolve a Forge installer for {version}")
        _download_first_available(candidates, installer_path, task, start=40, end=60)
    else:
        download_url = _resolve_jar_url(server_type, version, source)
        if not download_url:
            raise RuntimeError(f"Could not resolve download URL for {server_type.value}")
        _download_file(download_url, installer_path, task, start=40, end=60)
    task.complete_step("server-download")

    if needs_installer:
        task.set_step("installer", f"Install {server_type.value}")
        _run_installer(java_binary, installer_name, server.path, task)
        # Clean up installer jar
        if os.path.exists(installer_path):
            os.remove(installer_path)
        task.complete_step("installer")

    # Step 3: Write eula.txt
    task.set_step("finalize", "Accept EULA and save metadata")
    task.set_progress(90, "Accepting EULA and saving metadata…")
    eula_path = os.path.join(server.path, "eula.txt")
    with open(eula_path, "w") as f:
        f.write("eula=true")

    # Update metadata with resolved version
    meta_file = os.path.join(server.path, ".hslmeta")
    if os.path.exists(meta_file):
        import yaml

        with open(meta_file, encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        meta["java_binary"] = java_binary

        # Parse version for Forge/NeoForge: "mc_version|forge_version" or "mc_version"
        if "|" in version:
            parts = version.split("|", 1)
            meta["mc_version"] = parts[0]
            if server_type == ServerType.FORGE:
                meta["forge_version"] = parts[1]
            elif server_type == ServerType.NEOFORGE:
                meta["neoforge_version"] = parts[1]
        else:
            if mc_version or version:
                meta["mc_version"] = mc_version or version
            if server_type == ServerType.FORGE:
                meta["forge_version"] = version
            elif server_type == ServerType.NEOFORGE:
                meta["neoforge_version"] = version

        with open(meta_file, "w", encoding="utf-8") as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    task.complete_step("finalize")
    task.set_progress(100, "Server is ready")
    return {
        "server_uuid": server_uuid,
        "server_type": server_type.value,
        "java_version": java_version,
        "java_binary": java_binary,
        "jar_path": server_jar_path,
    }


def _find_java_binary(version: str, java_dir: str) -> str | None:
    version_dir = os.path.join(java_dir, version)
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


def _download_java(version: str, java_dir: str, source, task) -> str:
    import tempfile
    import zipfile

    java_source = None
    for item in source.java.list:
        if version in item.windows or version in item.linux:
            java_source = item
            break

    if not java_source:
        raise RuntimeError(f"No download source found for Java {version}")

    if platform.system() == "Windows":
        download_url = java_source.windows.get(version)
    else:
        download_url = java_source.linux.get(version)

    if not download_url:
        raise RuntimeError(f"No download URL for Java {version}")

    version_dir = os.path.join(java_dir, version)
    os.makedirs(version_dir, exist_ok=True)

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(tmp_fd)

        with (
            httpx.Client(timeout=httpx.Timeout(600.0, connect=60.0)) as client,
            client.stream("GET", download_url, follow_redirects=True) as response,
        ):
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = 10 + (downloaded / total) * 30
                        task.set_progress(pct, f"Downloading Java {version}...")

        task.set_progress(42, f"Extracting Java {version}...")
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(version_dir)

        binary = _find_java_binary(version, java_dir)
        if not binary:
            raise RuntimeError(f"Java {version} downloaded but binary not found after extraction")

        if platform.system() != "Windows":
            for root, dirs, files in os.walk(version_dir):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o755)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o755)

        return binary
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _resolve_jar_url(server_type: ServerType, version: str, source) -> str | None:
    if server_type == ServerType.VANILLA:
        return _resolve_vanilla_url(version, source)
    elif server_type == ServerType.PAPER:
        return _resolve_paper_url(version, source)
    elif server_type == ServerType.FABRIC:
        return _resolve_fabric_url(version, source)
    elif server_type == ServerType.FORGE:
        return _resolve_forge_installer_url(version, source)
    elif server_type == ServerType.NEOFORGE:
        return _resolve_neoforge_installer_url(version, source)
    elif server_type == ServerType.APRIL:
        return _resolve_april_url(version, source)
    return None


def _resolve_vanilla_url(version: str, source) -> str | None:
    for vs in source.mc.vanilla.list:
        if vs.type == "bmclapi":
            try:
                resp = httpx.get(vs.server.format(version=version), follow_redirects=True)
                if resp.status_code == 200:
                    return str(resp.url)
            except Exception:
                pass
    return None


def _resolve_paper_url(version: str, source) -> str | None:
    if version.startswith("https://"):
        return version
    # Fallback: try source.json static URL
    for ps in source.mc.paper.list:
        if ps.type == "stable":
            return ps.latest
    return None


def _resolve_fabric_url(version: str, source) -> str | None:
    if not version:
        # get latest stable
        try:
            resp = httpx.get(
                "https://meta.fabricmc.net/v2/versions/game",
                follow_redirects=True,
            )
            if resp.status_code == 200:
                versions = resp.json()
                stable = [v for v in versions if v.get("stable")]
                if stable:
                    version = stable[0]["version"]
        except Exception:
            pass

    try:
        loader_resp = httpx.get(
            "https://meta.fabricmc.net/v2/versions/loader",
            follow_redirects=True,
        )
        if loader_resp.status_code != 200:
            return None
        loader_list = loader_resp.json()
        if not loader_list:
            return None
        loader_version = loader_list[0]["version"]
    except Exception:
        return None

    for fs in source.fabric.list:
        if fs.type == "official":
            return fs.installer.replace("{version}", version).replace("{loader}", loader_version)
    return None


def _resolve_forge_installer_url(version: str, source) -> str | None:
    candidates = _forge_installer_candidates(version, source)
    return candidates[0] if candidates else None


def _forge_installer_candidates(version: str, source) -> list[str]:
    """Build mirror and official Forge installer URLs like the original launcher."""
    if not version:
        return []

    # version format: "mc_version" or "mc_version|forge_version"
    if "|" in version:
        mc_ver, fg_ver_raw = version.split("|", 1)
        # fg_ver_raw may already contain mc_version prefix like "1.21.4-52.0.27"
        # Strip the mc_ver prefix if present
        if fg_ver_raw.startswith(mc_ver + "-"):
            fg_ver = fg_ver_raw[len(mc_ver) + 1 :]
        else:
            fg_ver = fg_ver_raw
    else:
        mc_ver = version
        fg_ver = ""
        # Auto-resolve latest forge version
        try:
            resp = httpx.get(
                f"https://bmclapi2.bangbang93.com/forge/minecraft/{version}",
                follow_redirects=True,
            )
            if resp.status_code == 200:
                builds = resp.json()
                if builds:
                    installable = [
                        build
                        for build in builds
                        if any(
                            item.get("category") == "installer"
                            and item.get("format") == "jar"
                            for item in (build.get("files") or [])
                        )
                    ]
                    if not installable:
                        return []
                    latest = sorted(
                        installable, key=lambda b: b.get("build", 0), reverse=True
                    )[0]
                    forge_version = latest.get("version", "")
                    if "-" in forge_version:
                        parts = forge_version.split("-", 1)
                        mc_ver, fg_ver = parts[0], parts[1]
                    else:
                        fg_ver = forge_version
        except Exception:
            pass

    if not fg_ver:
        return []

    full_version = f"{mc_ver}-{fg_ver}"
    candidates: list[str] = []

    # The original implementation sends these four query parameters to BMCLAPI.
    for fs in source.forge.list:
        if fs.type == "bmclapi" and fs.download:
            params = {
                "mcversion": mc_ver,
                "version": fg_ver,
                "category": "installer",
                "format": "jar",
            }
            candidates.append(f"{fs.download}?{urlencode(params)}")

    # Keep both the configured official endpoint and the canonical Maven endpoint.
    for fs in source.forge.list:
        if fs.type == "official" and fs.download:
            candidates.append(
                f"{fs.download.rstrip('/')}/{full_version}/"
                f"forge-{full_version}-installer.jar"
            )
    candidates.append(
        f"https://maven.minecraftforge.net/net/minecraftforge/forge/"
        f"{full_version}/forge-{full_version}-installer.jar"
    )

    return list(dict.fromkeys(candidates))


def _resolve_neoforge_installer_url(version: str, source) -> str | None:
    if not version:
        return None

    # version format: "mc_version" or "mc_version|neoforge_version"
    if "|" in version:
        parts = version.split("|", 1)
        url_version = f"{parts[0]}-{parts[1]}"
    else:
        url_version = version

    for ns in source.neoforge.list:
        if ns.type == "official":
            return ns.download.replace("{version}", url_version)
    return None


def _resolve_april_url(version: str, source) -> str | None:
    for av in source.mc.april.list:
        if av.version == version or av.name == version:
            return av.link
    if source.mc.april.list:
        return source.mc.april.list[0].link
    return None


def _run_installer(
    java_binary: str,
    installer_jar_name: str | None,
    server_path: str,
    task,
) -> None:
    """Run a Forge/NeoForge installer subprocess, streaming stdout to task progress."""
    import subprocess

    if installer_jar_name is None:
        return

    cmd = [java_binary, "-jar", installer_jar_name, "--installServer"]
    task.set_progress(60, "Running installer...")

    process = subprocess.Popen(
        cmd,
        cwd=server_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    last_progress = 60.0
    if process.stdout is not None:
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            last_progress = min(last_progress + 0.3, 85)
            task.set_progress(last_progress, f"Installer: {line[:80]}")
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Installer failed (exit code: {process.returncode})")

    # Modern Forge emits run scripts/args files; legacy Forge emits a launch JAR.
    produced_runtime = any(
        os.path.exists(os.path.join(server_path, name))
        for name in ("run.bat", "run.sh", "user_jvm_args.txt")
    ) or any(
        name.startswith("forge-")
        and name.endswith(".jar")
        and name != installer_jar_name
        for name in os.listdir(server_path)
    )
    if not produced_runtime:
        raise RuntimeError("Forge installer exited successfully but produced no server runtime")

    task.set_progress(85, "Installer completed successfully")


def _download_file(
    url: str,
    destination: str,
    task,
    start: float = 0,
    end: float = 100,
):
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)

    with (
        httpx.Client(timeout=httpx.Timeout(300.0, connect=60.0)) as client,
        client.stream("GET", url, follow_redirects=True) as response,
    ):
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        started_at = __import__("time").monotonic()
        last_report_at = started_at
        with open(destination, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                now = __import__("time").monotonic()
                if total:
                    pct = start + (downloaded / total) * (end - start)
                    elapsed = max(now - started_at, 0.001)
                    speed = downloaded / elapsed
                    remaining = (total - downloaded) / speed if speed else None
                    task.set_metrics(
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                        speed_bps=round(speed),
                        eta_seconds=round(remaining) if remaining is not None else None,
                    )
                    if now - last_report_at > 0.2 or downloaded == total:
                        task.set_progress(pct, "Downloading server files…")
                        last_report_at = now

    return destination


def _download_first_available(
    urls: list[str],
    destination: str,
    task,
    start: float = 0,
    end: float = 100,
) -> str:
    errors: list[str] = []
    for index, url in enumerate(urls, start=1):
        try:
            task.set_progress(start, f"Trying Forge download source {index}/{len(urls)}")
            _download_file(url, destination, task, start=start, end=end)
            with open(destination, "rb") as installer:
                if installer.read(4) != b"PK\x03\x04":
                    raise ValueError("downloaded response is not a valid installer JAR")
            return destination
        except (httpx.HTTPError, OSError, ValueError) as error:
            errors.append(f"{url}: {error}")
            if os.path.exists(destination):
                os.remove(destination)
    raise RuntimeError("All Forge installer sources failed: " + " | ".join(errors))
