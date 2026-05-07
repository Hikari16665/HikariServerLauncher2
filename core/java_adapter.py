import os
import platform
import sys
from typing import Dict, Optional

from core import BaseAdapter, Operation, OperationResult, SourceManager


class JavaAdapter(BaseAdapter):
    adapter_name = "java"
    adapter_description = "Java 版本管理适配器"

    def __init__(self):
        self.java_dir = os.path.join(
            sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(__file__)),
            "java"
        )
        os.makedirs(self.java_dir, exist_ok=True)
        super().__init__()

    def _register_operations(self):
        self._operations = {
            "check_version": Operation(
                name="check_version",
                description="检查指定版本的 Java 是否安装",
                parameters={
                    "version": {"type": "str", "required": True, "description": "Java 版本号"}
                },
                _execute_func=_check_version,
                _adapter=self
            ),
            "get_version_binary_path": Operation(
                name="get_version_binary_path",
                description="获取指定版本 Java 的二进制文件路径",
                parameters={
                    "version": {"type": "str", "required": True, "description": "Java 版本号"}
                },
                _execute_func=_get_version_binary_path,
                _adapter=self
            ),
            "download_version": Operation(
                name="download_version",
                description="下载并安装指定版本的 Java",
                parameters={
                    "version": {"type": "str", "required": True, "description": "Java 版本号"}
                },
                _execute_func=_download_version,
                _adapter=self
            ),
            "list_installed_versions": Operation(
                name="list_installed_versions",
                description="列出已安装的所有 Java 版本",
                parameters={},
                _execute_func=_list_installed_versions,
                _adapter=self
            )
        }


def _check_version(adapter: JavaAdapter, version: str) -> OperationResult:
    try:
        version_dir = os.path.join(adapter.java_dir, version)
        if not os.path.exists(version_dir):
            return OperationResult(success=False, data={"installed": False, "version": version})
        
        binary_path = _find_java_binary(adapter, version)
        if binary_path and os.path.exists(binary_path):
            return OperationResult(success=True, data={"installed": True, "version": version, "path": binary_path})
        
        return OperationResult(success=False, data={"installed": False, "version": version, "reason": "Binary not found"})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _get_version_binary_path(adapter: JavaAdapter, version: str) -> OperationResult:
    try:
        binary_path = _find_java_binary(adapter, version)
        if binary_path and os.path.exists(binary_path):
            return OperationResult(success=True, data={"version": version, "binary_path": binary_path})
        return OperationResult(success=False, error=f"Java {version} 未安装或二进制文件不存在")
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _find_java_binary(adapter: JavaAdapter, version: str) -> Optional[str]:
    version_dir = os.path.join(adapter.java_dir, version)
    
    if platform.system() == "Windows":
        possible_paths = [
            os.path.join(version_dir, "bin", "java.exe"),
            os.path.join(version_dir, "java.exe"),
        ]
    else:
        possible_paths = [
            os.path.join(version_dir, "bin", "java"),
            os.path.join(version_dir, "java"),
        ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def _download_version(adapter: JavaAdapter, version: str) -> OperationResult:
    try:
        source = SourceManager().get()
        
        java_source = None
        for item in source.java.list:
            if version in item.windows or version in item.linux:
                java_source = item
                break
        
        if not java_source:
            return OperationResult(success=False, error=f"未找到 Java {version} 的下载源")
        
        if platform.system() == "Windows":
            download_url = java_source.windows.get(version)
        else:
            download_url = java_source.linux.get(version)
        
        if not download_url:
            return OperationResult(success=False, error=f"未找到 Java {version} 的下载链接")
        
        import httpx
        import zipfile
        import tempfile
        
        version_dir = os.path.join(adapter.java_dir, version)
        os.makedirs(version_dir, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.get(download_url, follow_redirects=True)
                response.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(response.content)
            
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                zip_ref.extractall(version_dir)
            
            binary_path = _find_java_binary(adapter, version)
            if binary_path:
                return OperationResult(
                    success=True,
                    data={"version": version, "binary_path": binary_path, "download_url": download_url}
                )
            else:
                return OperationResult(
                    success=False,
                    error=f"下载成功但未找到 java 二进制文件，请检查解压结果"
                )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _list_installed_versions(adapter: JavaAdapter) -> OperationResult:
    try:
        versions = []
        if os.path.exists(adapter.java_dir):
            for item in os.listdir(adapter.java_dir):
                item_path = os.path.join(adapter.java_dir, item)
                if os.path.isdir(item_path):
                    binary_path = _find_java_binary(adapter, item)
                    versions.append({
                        "version": item,
                        "installed": binary_path is not None,
                        "binary_path": binary_path
                    })
        
        return OperationResult(success=True, data={"versions": versions})
    except Exception as e:
        return OperationResult(success=False, error=str(e))
