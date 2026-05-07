from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class OperationResult:
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


@dataclass
class Operation:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    _execute_func: Optional[Callable] = field(default=None, repr=False)
    _adapter: Optional['BaseAdapter'] = field(default=None, repr=False)

    def execute(self, **kwargs) -> OperationResult:
        if self._execute_func:
            return self._execute_func(self._adapter, **kwargs)
        raise NotImplementedError("Operation execute not implemented")


class BaseAdapter(ABC):
    adapter_name: str = "base"
    adapter_description: str = ""

    def __init__(self):
        self._operations: Dict[str, Operation] = {}
        self._register_operations()

    @abstractmethod
    def _register_operations(self):
        pass

    def get_operations(self) -> Dict[str, Operation]:
        return self._operations

    def get_operation(self, name: str) -> Optional[Operation]:
        return self._operations.get(name)

    def list_operations(self) -> List[str]:
        return list(self._operations.keys())

    def get_adapter_info(self) -> Dict[str, Any]:
        return {
            "name": self.adapter_name,
            "description": self.adapter_description,
            "operations": [
                {
                    "name": op.name,
                    "description": op.description,
                    "parameters": op.parameters
                }
                for op in self._operations.values()
            ]
        }

    def validate_params(self, operation_name: str, **kwargs) -> Tuple[bool, str]:
        op = self.get_operation(operation_name)
        if not op:
            return False, f"Operation '{operation_name}' not found"
        return True, ""
