from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional


class OperationResult:
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


@dataclass
class Operation:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    _execute_func: Callable | None = field(default=None, repr=False)
    _adapter: Optional["BaseAdapter"] = field(default=None, repr=False)

    def execute(self, **kwargs) -> OperationResult:
        if self._execute_func:
            return self._execute_func(self._adapter, **kwargs)
        raise NotImplementedError("Operation execute not implemented")


class BaseAdapter(ABC):
    adapter_name: str = "base"
    adapter_description: str = ""

    def __init__(self):
        self._operations: dict[str, Operation] = {}
        self._register_operations()

    @abstractmethod
    def _register_operations(self):
        pass

    def get_operations(self) -> dict[str, Operation]:
        return self._operations

    def get_operation(self, name: str) -> Operation | None:
        return self._operations.get(name)

    def list_operations(self) -> list[str]:
        return list(self._operations.keys())

    def get_adapter_info(self) -> dict[str, Any]:
        return {
            "name": self.adapter_name,
            "description": self.adapter_description,
            "operations": [
                {"name": op.name, "description": op.description, "parameters": op.parameters}
                for op in self._operations.values()
            ],
        }

    def validate_params(self, operation_name: str, **kwargs) -> tuple[bool, str]:
        op = self.get_operation(operation_name)
        if not op:
            return False, f"Operation '{operation_name}' not found"
        return True, ""
