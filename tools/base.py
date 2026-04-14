import inspect
from dataclasses import dataclass, field
from typing import Callable, get_type_hints


_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class Tool:
    name: str
    description: str
    func: Callable
    parameters: dict = field(default_factory=dict)

    def to_schema(self) -> dict:
        """OpenAI function calling 格式（litellm 統一用這個）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, **kwargs):
        return self.func(**kwargs)


def tool(name: str | None = None, description: str | None = None):
    """把一個 function 註冊成 Tool，自動從 type hints 產生 schema。

    參數描述會從 docstring 的第一段取得。
    """
    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip().split("\n")[0]

        hints = get_type_hints(func)
        sig = inspect.signature(func)

        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            py_type = hints.get(param_name, str)
            json_type = _PY_TO_JSON.get(py_type, "string")
            properties[param_name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        return Tool(
            name=tool_name,
            description=tool_desc,
            func=func,
            parameters=parameters,
        )

    return decorator


class ToolRegistry:
    """集中管理所有可用工具"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, *tools: Tool):
        for t in tools:
            self._tools[t.name] = t

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' 不存在，可用的: {list(self._tools.keys())}")
        return self._tools[name]

    def list_schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __bool__(self) -> bool:
        return len(self._tools) > 0
