from typing import Any, Dict, List, Optional, Tuple

import docker

from .adapter import BaseAdapter, Operation, OperationResult


def _create_operation(name: str, description: str, func, parameters: Dict[str, Any] = None):
    op = Operation(
        name=name,
        description=description,
        parameters=parameters or {}
    )
    op._execute_func = func
    return op


def _check_installed(adapter: BaseAdapter) -> OperationResult:
    try:
        client = docker.from_env()
        client.ping()
        return OperationResult(success=True, data={"installed": True})
    except Exception as e:
        return OperationResult(success=True, data={"installed": False}, error=str(e))


def _get_version(adapter: BaseAdapter) -> OperationResult:
    try:
        client = docker.from_env()
        version = client.version()
        return OperationResult(success=True, data={
            "version": version.get("Version"),
            "api_version": version.get("ApiVersion"),
            "os": version.get("Os"),
            "arch": version.get("Arch"),
            "kernel": version.get("KernelVersion"),
        })
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _list_images(adapter: BaseAdapter, all_tags: bool = False) -> OperationResult:
    try:
        client = docker.from_env()
        images = client.images.list(all=all_tags)
        data = []
        for img in images:
            data.append({
                "id": img.id,
                "tags": img.tags,
                "size": img.attrs.get("Size", 0),
                "created": img.attrs.get("Created"),
            })
        return OperationResult(success=True, data=data)
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _pull_image(adapter: BaseAdapter, repository: str, tag: str = "latest") -> OperationResult:
    try:
        client = docker.from_env()
        client.images.pull(repository, tag)
        return OperationResult(success=True, data={"repository": repository, "tag": tag})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _remove_image(adapter: BaseAdapter, image_id: str, force: bool = False) -> OperationResult:
    try:
        client = docker.from_env()
        client.images.remove(image_id, force=force)
        return OperationResult(success=True, data={"image_id": image_id})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _list_containers(adapter: BaseAdapter, all: bool = True) -> OperationResult:
    try:
        client = docker.from_env()
        containers = client.containers.list(all=all)
        data = []
        for c in containers:
            data.append({
                "id": c.id,
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else c.image_id,
                "status": c.status,
                "ports": c.ports,
            })
        return OperationResult(success=True, data=data)
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _get_container(adapter: BaseAdapter, container_id: str) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        return OperationResult(success=True, data={
            "id": container.id,
            "name": container.name,
            "image": container.image.tags[0] if container.image.tags else container.image_id,
            "status": container.status,
            "ports": container.ports,
        })
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _create_container(
    adapter: BaseAdapter,
    image: str,
    name: str = None,
    ports: str = None,
    volumes: str = None,
    environment: str = None,
    detach: bool = True
) -> OperationResult:
    try:
        client = docker.from_env()

        port_bindings = None
        if ports:
            port_bindings = {}
            for mapping in ports.split(","):
                container_port, host_port = mapping.split(":")
                port_bindings[f"{container_port}/tcp"] = int(host_port)

        volume_bindings = None
        if volumes:
            volume_bindings = {}
            for vol in volumes.split(","):
                host_path, container_path, mode = vol.split(":")
                volume_bindings[host_path] = {"bind": container_path, "mode": mode}

        env_vars = None
        if environment:
            env_vars = [e for e in environment.split(",")]

        container = client.containers.run(
            image,
            name=name,
            ports=port_bindings,
            volumes=volume_bindings,
            environment=env_vars,
            detach=detach,
        )
        return OperationResult(success=True, data={"container_id": container.id})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _start_container(adapter: BaseAdapter, container_id: str) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.start()
        return OperationResult(success=True, data={"container_id": container_id})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _stop_container(adapter: BaseAdapter, container_id: str, timeout: int = 10) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.stop(timeout=timeout)
        return OperationResult(success=True, data={"container_id": container_id})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _restart_container(adapter: BaseAdapter, container_id: str, timeout: int = 10) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.restart(timeout=timeout)
        return OperationResult(success=True, data={"container_id": container_id})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _remove_container(
    adapter: BaseAdapter,
    container_id: str,
    force: bool = False,
    remove_volumes: bool = True
) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.remove(force=force, remove_volumes=remove_volumes)
        return OperationResult(success=True, data={"container_id": container_id})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _get_container_logs(adapter: BaseAdapter, container_id: str, tail: int = 100) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        logs = container.logs(tail=tail).decode("utf-8")
        return OperationResult(success=True, data={"logs": logs})
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _get_container_stats(adapter: BaseAdapter, container_id: str) -> OperationResult:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        return OperationResult(success=True, data={
            "cpu_percent": stats.get("cpu_stats", {}).get("cpu_percent", 0),
            "memory_usage": stats.get("memory_stats", {}).get("usage", 0),
            "memory_limit": stats.get("memory_stats", {}).get("limit", 0),
            "network_rx": stats.get("networks", {}).get("eth0", {}).get("rx_bytes", 0),
            "network_tx": stats.get("networks", {}).get("eth0", {}).get("tx_bytes", 0),
        })
    except Exception as e:
        return OperationResult(success=False, error=str(e))


