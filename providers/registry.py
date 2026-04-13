from .base import LLM


class ProviderRegistry:
    """集中管理所有 LLM，Agent 用名稱引用"""

    def __init__(self):
        self._providers: dict[str, LLM] = {}
        self._default: str | None = None

    def register(self, name: str, llm: LLM, default: bool = False):
        self._providers[name] = llm
        if default or self._default is None:
            self._default = name

    def get(self, name: str | None = None) -> LLM:
        name = name or self._default
        if name is None or name not in self._providers:
            available = list(self._providers.keys())
            raise KeyError(f"LLM '{name}' 不存在，可用的: {available}")
        return self._providers[name]

    def list(self) -> list[dict]:
        return [
            {"name": name, "default": name == self._default, "model": llm.model}
            for name, llm in self._providers.items()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._providers
