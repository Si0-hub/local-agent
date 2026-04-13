from dataclasses import dataclass
from typing import Iterator

import logging
import litellm

litellm.suppress_debug_info = True
litellm.set_verbose = False
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class Response:
    content: str
    model: str
    usage: dict | None = None


class LLM:
    """統一的 LLM 介面，透過 litellm 支援所有 provider。

    model 格式：
        "ollama/qwen3:4b"          → Ollama 本地模型
        "gpt-4o"                   → OpenAI
        "claude-sonnet-4-20250514"          → Anthropic
        "deepseek/deepseek-chat"   → DeepSeek
    """

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.extra_params = kwargs

    def chat(self, messages: list[Message]) -> Response:
        raw = litellm.completion(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            base_url=self.base_url,
            api_key=self.api_key,
            **self.extra_params,
        )
        return Response(
            content=raw.choices[0].message.content,
            model=self.model,
            usage={
                "prompt_tokens": raw.usage.prompt_tokens,
                "completion_tokens": raw.usage.completion_tokens,
            } if raw.usage else None,
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
