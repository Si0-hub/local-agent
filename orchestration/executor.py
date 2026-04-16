import json
import logging

from providers import LLM, Message
from tools import ToolRegistry
from .types import StepResult


EXECUTOR_PROMPT = """你是任務執行者。

使用者會給你單一步驟，請用提供的工具完成它。

規則：
- 專注於當前這一步，不要做額外的事
- 必要時可連續呼叫多個工具
- 完成後用一句簡短的話說明實際做了什麼
- 若無法完成，清楚說明原因
- 使用繁體中文回覆"""


class ExecutorAgent:
    """執行單一步驟，內部跑 mini ReAct loop"""

    MAX_ITERATIONS = 6

    def __init__(self, llm: LLM, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools

    def execute(self, step: str, prior_results: list[StepResult] | None = None) -> StepResult:
        context_hint = ""
        if prior_results:
            context_hint = "\n\n前面步驟的結果：\n" + "\n".join(
                f"- {r.step} → {r.output}" for r in prior_results
            )

        messages: list[Message] = [
            Message(role="system", content=EXECUTOR_PROMPT),
            Message(role="user", content=f"步驟：{step}{context_hint}"),
        ]

        tools_schema = self.tools.list_schemas()

        for i in range(self.MAX_ITERATIONS):
            response = self.llm.chat(messages, tools=tools_schema)

            if not response.tool_calls:
                return StepResult(step=step, output=response.content.strip() or "（無輸出）", success=True)

            messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            for call in response.tool_calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                logging.info("[Executor iter %d] %s(%s)", i, name, args)

                try:
                    result = self.tools.get(name)(**args)
                except Exception as e:
                    result = f"錯誤：{e}"

                logging.info("[Executor iter %d] result: %s", i, str(result)[:300])

                messages.append(Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=call["id"],
                    name=name,
                ))

        return StepResult(step=step, output="達到最大迭代次數未能完成", success=False)
