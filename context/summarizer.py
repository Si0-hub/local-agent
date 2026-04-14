from providers import LLM, Message


SUMMARIZE_PROMPT = """你的任務是把一段對話壓縮成精簡的摘要，供後續對話作為背景記憶使用。

保留原則（重要 → 不重要）：
1. 使用者透露的個人資訊、身份、偏好
2. 已經做出的決定、達成的共識
3. 關鍵事實、資料、結論
4. 討論過但未解決的問題

略去原則：
- 寒暄、客套、表情符號
- 重複的內容
- 已被後續對話否定或取代的資訊

{existing_section}
## 要壓縮的新對話

{conversation}

請輸出更新後的完整摘要（繁體中文，條列式，精簡）："""


class Summarizer:
    """把對話壓縮成摘要，用於長期記憶"""

    def __init__(self, llm: LLM):
        self.llm = llm

    def summarize(self, messages: list[Message], existing: str = "") -> str:
        conversation = "\n".join(
            f"[{m.role}] {m.content}" for m in messages
        )

        if existing:
            existing_section = f"## 既有摘要\n\n{existing}\n\n"
        else:
            existing_section = ""

        prompt = SUMMARIZE_PROMPT.format(
            existing_section=existing_section,
            conversation=conversation,
        )

        response = self.llm.chat([Message(role="user", content=prompt)])
        return response.content.strip()
