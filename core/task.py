import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .adapter import BaseAdapter, Operation


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def from_str(cls, value: str) -> "TaskStatus":
        return cls(value)


@dataclass
class BaseTask(ABC):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    progress_message: str = ""
    error_message: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any | None = None
    _started: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _coroutine: asyncio.Task | None = field(default=None, repr=False)

    @abstractmethod
    def execute_sync(self) -> Any:
        pass

    @abstractmethod
    async def execute(self) -> Any:
        pass

    @abstractmethod
    async def cancel(self):
        pass

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
        }


@dataclass
class OperationTask(BaseTask):
    adapter: BaseAdapter | None = None
    operation: Operation | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def execute_sync(self) -> Any:
        try:
            if self.operation:
                return self.operation.execute(**self.params)
            raise ValueError("Operation not set")
        except Exception:
            raise

    async def execute(self) -> Any:
        try:
            return await asyncio.to_thread(self.execute_sync)
        except Exception:
            raise

    async def cancel(self):
        pass


@dataclass
class CompositeTask(BaseTask):
    """A task composed of multiple sequential steps driven by a callable."""

    _execute_fn: Callable | None = field(default=None, repr=False)
    _cancel_fn: Callable | None = field(default=None, repr=False)
    _progress_callback: Callable | None = field(default=None, repr=False)

    def set_progress(self, progress: float, message: str = ""):
        self.progress = progress
        if message:
            self.progress_message = message

    def execute_sync(self) -> Any:
        if self._execute_fn:
            return self._execute_fn(self, self.set_progress)
        raise ValueError("CompositeTask has no _execute_fn")

    async def execute(self) -> Any:
        try:
            return await asyncio.to_thread(self.execute_sync)
        except Exception:
            raise

    async def cancel(self):
        if self._cancel_fn:
            self._cancel_fn()


@dataclass
class TaskResult:
    success: bool
    data: Any | None = None
    error: str | None = None
