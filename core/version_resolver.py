"""Version resolver for Minecraft server types.

Fetches available versions from official and mirror sources.
The `use_mirror` parameter reverses source list order (mirror-first).
"""

import platform
from typing import Any

import httpx

from .source import SourceManager


def _http_get(url: str, **kwargs) -> httpx.Response | None:
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp = client.get(url, follow_redirects=True, **kwargs)
            if resp.status_code == 200:
                return resp
    except Exception:
        pass
    return None


def _http_post_json(url: str, json_data: dict) -> httpx.Response | None:
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp = client.post(url, json=json_data, follow_redirects=True)
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


def get_vanilla_versions(use_mirror: bool = False) -> dict[str, Any]:
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
                    for v in all_versions
                    if v.get("type") == "release"
                ]
                snapshots = [
                    {"id": v["id"], "type": v["type"], "release_time": v.get("releaseTime", "")}
                    for v in all_versions
                    if v.get("type") == "snapshot"
                ]
                break

    return {
        "releases": releases,
        "snapshots": snapshots,
        "source_type": sources[0].type if sources else "unknown",
    }


# ── Paper (GraphQL) ─────────────────────────────────────────────────

PAPER_GRAPHQL_URL = "https://fill.papermc.io/graphql"

PAPER_FAMILIES_QUERY = """
query ProjectFamilies($id: String!) {
  project(key: $id) {
    id
    families { id key __typename }
    __typename
  }
}
"""

PAPER_FAMILY_QUERY = """
query Family($project: String!, $id: String!) {
  project(key: $project) {
    id
    family(key: $id) {
      id key
      java {
        version { minimum __typename }
        flags { recommended __typename }
        __typename
      }
      __typename
    }
    versions(filterBy: {familyKey: $id}, first: 100, orderBy: {direction: DESC}) {
      edges {
        node {
          id key
          family { id key __typename }
          support { status end __typename }
          __typename
        }
        __typename
      }
      pageInfo { hasNextPage endCursor __typename }
      __typename
    }
    __typename
  }
}
"""

