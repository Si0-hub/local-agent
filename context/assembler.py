import litellm

from providers import Message


class ContextAssembler:
    """動態組裝送進 LLM 的 context，根據 token 預算決定要塞哪些訊息。

    策略：
    - System prompt 一定保留
    - 從最新往舊加入對話，直到超過預算為止
    - 舊對話會被丟掉（未來由摘要機制替代）
    """

    def __init__(self, model: str, max_tokens: int = 8000, reserve_for_response: int = 2000):
        self.model = model
        self.max_tokens = max_tokens
        self.reserve_for_response = reserve_for_response

    @property
    def budget(self) -> int:
        """可用於 input 的 token 預算"""
        return self.max_tokens - self.reserve_for_response

    def count_tokens(self, messages: list[Message]) -> int:
        """計算一組訊息的總 token 數"""
        return litellm.token_counter(
            model=self.model,
            messages=[m.to_dict() for m in messages],
        )

    def assemble(self, system: Message, history: list[Message], summary: str = "") -> tuple[list[Message], dict]:
        """組裝 context，回傳 (messages, stats)。

        若有 summary，會注入到 system prompt 後段作為長期記憶。
        stats: {"total_tokens": int, "included": int, "dropped": int}
        """
        if summary:
            system = Message(
                role="system",
                content=f"{system.content}\n\n## 過去對話摘要（長期記憶）\n\n{summary}",
            )

        budget = self.budget
        result = [system]
        system_tokens = self.count_tokens(result)
        used = system_tokens

        included_history: list[Message] = []
        for msg in reversed(history):
            msg_tokens = self.count_tokens([msg])
            if used + msg_tokens > budget:
                break
            included_history.insert(0, msg)
            used += msg_tokens

        result.extend(included_history)
        stats = {
            "total_tokens": used,
            "included": len(included_history),
            "dropped": len(history) - len(included_history),
        }
        return result, stats
