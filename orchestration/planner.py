import re

from providers import LLM, Message
from .types import Plan


PLANNER_PROMPT = """你是任務規劃專家。

使用者會給你一個任務，請把它拆解成清楚、可執行的步驟清單。

規則：
- 每個步驟要具體、單一動作
- 步驟按執行順序排列
- 不要寫程式碼，只描述要做什麼
- 使用繁體中文
- 每行一個步驟，以數字加句點開頭（例如「1. ...」）
- 不要輸出其他說明文字，只輸出步驟清單

範例：
任務：讀取 config.json 的內容並備份到 backup/config.json
輸出：
1. 讀取 config.json 的內容
2. 建立 backup 資料夾
3. 將內容寫入 backup/config.json"""


class PlannerAgent:
    """把任務拆成步驟清單，不使用工具"""

    def __init__(self, llm: LLM):
        self.llm = llm

    def plan(self, task: str) -> Plan:
        messages = [
            Message(role="system", content=PLANNER_PROMPT),
            Message(role="user", content=f"任務：{task}\n\n請輸出步驟清單："),
        ]
        response = self.llm.chat(messages)
        return self._parse(response.content)

    def _parse(self, text: str) -> Plan:
        steps = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\d+\s*[\.\)、:]\s*(.+)", line)
            if m:
                steps.append(m.group(1).strip())
            elif line.startswith(("-", "*", "•")):
                steps.append(line.lstrip("-*• ").strip())
        return Plan(steps=steps)
