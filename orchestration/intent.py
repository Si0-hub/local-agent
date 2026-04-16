import re
from enum import Enum
from providers import LLM, Message

class Intent(Enum):
    INQUIRY = "INQUIRY"     # 詢問、分析、搜尋信息
    DIRECTIVE = "DIRECTIVE" # 執行、修改、操作、實現功能

INTENT_PROMPT = """你是一個意圖分析專家。
請判斷使用者的輸入是「詢問」(INQUIRY) 還是「指令」(DIRECTIVE)。

- INQUIRY (詢問)：使用者在尋求資訊、分析現況、解釋代碼、提出疑問或搜尋特定內容。不涉及對系統或檔案的實質修改。
- DIRECTIVE (指令)：使用者要求執行動作、修改檔案、建立新功能、修復 Bug、重構代碼或進行任何會改變系統狀態的操作。

規則：
- 只輸出「INQUIRY」或「DIRECTIVE」。
- 不要輸出任何其他文字。
"""

class IntentClassifier:
    """判斷使用者輸入的意圖"""

    def __init__(self, llm: LLM):
        self.llm = llm

    def classify(self, user_input: str) -> Intent:
        messages = [
            Message(role="system", content=INTENT_PROMPT),
            Message(role="user", content=f"使用者輸入：{user_input}"),
        ]
        response = self.llm.chat(messages)
        content = response.content.strip()

        # 去掉 qwen3 的 <think>...</think> 思考鏈，只看最終輸出
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip().upper()

        if "DIRECTIVE" in content:
            return Intent.DIRECTIVE
        return Intent.INQUIRY
