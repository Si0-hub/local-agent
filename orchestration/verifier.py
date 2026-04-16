import json
import logging
import re

from providers import LLM, Message
from tools import ToolRegistry
from .types import Plan, StepResult, Verdict


VERIFIER_PROMPT = """你是任務驗證者。

使用者會給你：原始任務、執行計畫、每一步的結果。
請判斷任務是否真的完成。

你可以使用唯讀工具（list_directory、read_file、search_file）去確認結果是否正確。
不要使用任何會修改檔案的工具。

輸出格式（嚴格遵守）：
先用自然語言分析，最後一行必須是：
VERDICT: OK
或
VERDICT: FAIL
FEEDBACK: <具體原因與修正建議>

請使用繁體中文。"""


class VerifierAgent:
    """驗證任務是否完成，只用唯讀工具"""

    MAX_ITERATIONS = 4

    def __init__(self, llm: LLM, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools

    def verify(self, task: str, plan: Plan, results: list[StepResult]) -> Verdict:
        report = f"## 原始任務\n{task}\n\n## 執行計畫\n"
        for i, step in enumerate(plan.steps, 1):
            report += f"{i}. {step}\n"
        report += "\n## 執行結果\n"
        for i, r in enumerate(results, 1):
            mark = "OK" if r.success else "FAIL"
            report += f"{i}. [{mark}] {r.step}\n   → {r.output}\n"

        messages: list[Message] = [
            Message(role="system", content=VERIFIER_PROMPT),
            Message(role="user", content=report + "\n\n請驗證任務是否完成。"),
        ]

        tools_schema = self.tools.list_schemas()

        for i in range(self.MAX_ITERATIONS):
            response = self.llm.chat(messages, tools=tools_schema)

            if not response.tool_calls:
                return self._parse(response.content)

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

                logging.info("[Verifier iter %d] %s(%s)", i, name, args)

                try:
                    result = self.tools.get(name)(**args)
                except Exception as e:
                    result = f"錯誤：{e}"

                messages.append(Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=call["id"],
                    name=name,
                ))

        return Verdict(ok=False, feedback="驗證達到最大迭代次數，無法確認結果", raw="")

    def _parse(self, text: str) -> Verdict:
        ok = bool(re.search(r"VERDICT\s*[:：]\s*OK", text, re.IGNORECASE))
        feedback = ""
        m = re.search(r"FEEDBACK\s*[:：]\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        if m:
            feedback = m.group(1).strip()
        return Verdict(ok=ok, feedback=feedback, raw=text)