class DockerAdapter(BaseAdapter):
    adapter_name = "docker"
    adapter_description = "Docker container management adapter"

    def _register_operations(self):
        self._operations = {
            "check_installed": _create_operation(
                "check_installed",
                "Check if Docker is installed and running",
                _check_installed
            ),
            "get_version": _create_operation(
                "get_version",
                "Get Docker version information",
                _get_version
            ),
            "list_images": _create_operation(
                "list_images",
                "List all Docker images",
                _list_images,
                {"all_tags": {"type": "bool", "default": False}}
            ),
            "pull_image": _create_operation(
                "pull_image",
                "Pull a Docker image from registry",
                _pull_image,
                {
                    "repository": {"type": "str", "required": True},
                    "tag": {"type": "str", "default": "latest"}
                }
            ),
            "remove_image": _create_operation(
                "remove_image",
                "Remove a Docker image",
                _remove_image,
                {
                    "image_id": {"type": "str", "required": True},
                    "force": {"type": "bool", "default": False}
                }
            ),
            "list_containers": _create_operation(
                "list_containers",
                "List all Docker containers",
                _list_containers,
                {"all": {"type": "bool", "default": True}}
            ),
            "get_container": _create_operation(
                "get_container",
                "Get details of a specific container",
                _get_container,
                {"container_id": {"type": "str", "required": True}}
            ),
            "create_container": _create_operation(
                "create_container",
                "Create a new Docker container",
                _create_container,
                {
                    "image": {"type": "str", "required": True},
                    "name": {"type": "str", "default": None},
                    "ports": {"type": "str", "default": None, "hint": "container_port:host_port,..."},
                    "volumes": {"type": "str", "default": None, "hint": "host_path:container_path:mode,..."},
                    "environment": {"type": "str", "default": None, "hint": "KEY=VALUE,..."},
                    "detach": {"type": "bool", "default": True}
                }
            ),
            "start_container": _create_operation(
                "start_container",
                "Start a Docker container",
                _start_container,
                {"container_id": {"type": "str", "required": True}}
            ),
            "stop_container": _create_operation(
                "stop_container",
                "Stop a Docker container",
                _stop_container,
                {
                    "container_id": {"type": "str", "required": True},
                    "timeout": {"type": "int", "default": 10}
                }
            ),
            "restart_container": _create_operation(
                "restart_container",
                "Restart a Docker container",
                _restart_container,
                {
                    "container_id": {"type": "str", "required": True},
                    "timeout": {"type": "int", "default": 10}
                }
            ),
            "remove_container": _create_operation(
                "remove_container",
                "Remove a Docker container",
                _remove_container,
                {
                    "container_id": {"type": "str", "required": True},
                    "force": {"type": "bool", "default": False},
                    "remove_volumes": {"type": "bool", "default": True}
                }
            ),
            "get_container_logs": _create_operation(
                "get_container_logs",
                "Get logs from a container",
                _get_container_logs,
                {
                    "container_id": {"type": "str", "required": True},
                    "tail": {"type": "int", "default": 100}
                }
            ),
            "get_container_stats": _create_operation(
                "get_container_stats",
                "Get resource usage stats from a container",
                _get_container_stats,
                {"container_id": {"type": "str", "required": True}}
            ),
        }
