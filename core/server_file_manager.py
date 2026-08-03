"""Server file management — browse, create, edit, delete files in a server directory.

All paths are resolved relative to the server's root directory.
Path traversal outside the server root is blocked.
"""

import mimetypes
import os
import shutil
from datetime import datetime
from typing import Any, BinaryIO


class PathTraversalError(Exception):
    pass


def _safe_path(server_path: str, relative_path: str) -> str:
    """Resolve a relative path within the server directory.

    Blocks path traversal (e.g. '../../../etc/passwd').
    """
    if not isinstance(relative_path, str) or "\x00" in relative_path:
        raise PathTraversalError("Invalid path")
    root = os.path.realpath(os.path.abspath(server_path))
    cleaned = relative_path.replace("\\", "/").lstrip("/")
    resolved = os.path.realpath(os.path.abspath(os.path.join(root, cleaned)))
    try:
        inside_root = os.path.commonpath((root, resolved)) == root
    except ValueError:
        inside_root = False
    if not inside_root:
        raise PathTraversalError(f"Path traversal blocked: {relative_path}")

    return resolved


def _file_info(abs_path: str, server_path: str) -> dict[str, Any]:
    """Get metadata for a file or directory."""
    stat = os.stat(abs_path)
    rel_path = os.path.relpath(abs_path, server_path).replace("\\", "/")
    return {
        "name": os.path.basename(abs_path),
        "path": rel_path,
        "type": "directory" if os.path.isdir(abs_path) else "file",
        "size": stat.st_size if os.path.isfile(abs_path) else 0,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def list_directory(server_path: str, relative_path: str = "") -> dict[str, Any]:
    """List contents of a directory within the server."""
    try:
        target = _safe_path(server_path, relative_path) if relative_path else server_path
    except PathTraversalError as e:
        return {"error": str(e)}

    if not os.path.exists(target):
        return {"error": f"Path not found: {relative_path}"}
    if not os.path.isdir(target):
        return {"error": f"Not a directory: {relative_path}"}

    items = []
    try:
        for entry in sorted(os.listdir(target)):
            abs_entry = os.path.join(target, entry)
            items.append(_file_info(abs_entry, server_path))
    except PermissionError:
        return {"error": "Permission denied"}

    current_rel = os.path.relpath(target, server_path).replace("\\", "/")
    if current_rel == ".":
        current_rel = ""

    return {
        "path": current_rel,
        "items": items,
    }


def read_file(server_path: str, relative_path: str) -> dict[str, Any]:
    """Read file contents. Returns raw text."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return {"error": str(e)}

    if not os.path.exists(target):
        return {"error": f"File not found: {relative_path}"}
    if os.path.isdir(target):
        return {"error": f"Cannot read directory as file: {relative_path}"}

    try:
        with open(target, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return {"error": str(e)}

    info = _file_info(target, server_path)
    info["content"] = content
    return info


def write_file(server_path: str, relative_path: str, content: str) -> dict[str, Any]:
    """Write complete file contents. Creates parent directories if needed."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return {"error": str(e)}

    # Don't allow overwriting the .hslmeta file
    if os.path.basename(target) == ".hslmeta":
        return {"error": "Cannot edit server metadata file"}

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return {"error": str(e)}

    return _file_info(target, server_path)


def create_file(server_path: str, relative_path: str, content: str = "") -> dict[str, Any]:
    """Create a new file."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return {"error": str(e)}

    if os.path.exists(target):
        return {"error": f"Already exists: {relative_path}"}

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return {"error": str(e)}

    return _file_info(target, server_path)


def delete_file(server_path: str, relative_path: str) -> dict[str, Any]:
    """Delete a file."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return {"error": str(e)}

    if os.path.basename(target) == ".hslmeta":
        return {"error": "Cannot delete server metadata file"}

    if not os.path.exists(target):
        return {"error": f"Not found: {relative_path}"}
    if os.path.isdir(target):
        return {"error": "Use /api/servers/<uuid>/folders to delete directories"}

    try:
        os.remove(target)
    except Exception as e:
        return {"error": str(e)}

    return {"success": True, "path": relative_path}


def create_folder(server_path: str, relative_path: str) -> dict[str, Any]:
    """Create a new directory."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return {"error": str(e)}

    if os.path.exists(target):
        return {"error": f"Already exists: {relative_path}"}

    try:
        os.makedirs(target, exist_ok=True)
    except Exception as e:
        return {"error": str(e)}

    return _file_info(target, server_path)


def delete_folder(server_path: str, relative_path: str, recursive: bool = False) -> dict[str, Any]:
    """Delete a directory. Must be empty unless recursive=True."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return {"error": str(e)}

    if not os.path.exists(target):
        return {"error": f"Not found: {relative_path}"}
    if not os.path.isdir(target):
        return {"error": f"Not a directory: {relative_path}"}

    # Safety: refuse to delete the server root
    if os.path.normpath(target) == os.path.normpath(server_path):
        return {"error": "Cannot delete server root directory"}

    try:
        if recursive:
            shutil.rmtree(target)
        else:
            os.rmdir(target)  # Will fail if not empty
    except OSError as e:
        if not recursive and "directory not empty" in str(e).lower():
            return {"error": "Directory not empty. Use recursive=true to delete recursively"}
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

    return {"success": True, "path": relative_path}


def upload_file(
    server_path: str, relative_path: str, file_data: bytes, filename: str
) -> dict[str, Any]:
    """Save an uploaded file to the server directory."""
    from io import BytesIO

    return upload_stream(server_path, relative_path, BytesIO(file_data), filename)


def upload_stream(
    server_path: str, relative_path: str, stream: BinaryIO, filename: str
) -> dict[str, Any]:
    """Stream an upload to disk while enforcing the server root boundary."""
    if not filename or filename in {".", ".."}:
        return {"error": "Invalid filename"}
    if os.path.basename(filename) != filename or "/" in filename or "\\" in filename:
        return {"error": "Invalid filename"}
    try:
        target_dir = _safe_path(server_path, relative_path or "")
        target_file = _safe_path(server_path, os.path.join(relative_path, filename))
    except PathTraversalError as e:
        return {"error": str(e)}

    if filename.casefold() == ".hslmeta":
        return {"error": "Cannot overwrite server metadata file"}

    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(target_file, "wb") as output:
            shutil.copyfileobj(stream, output, length=1024 * 1024)
    except Exception as e:
        return {"error": str(e)}
    return _file_info(target_file, server_path)


def download_file(server_path: str, relative_path: str):
    """Resolve a file for streaming. Returns (error, path, mimetype) tuple."""
    try:
        target = _safe_path(server_path, relative_path)
    except PathTraversalError as e:
        return str(e), None, None

    if not os.path.exists(target):
        return f"File not found: {relative_path}", None, None
    if os.path.isdir(target):
        return f"Cannot download a directory: {relative_path}", None, None

    mime_type, _ = mimetypes.guess_type(relative_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    return None, target, mime_type