PAPER_BUILDS_QUERY = """
query VersionBuilds($projectKey: String!, $versionKey: String!, $after: String) {
  project(key: $projectKey) {
    id
    version(key: $versionKey) {
      id
      builds(first: 25, after: $after, orderBy: {direction: DESC}) {
        edges {
          node {
            id number channel createdAt
            downloads {
              name size url
              checksums { sha256 __typename }
              __typename
            }
            commits { sha message __typename }
            __typename
          }
          __typename
        }
        pageInfo { hasNextPage hasPreviousPage startCursor endCursor __typename }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""


def _paper_graphql(query: str, variables: dict) -> dict | None:
    """Execute a GraphQL query against the PaperMC fill API."""
    try:
        payload = {"operationName": None, "query": query, "variables": variables}
        resp = _http_post_json(PAPER_GRAPHQL_URL, payload)
        if resp and resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def get_paper_versions(mc_version: str | None = None) -> dict[str, Any]:
    """Get PaperMC version families and sub-versions using GraphQL.

    Without mc_version: returns all families as versions list.
    With mc_version: returns sub-versions for that family plus Java requirements.
    """
    if mc_version:
        # Return sub-versions for a specific family
        sub_data = _paper_graphql(
            PAPER_FAMILY_QUERY,
            {"project": "paper", "id": mc_version},
        )
        sub_versions = []
        java_min = 0
        recommended_flags = []

        if sub_data:
            sub_project = sub_data.get("data", {}).get("project", {})
            sub_family = sub_project.get("family", {})
            java_info = sub_family.get("java", {})
            java_min = java_info.get("version", {}).get("minimum", 0) or 0
            recommended_flags = java_info.get("flags", {}).get("recommended", []) or []

            versions_data = sub_project.get("versions", {})
            for edge in versions_data.get("edges", []):
                node = edge.get("node", {})
                sub_versions.append(
                    {
                        "id": node.get("id", ""),
                        "key": node.get("key", ""),
                        "support_status": node.get("support", {}).get("status", ""),
                        "support_end": node.get("support", {}).get("end"),
                    }
                )

        return {
            "mc_version": mc_version,
            "sub_versions": sub_versions,
            "java_minimum": java_min,
            "recommended_flags": recommended_flags,
        }

    # Without mc_version: return all families as version list
    families_data = _paper_graphql(PAPER_FAMILIES_QUERY, {"id": "paper"})
    versions = []

    if families_data:
        project = families_data.get("data", {}).get("project", {})
        raw_families = project.get("families", [])

        for fam in raw_families:
            versions.append(
                {
                    "id": fam.get("key", ""),
                    "type": "release",
                    "release_time": "",
                }
            )

    return {
        "releases": versions,
        "project": "paper",
    }


def get_paper_builds(sub_version: str) -> dict[str, Any]:
    """Get PaperMC builds for a specific sub-version using GraphQL.

    Returns builds with download URLs, channel info, and creation dates.
    """
    data = _paper_graphql(
        PAPER_BUILDS_QUERY,
        {"projectKey": "paper", "versionKey": sub_version},
    )
    builds = []

    if data:
        project = data.get("data", {}).get("project", {})
        version_data = project.get("version", {})
        builds_data = version_data.get("builds", {})

        for edge in builds_data.get("edges", []):
            node = edge.get("node", {})
            downloads = node.get("downloads", [])
            download_url = downloads[0].get("url", "") if downloads else ""
            download_name = downloads[0].get("name", "") if downloads else ""
            sha256 = ""
            if downloads:
                checksums = downloads[0].get("checksums", {})
                sha256 = checksums.get("sha256", "")

            builds.append(
                {
                    "number": node.get("number", 0),
                    "channel": node.get("channel", "default"),
                    "created_at": node.get("createdAt", ""),
                    "download_url": download_url,
                    "download_name": download_name,
                    "sha256": sha256,
                }
            )

    return {
        "sub_version": sub_version,
        "builds": builds,
    }


# ── April (愚人节) ───────────────────────────────────────────────


def get_april_versions() -> dict[str, Any]:
    """Get April Fools Minecraft server versions."""
    source = SourceManager().get()
    versions = []
    for av in source.mc.april.list:
        versions.append(
            {
                "name": av.name,
                "version": av.version,
                "download_url": av.link,
            }
        )
    return {"versions": versions}


# ── Forge ────────────────────────────────────────────────────────


def get_forge_versions(mc_version: str | None = None, use_mirror: bool = False) -> dict[str, Any]:
    """Get Forge versions.

    If mc_version is provided, returns forge versions for that MC version.
    Otherwise returns supported MC versions list.
    """
    source = SourceManager().get()
    sources = _ordered_sources(source.forge.list, use_mirror)

    result: dict[str, Any] = {
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
                        # Match the original launcher: a Forge build is installable only
                        # when its metadata explicitly contains an installer JAR.
                        files = b.get("files") or []
                        has_installer = any(
                            item.get("category") == "installer"
                            and item.get("format") == "jar"
                            for item in files
                        )
                        if not has_installer:
                            continue
                        result["forge_versions"].append(
                            {
                                "version": b.get("version", ""),
                                "build": b.get("build", 0),
                                "mc_version": b.get("mcversion", mc_version),
                                "installer_url": fs.download
                                if fs.download and "download" in dir(fs)
                                else None,
                            }
                        )
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


def get_neoforge_versions(
    mc_version: str | None = None, use_mirror: bool = False
) -> dict[str, Any]:
    """Get NeoForge versions."""
    source = SourceManager().get()
    sources = _ordered_sources(source.neoforge.list, use_mirror)

    result: dict[str, Any] = {
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


def get_fabric_versions(use_mirror: bool = False) -> dict[str, Any]:
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
                    {"version": v["version"], "stable": v.get("stable", True)} for v in stable
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


def get_recommended_java_version(mc_version: str) -> str:
    """Return recommended Java major version for a Minecraft version string.

    Mapping:
      MC 1.x  (x <= 16)   -> Java 8
      MC 1.17 - 1.19.x    -> Java 17
      MC 1.20 - 1.26.0    -> Java 21
      MC 1.26.1+ / 2.x+   -> Java 25
    """
    try:
        parts = mc_version.split(".")
        major = int(parts[0])
        if major == 1:
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            if minor <= 16:
                return "8"
            elif minor <= 19:
                return "17"
            elif minor <= 25 or minor == 26 and patch == 0:
                return "21"
            else:
                return "25"
        else:
            return "25"
    except (ValueError, IndexError):
        pass
    return "21"


def get_java_versions(use_mirror: bool = False) -> dict[str, Any]:
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
            versions.append(
                {
                    "version": ver,
                    "source": js.type,
                    "source_label": "mirror" if js.type == "lingyi" else "normal",
                    "download_url": url,
                    "os": os_key,
                }
            )

    return {
        "os": os_key,
        "versions": versions,
    }
