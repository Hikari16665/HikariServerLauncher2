import asyncio
import contextlib
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from .adapter import BaseAdapter
from .task import BaseTask, CompositeTask, OperationTask, TaskStatus


class TaskManager:
    MAX_COMPLETED_TASKS = 200
    _instance: Optional["TaskManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._tasks: dict[str, BaseTask] = {}
            self._adapters: dict[str, BaseAdapter] = {}
            self._loop: asyncio.AbstractEventLoop | None = None
            self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
                max_workers=4, thread_name_prefix="task_manager_"
            )
            self._listeners: set[Callable[[dict[str, Any]], None]] = set()
            self._lock = threading.RLock()
            self._initialized = True

    def _ensure_event_loop(self):
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

    def register_adapter(self, adapter: BaseAdapter):
        self._adapters[adapter.adapter_name] = adapter

    def get_adapter(self, name: str) -> BaseAdapter | None:
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        return list(self._adapters.keys())

    def get_all_operations(self) -> dict[str, list[str]]:
        result = {}
        for name, adapter in self._adapters.items():
            result[name] = adapter.list_operations()
        return result

    def get_adapter_operations(self, adapter_name: str) -> list[str] | None:
        adapter = self.get_adapter(adapter_name)
        if adapter:
            return adapter.list_operations()
        return None

    def _run_task_sync(self, task: BaseTask):
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            task._started.set()
            task.notify()
            result = task.execute_sync()
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.progress = 100.0
            if task.current_step:
                task.complete_step(task.current_step)
            task.notify()
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = time.time()
            if task.current_step:
                task.set_step(
                    task.current_step, task.progress_message or task.current_step, "failed"
                )
            task.notify()

    async def _run_task_async(self, task: BaseTask):
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            task._started.set()

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._run_task_sync, task)

            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                task.progress = 100.0
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            await task.cancel()
            task.notify()
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = time.time()
            task.notify()

    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.add(listener)

        def unsubscribe() -> None:
            with self._lock:
                self._listeners.discard(listener)

        return unsubscribe

    def _emit_task(self, task: BaseTask) -> None:
        event = {"type": "task", "task": task.to_dict(), "timestamp": time.time()}
        with self._lock:
            self._prune_completed_locked()
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                with self._lock:
                    self._listeners.discard(listener)

    def _prune_completed_locked(self) -> None:
        completed = sorted(
            (
                task
                for task in self._tasks.values()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ),
            key=lambda task: task.completed_at or 0,
            reverse=True,
        )
        for task in completed[self.MAX_COMPLETED_TASKS :]:
            self._tasks.pop(task.task_id, None)

    def create_operation_task(
        self, adapter_name: str, operation_name: str, **kwargs
    ) -> tuple[bool, BaseTask | None, str]:
        adapter = self.get_adapter(adapter_name)
        if not adapter:
            return False, None, f"Adapter '{adapter_name}' not found"

        operation = adapter.get_operation(operation_name)
        if not operation:
            return (
                False,
                None,
                f"Operation '{operation_name}' not found in adapter '{adapter_name}'",
            )

        valid, error = adapter.validate_params(operation_name, **kwargs)
        if not valid:
            return False, None, error

        task = OperationTask(
            task_id=str(uuid.uuid4()),
            adapter=adapter,
            operation=operation,
            params=kwargs,
            title=operation.description or operation.name,
        )
        task._on_update = self._emit_task
        with self._lock:
            self._prune_completed_locked()
            self._tasks[task.task_id] = task
        return True, task, ""

    def create_composite_task(
        self,
        execute_fn: Callable,
        cancel_fn: Callable = lambda: None,
    ) -> CompositeTask:
        task = CompositeTask(
            task_id=str(uuid.uuid4()),
            _execute_fn=execute_fn,
            _cancel_fn=cancel_fn,
            title="Create server",
        )
        task._on_update = self._emit_task
        with self._lock:
            self._prune_completed_locked()
            self._tasks[task.task_id] = task
        return task

    def set_task_progress(self, task_id: str, progress: float, message: str = ""):
        task = self._tasks.get(task_id)
        if task:
            task.set_progress(progress, message)

    async def start_task(self, task_id: str) -> tuple[bool, str]:
        task = self._tasks.get(task_id)
        if not task:
            return False, f"Task '{task_id}' not found"
        if task.status != TaskStatus.PENDING:
            return False, f"Task '{task_id}' is not in pending state"

        self._ensure_event_loop()
        task._coroutine = asyncio.create_task(self._run_task_async(task))
        try:
            async with asyncio.timeout(5.0):
                await task._started.wait()
        except TimeoutError:
            return False, f"Task '{task_id}' failed to start within timeout"
        return True, ""

    def get_task(self, task_id: str) -> BaseTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> TaskStatus | None:
        task = self._tasks.get(task_id)
        return task.status if task else None

    def get_task_progress(self, task_id: str) -> float:
        task = self._tasks.get(task_id)
        return task.progress if task else 0.0

    def get_task_error(self, task_id: str) -> str | None:
        task = self._tasks.get(task_id)
        return task.error_message if task else None

    async def cancel_task(self, task_id: str) -> tuple[bool, str]:
        task = self._tasks.get(task_id)
        if not task:
            return False, f"Task '{task_id}' not found"
        if task.status == TaskStatus.COMPLETED:
            return False, f"Task '{task_id}' already completed"
        if task.status == TaskStatus.FAILED:
            return False, f"Task '{task_id}' already failed"

        if task._coroutine:
            task._coroutine.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task._coroutine

        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        task.notify()
        return True, ""

    def list_tasks(self, status: TaskStatus | None = None) -> list[BaseTask]:
        with self._lock:
            if status:
                return [t for t in self._tasks.values() if t.status == status]
            return list(self._tasks.values())

    def get_all_tasks_info(self) -> list[dict[str, Any]]:
        return [task.to_dict() for task in self.list_tasks()]

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def clear_completed_tasks(self) -> int:
        with self._lock:
            completed_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for task_id in completed_ids:
                del self._tasks[task_id]
            snapshot = [task.to_dict() for task in self._tasks.values()]
            listeners = list(self._listeners)
        event = {"type": "task_snapshot", "tasks": snapshot, "timestamp": time.time()}
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                with self._lock:
                    self._listeners.discard(listener)
        return len(completed_ids)

    async def run_operation(
        self,
        adapter_name: str,
        operation_name: str,
        progress_callback: Callable | None = None,
        **kwargs,
    ) -> tuple[bool, Any, str | None]:
        success, task, error = self.create_operation_task(adapter_name, operation_name, **kwargs)
        if not success:
            return False, None, error

        if task is None:
            return False, None, error

        success, error = await self.start_task(task.task_id)
        if not success:
            return False, None, error

        try:
            while task.status == TaskStatus.RUNNING:
                if progress_callback:
                    progress_callback(task.task_id, task.status, task.progress)
                await asyncio.sleep(0.1)

            if task.status == TaskStatus.COMPLETED:
                if progress_callback:
                    progress_callback(task.task_id, task.status, task.progress)
                return True, task.result, None
            elif task.status == TaskStatus.FAILED:
                return False, None, task.error_message
            elif task.status == TaskStatus.CANCELLED:
                return False, None, "Task was cancelled"
            else:
                return False, None, f"Unexpected status: {task.status.value}"
        except asyncio.CancelledError:
            await self.cancel_task(task.task_id)
            return False, None, "Task was cancelled"

    async def run_operation_with_progress(
        self,
        adapter_name: str,
        operation_name: str,
        on_progress: Callable[[str, float, str], None] | None = None,
        poll_interval: float = 0.1,
        **kwargs,
    ) -> tuple[bool, Any, str | None]:
        success, task, error = self.create_operation_task(adapter_name, operation_name, **kwargs)
        if not success:
            return False, None, error

        if task is None:
            return False, None, error

        success, error = await self.start_task(task.task_id)
        if not success:
            return False, None, error

        try:
            while task.status == TaskStatus.RUNNING:
                if on_progress:
                    on_progress(task.task_id, task.progress, task.status.value)
                await asyncio.sleep(poll_interval)

            if task.status == TaskStatus.COMPLETED:
                if on_progress:
                    on_progress(task.task_id, 100.0, task.status.value)
                return True, task.result, None
            elif task.status == TaskStatus.FAILED:
                return False, None, task.error_message
            elif task.status == TaskStatus.CANCELLED:
                return False, None, "Task was cancelled"
            else:
                return False, None, f"Unexpected status: {task.status.value}"
        except asyncio.CancelledError:
            await self.cancel_task(task.task_id)
            return False, None, "Task was cancelled"

    def create_and_run_sync(
        self, adapter_name: str, operation_name: str, **kwargs
    ) -> tuple[bool, Any, str | None]:
        success, task, error = self.create_operation_task(adapter_name, operation_name, **kwargs)
        if not success:
            return False, None, error

        if task is None:
            return False, None, error

        self._ensure_event_loop()
        if self._loop.is_running():  # type: ignore because event loop ensured
            raise RuntimeError("Cannot run sync task when event loop is already running")

        self._run_task_sync(task)
        self.remove_task(task.task_id)

        if task.status == TaskStatus.COMPLETED:
            return True, task.result, None
        elif task.status == TaskStatus.FAILED:
            return False, None, task.error_message
        else:
            return False, None, f"Unexpected status: {task.status.value}"

    def run_task_background(self, task_id: str):
        """Start a task in a background thread with its own event loop."""
        import threading

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start_task(task_id))
            finally:
                loop.close()

        thread = threading.Thread(target=_run, daemon=True, name=f"task_{task_id}")
        thread.start()

    def get_tasks(self, status: TaskStatus | None = None) -> list[BaseTask]:
        return self.list_tasks(status)
