from dataclasses import dataclass, field
from typing import Any, Iterator

import logging
import litellm

litellm.suppress_debug_info = True
litellm.set_verbose = False
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class Message:
    """支援一般對話與 function calling 兩種模式。

    一般訊息：role + content
    assistant tool call：role="assistant", content="", tool_calls=[...]
    tool response：role="tool", content=<結果>, tool_call_id, name
    """
    role: str
    content: str = ""
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"role": self.role, "content": self.content or ""}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class Response:
    content: str
    model: str
    usage: dict | None = None
    tool_calls: list[dict] = field(default_factory=list)


class LLM:
    """統一的 LLM 介面，透過 litellm 支援所有 provider。

    model 格式：
        "ollama_chat/qwen3:4b"     → Ollama 本地模型
        "gpt-4o"                   → OpenAI
        "claude-sonnet-4-20250514" → Anthropic
    """

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.extra_params = kwargs

    def chat(self, messages: list[Message], tools: list[dict] | None = None) -> Response:
        raw = litellm.completion(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            base_url=self.base_url,
            api_key=self.api_key,
            tools=tools,
            **self.extra_params,
        )
        msg = raw.choices[0].message

        # 把 litellm 回傳的 tool_calls 轉成純 dict
        tool_calls: list[dict] = []
        raw_calls = getattr(msg, "tool_calls", None) or []
        for tc in raw_calls:
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })

        return Response(
            content=msg.content or "",
            model=self.model,
            usage={
                "prompt_tokens": raw.usage.prompt_tokens,
                "completion_tokens": raw.usage.completion_tokens,
            } if raw.usage else None,
            tool_calls=tool_calls,
        )

    def stream(self, messages: list[Message]) -> Iterator[str]:
        stream = litellm.completion(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            base_url=self.base_url,
            api_key=self.api_key,
            stream=True,
            **self.extra_params,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
