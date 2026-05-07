"""Version resolver for Minecraft server types.

Fetches available versions from official and mirror sources.
The `use_mirror` parameter reverses source list order (mirror-first).
"""

import platform
from typing import Any, Dict, List, Optional

import httpx

from .source import SourceManager


def _http_get(url: str, **kwargs) -> Optional[httpx.Response]:
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp = client.get(url, follow_redirects=True, **kwargs)
            if resp.status_code == 200:
                return resp
    except Exception:
        pass
    return None


def _ordered_sources(sources: list, use_mirror: bool) -> list:
    """Return sources in normal or mirror-first order."""
    if use_mirror:
        return list(reversed(sources))
    return list(sources)


# ── Vanilla ──────────────────────────────────────────────────────


def get_vanilla_versions(use_mirror: bool = False) -> Dict[str, Any]:
    """Fetch vanilla Minecraft version manifest.

    Returns all versions and also a filtered list of release versions.
    """
    source = SourceManager().get()
    sources = _ordered_sources(source.mc.vanilla.list, use_mirror)

    all_versions = []
    releases = []
    snapshots = []

    for vs in sources:
        if vs.type == "bmclapi":
            resp = _http_get(vs.versionList)
            if resp:
                data = resp.json()
                all_versions = data.get("versions", [])
                releases = [
                    {"id": v["id"], "type": v["type"], "release_time": v.get("releaseTime", "")}
                    for v in all_versions if v.get("type") == "release"
                ]
                snapshots = [
                    {"id": v["id"], "type": v["type"], "release_time": v.get("releaseTime", "")}
                    for v in all_versions if v.get("type") == "snapshot"
                ]
                break

    return {
        "releases": releases,
        "snapshots": snapshots,
        "source_type": sources[0].type if sources else "unknown",
    }


# ── Paper ────────────────────────────────────────────────────────


def get_paper_versions() -> Dict[str, Any]:
    """Get PaperMC latest version info.

    Returns stable and experimental version names and download URLs.
    """
    source = SourceManager().get()
    paper = source.mc.paper

    stable_info = None
    experimental_info = None

    for ps in paper.list:
        if ps.type == "stable" and not stable_info:
            stable_info = {
                "version": paper.latestVersionName,
                "download_url": ps.latest,
            }
        elif ps.type == "experimental" and not experimental_info:
            experimental_info = {
                "version": paper.experimentalVersionName,
                "download_url": ps.latest,
            }

    # Fetch builds for the latest version from PaperMC API
    builds = []
    try:
        resp = _http_get(
            f"https://api.papermc.io/v2/projects/paper/versions/{paper.latestVersionName}/builds"
        )
        if resp:
            data = resp.json()
            for b in data.get("builds", []):
                builds.append({
                    "build": b.get("build"),
                    "version": b.get("version"),
                    "channel": b.get("channel", "default"),
                })
    except Exception:
        pass

    return {
        "latest_stable": stable_info,
        "latest_experimental": experimental_info,
        "latest_version_builds": builds,
    }


# ── April (愚人节) ───────────────────────────────────────────────


def get_april_versions() -> Dict[str, Any]:
    """Get April Fools Minecraft server versions."""
    source = SourceManager().get()
    versions = []
    for av in source.mc.april.list:
        versions.append({
            "name": av.name,
            "version": av.version,
            "download_url": av.link,
        })
    return {"versions": versions}


# ── Forge ────────────────────────────────────────────────────────


