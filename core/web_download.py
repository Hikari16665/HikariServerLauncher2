import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from .adapter import BaseAdapter, Operation, OperationResult
from .task import BaseTask, OperationTask, TaskStatus


@dataclass
class WebFileDownloadTask(BaseTask):
    url: str = None
    destination: str = None
    chunk_size: int = 8192
    headers: dict = None
    _downloaded_bytes: int = 0
    _total_bytes: Optional[int] = None
    _cancel_event: asyncio.Event = None

    def __post_init__(self):
        if self._cancel_event is None:
            self._cancel_event = asyncio.Event()

    async def execute(self) -> Any:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
            async with client.stream("GET", self.url, headers=self.headers) as response:
                response.raise_for_status()
                self._total_bytes = response.headers.get("content-length", None)
                if self._total_bytes:
                    self._total_bytes = int(self._total_bytes)

                os.makedirs(os.path.dirname(self.destination) or ".", exist_ok=True)

                with open(self.destination, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=self.chunk_size):
                        if self._cancel_event.is_set():
                            raise asyncio.CancelledError("Download cancelled")

                        f.write(chunk)
                        self._downloaded_bytes += len(chunk)

                        if self._total_bytes:
                            self.progress = (self._downloaded_bytes / self._total_bytes) * 100
                        else:
                            self.progress = -1

        return {
            "url": self.url,
            "destination": self.destination,
            "downloaded_bytes": self._downloaded_bytes,
            "total_bytes": self._total_bytes
        }

    async def cancel(self):
        self._cancel_event.set()


def _create_operation(name: str, description: str, func, parameters: Dict[str, Any] = None):
    op = Operation(
        name=name,
        description=description,
        parameters=parameters or {}
    )
    op._execute_func = func
    return op


def _download_file(adapter: BaseAdapter, url: str, destination: str, chunk_size: int = 8192) -> OperationResult:
    try:
        downloaded_bytes = 0
        total_bytes = None

        with httpx.SyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                total_bytes = response.headers.get("content-length", None)
                if total_bytes:
                    total_bytes = int(total_bytes)

                os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)

                with open(destination, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        downloaded_bytes += len(chunk)

        return OperationResult(success=True, data={
            "url": url,
            "destination": destination,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes
        })
    except Exception as e:
        return OperationResult(success=False, error=str(e))


def _download_file_async(adapter: BaseAdapter, url: str, destination: str, chunk_size: int = 8192) -> OperationResult:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_async_download(url, destination, chunk_size))
            return result
        finally:
            loop.close()
    except Exception as e:
        return OperationResult(success=False, error=str(e))


async def _async_download(url: str, destination: str, chunk_size: int):
    downloaded_bytes = 0
    total_bytes = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            total_bytes = response.headers.get("content-length", None)
            if total_bytes:
                total_bytes = int(total_bytes)

            os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)

            with open(destination, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded_bytes += len(chunk)

    return OperationResult(success=True, data={
        "url": url,
        "destination": destination,
        "downloaded_bytes": downloaded_bytes,
        "total_bytes": total_bytes
    })


class WebFileDownloadAdapter(BaseAdapter):
    adapter_name = "web_file_download"
    adapter_description = "Web file download adapter"

    def _register_operations(self):
        self._operations = {
            "download": _create_operation(
                "download",
                "Download a file from URL to destination",
                _download_file_async,
                {
                    "url": {"type": "str", "required": True},
                    "destination": {"type": "str", "required": True},
                    "chunk_size": {"type": "int", "default": 8192}
                }
            ),
        }

    def validate_params(self, operation_name: str, **kwargs) -> tuple[bool, str]:
        url = kwargs.get("url")
        destination = kwargs.get("destination")

        if not url:
            return False, "URL is required"
        if not destination:
            return False, "Destination is required"
        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"

        return True, ""

    def create_task(self, **kwargs) -> WebFileDownloadTask:
        return WebFileDownloadTask(
            task_id=str(uuid.uuid4()),
            url=kwargs["url"],
            destination=kwargs["destination"],
            chunk_size=kwargs.get("chunk_size", 8192),
            headers=kwargs.get("headers")
        )
