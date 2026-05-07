import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

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
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    _started: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _coroutine: Optional[asyncio.Task] = field(default=None, repr=False)

    @abstractmethod
    def execute_sync(self) -> Any:
        pass

    @abstractmethod
    async def execute(self) -> Any:
        pass

    @abstractmethod
    async def cancel(self):
        pass

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result
        }


@dataclass
class OperationTask(BaseTask):
    adapter: Optional[BaseAdapter] = None
    operation: Optional[Operation] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def execute_sync(self) -> Any:
        try:
            if self.operation:
                return self.operation.execute(**self.params)
            raise ValueError("Operation not set")
        except Exception as e:
            raise

    async def execute(self) -> Any:
        try:
            return await asyncio.to_thread(self.execute_sync)
        except Exception as e:
            raise

    async def cancel(self):
        pass


@dataclass
class CompositeTask(BaseTask):
    """A task composed of multiple sequential steps driven by a callable."""
    _execute_fn: Optional[Callable] = field(default=None, repr=False)
    _cancel_fn: Optional[Callable] = field(default=None, repr=False)
    _progress_callback: Optional[Callable] = field(default=None, repr=False)

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
        except Exception as e:
            raise

    async def cancel(self):
        if self._cancel_fn:
            self._cancel_fn()


@dataclass
class TaskResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