def get_forge_versions(mc_version: Optional[str] = None, use_mirror: bool = False) -> Dict[str, Any]:
    """Get Forge versions.

    If mc_version is provided, returns forge versions for that MC version.
    Otherwise returns supported MC versions list.
    """
    source = SourceManager().get()
    sources = _ordered_sources(source.forge.list, use_mirror)

    result: Dict[str, Any] = {
        "mc_versions": [],
        "forge_versions": [],
    }

    if mc_version:
        result["mc_version"] = mc_version
        for fs in sources:
            if fs.type == "bmclapi" and fs.getByVersion:
                url = fs.getByVersion.replace("{version}", mc_version)
                resp = _http_get(url)
                if resp:
                    data = resp.json()
                    sorted_builds = sorted(data, key=lambda b: b.get("build", 0), reverse=True)
                    for b in sorted_builds:
                        result["forge_versions"].append({
                            "version": b.get("version", ""),
                            "build": b.get("build", 0),
                            "mc_version": b.get("mcversion", mc_version),
                            "installer_url": fs.download
                            if fs.download and "download" in dir(fs)
                            else None,
                        })
                    result["source_type"] = fs.type
                    break
            elif fs.type == "official" and fs.metadata:
                resp = _http_get(fs.metadata)
                if resp:
                    data = resp.json()
                    if mc_version in data:
                        versions = list(data[mc_version])
                        result["forge_versions"] = [
                            {"version": v, "build": 0, "mc_version": mc_version}
                            for v in reversed(versions)
                        ]
                        result["source_type"] = fs.type
                        break
    else:
        for fs in sources:
            if fs.type == "bmclapi" and fs.supportList:
                resp = _http_get(fs.supportList)
                if resp:
                    result["mc_versions"] = resp.json()
                    result["source_type"] = fs.type
                    break
            elif fs.type == "official" and fs.metadata:
                resp = _http_get(fs.metadata)
                if resp:
                    result["mc_versions"] = list(resp.json().keys())
                    result["source_type"] = fs.type
                    break

    return result


# ── NeoForge ─────────────────────────────────────────────────────


def get_neoforge_versions(mc_version: Optional[str] = None, use_mirror: bool = False) -> Dict[str, Any]:
    """Get NeoForge versions."""
    source = SourceManager().get()
    sources = _ordered_sources(source.neoforge.list, use_mirror)

    result: Dict[str, Any] = {
        "mc_versions": [],
        "neoforge_versions": [],
    }

    if mc_version:
        result["mc_version"] = mc_version
        for ns in sources:
            if ns.type == "official" and ns.getByVersion:
                url = ns.getByVersion.replace("{version}", mc_version)
                resp = _http_get(url)
                if resp:
                    data = resp.json()
                    result["neoforge_versions"] = data
                    result["source_type"] = ns.type
                    break
    else:
        # NeoForge doesn't have a direct "list all MC versions" endpoint in source.json.
        # We need to iterate common versions or fetch from the base URL.
        try:
            resp = _http_get("https://bmclapi2.bangbang93.com/neoforge/list")
            if resp:
                result["mc_versions"] = resp.json()
                result["source_type"] = "bmclapi"
        except Exception:
            pass

    return result


# ── Fabric ───────────────────────────────────────────────────────


def get_fabric_versions(use_mirror: bool = False) -> Dict[str, Any]:
    """Get Fabric loader and supported MC versions.

    Fabric only has official source; mirror parameter is accepted for
    API consistency but has no effect.
    """
    source = SourceManager().get()
    sources = _ordered_sources(source.fabric.list, use_mirror)

    mc_versions = []
    loader_versions = []
    latest_loader = ""

    for fs in sources:
        if fs.type == "official":
            # Fetch supported game versions
            resp = _http_get(fs.supportList)
            if resp:
                data = resp.json()
                stable = [v for v in data if v.get("stable")]
                mc_versions = [
                    {"version": v["version"], "stable": v.get("stable", True)}
                    for v in stable
                ]

            # Fetch loader versions
            resp = _http_get(fs.loaderList)
            if resp:
                data = resp.json()
                loader_versions = [v["version"] for v in data]
                if data:
                    latest_loader = data[0]["version"]

            break

    return {
        "mc_versions": mc_versions,
        "loader_versions": loader_versions,
        "latest_loader": latest_loader,
    }


# ── Java ─────────────────────────────────────────────────────────


def get_java_versions(use_mirror: bool = False) -> Dict[str, Any]:
    """Get available Java versions.

    Automatically detects OS (Windows/Linux) and returns appropriate URLs.
    GloryGods = normal source, lingyi = mirror source.
    """
    source = SourceManager().get()
    sources = _ordered_sources(source.java.list, use_mirror)

    is_windows = platform.system() == "Windows"
    os_key = "windows" if is_windows else "linux"

    versions = []
    for js in sources:
        urls = js.windows if is_windows else js.linux
        for ver, url in urls.items():
            versions.append({
                "version": ver,
                "source": js.type,
                "source_label": "mirror" if js.type == "lingyi" else "normal",
                "download_url": url,
                "os": os_key,
            })

    return {
        "os": os_key,
        "versions": versions,
    }
