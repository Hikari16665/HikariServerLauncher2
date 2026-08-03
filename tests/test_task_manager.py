from core.task import TaskStatus
from core.task_manager import TaskManager


def isolated_manager():
    manager = TaskManager()
    previous_tasks = manager._tasks
    previous_listeners = manager._listeners
    manager._tasks = {}
    manager._listeners = set()
    return manager, previous_tasks, previous_listeners


def restore_manager(manager, tasks, listeners):
    manager._tasks = tasks
    manager._listeners = listeners


def test_completed_task_history_is_bounded():
    manager, previous_tasks, previous_listeners = isolated_manager()
    try:
        for number in range(manager.MAX_COMPLETED_TASKS + 25):
            task = manager.create_composite_task(lambda *_args: None)
            task.status = TaskStatus.COMPLETED
            task.completed_at = float(number)
            task.notify()

        tasks = manager.get_tasks()
        assert len(tasks) == manager.MAX_COMPLETED_TASKS
        assert min(task.completed_at for task in tasks) == 25
    finally:
        restore_manager(manager, previous_tasks, previous_listeners)


def test_clear_completed_tasks_preserves_active_tasks():
    manager, previous_tasks, previous_listeners = isolated_manager()
    try:
        pending = manager.create_composite_task(lambda *_args: None)
        completed = manager.create_composite_task(lambda *_args: None)
        completed.status = TaskStatus.COMPLETED

        assert manager.clear_completed_tasks() == 1
        assert manager.get_tasks() == [pending]
    finally:
        restore_manager(manager, previous_tasks, previous_listeners)


def test_clear_completed_tasks_broadcasts_new_snapshot():
    manager, previous_tasks, previous_listeners = isolated_manager()
    events = []
    try:
        pending = manager.create_composite_task(lambda *_args: None)
        completed = manager.create_composite_task(lambda *_args: None)
        completed.status = TaskStatus.COMPLETED
        manager.subscribe(events.append)

        manager.clear_completed_tasks()

        assert events[-1]["type"] == "task_snapshot"
        assert [task["task_id"] for task in events[-1]["tasks"]] == [pending.task_id]
    finally:
        restore_manager(manager, previous_tasks, previous_listeners)
