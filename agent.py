import json
import os
import uuid
import logging
from datetime import datetime
from typing import Iterator

from providers import Message, ProviderRegistry
from context import ContextAssembler, Summarizer
from tools import ToolRegistry

AGENT_HOME = os.path.join(os.path.expanduser("~"), ".agent")
PROJECTS_DIR = os.path.join(AGENT_HOME, "projects")

DEFAULT_SYSTEM_PROMPT = "你是一個本地 AI 助手，運行在使用者的電腦上。"

logging.basicConfig(
    filename="agent.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)


def path_to_dirname(path: str) -> str:
    """將路徑轉成資料夾名稱（如 E:\\workspace\\agent → E--workspace-agent）"""
    path = os.path.abspath(path)
    # 移除尾部斜線，替換 : / \ 為 -
    path = path.rstrip("/\\")
    return path.replace(":", "").replace("\\", "-").replace("/", "-")


def get_project_dir(project_path: str) -> str:
    """取得專案在 ~/.agent/projects/ 下的資料夾路徑"""
    dirname = path_to_dirname(project_path)
    return os.path.join(PROJECTS_DIR, dirname)


def list_projects() -> list[dict]:
    """列出所有已建立的專案"""
    if not os.path.exists(PROJECTS_DIR):
        return []
    projects = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        project_dir = os.path.join(PROJECTS_DIR, name)
        if not os.path.isdir(project_dir):
            continue
        # 讀取原始路徑
        meta_path = os.path.join(project_dir, "project.json")
        original_path = name  # fallback
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                original_path = json.load(f).get("path", name)
        sessions = [f for f in os.listdir(project_dir) if f.endswith(".jsonl")]
        projects.append({"name": name, "original_path": original_path, "path": project_dir, "sessions": len(sessions)})
    return projects


class Agent:
    # 當記憶中訊息數超過此閾值時觸發摘要，壓縮最舊一半
    SUMMARIZE_THRESHOLD = 30
    # ReAct loop 最多迭代次數，避免無限循環
    MAX_ITERATIONS = 10

    def __init__(self, registry: ProviderRegistry, project_path: str, provider_name: str | None = None, session_id: str | None = None, project_dir: str | None = None, max_tokens: int = 8000, tools: ToolRegistry | None = None):
        self.registry = registry
        self.provider = registry.get(provider_name)
        self.assembler = ContextAssembler(model=self.provider.model, max_tokens=max_tokens)
        self.summarizer = Summarizer(llm=self.provider)
        self.tools = tools or ToolRegistry()
        self.last_stats: dict = {}
        self.project_path = os.path.abspath(project_path)
        # 若直接傳入 project_dir（已有專案），就不重新計算
        self.project_dir = project_dir or get_project_dir(project_path)
        self.session_id = session_id or uuid.uuid4().hex[:8]

        # 建立專案資料夾並儲存原始路徑
        os.makedirs(self.project_dir, exist_ok=True)
        meta_path = os.path.join(self.project_dir, "project.json")
        if not os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"path": self.project_path}, f, ensure_ascii=False)

        # 載入 system prompt
        system_prompt = self._load_system_prompt()

        # 載入長期記憶摘要
        self.summary: str = self._load_summary()

        # 載入對話歷史
        self.messages: list[Message] = [Message(role="system", content=system_prompt)]
        self._load_history()

    def _load_system_prompt(self) -> str:
        """讀取 SYSTEM.md 作為 system prompt"""
        system_md = os.path.join(self.project_dir, "SYSTEM.md")
        if os.path.exists(system_md):
            with open(system_md, "r", encoding="utf-8") as f:
                return f.read().strip()
        # 不存在則建立預設
        with open(system_md, "w", encoding="utf-8") as f:
            f.write(DEFAULT_SYSTEM_PROMPT)
        return DEFAULT_SYSTEM_PROMPT

    @property
    def _session_path(self) -> str:
        return os.path.join(self.project_dir, f"{self.session_id}.jsonl")

    @property
    def _summary_path(self) -> str:
        return os.path.join(self.project_dir, f"{self.session_id}.summary.md")

    def _load_summary(self) -> str:
        if os.path.exists(self._summary_path):
            with open(self._summary_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def _save_summary(self):
        with open(self._summary_path, "w", encoding="utf-8") as f:
            f.write(self.summary)

    def _load_history(self):
        """從 JSONL 載入完整對話歷史，由 ContextAssembler 決定實際送進 LLM 的範圍"""
        path = self._session_path
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("role") in ("user", "assistant"):
                        self.messages.append(Message(role=entry["role"], content=entry["content"]))
                except json.JSONDecodeError:
                    continue

    def _append_log(self, role: str, content: str):
        """追加一行到 JSONL"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        with open(self._session_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _prepare_context(self, user_input: str) -> list[Message]:
        """共用邏輯：加入 user 訊息、log、組裝 context"""
        self.messages.append(Message(role="user", content=user_input))
        self._append_log("user", user_input)

        assembled, stats = self.assembler.assemble(
            self.messages[0], self.messages[1:], summary=self.summary,
        )
        self.last_stats = stats

        logging.info(">>> Context 組裝：included=%d, dropped=%d, tokens=%d",
                     stats["included"], stats["dropped"], stats["total_tokens"])
        logging.info(">>> 送出給模型的 messages:\n%s",
                     json.dumps([m.to_dict() for m in assembled], ensure_ascii=False, indent=2))
        return assembled

    def _finalize(self, reply: str):
        """共用邏輯：記錄回應、觸發摘要"""
        logging.info("<<< 模型回應:\n%s", reply)
        self.messages.append(Message(role="assistant", content=reply))
        self._append_log("assistant", reply)
        self._maybe_summarize()

    def chat(self, user_input: str) -> str:
        """送出訊息，執行 ReAct loop（LLM → 工具 → LLM → ... → 最終回答）"""
        assembled = self._prepare_context(user_input)
        tools_schema = self.tools.list_schemas() if self.tools else None

        for i in range(self.MAX_ITERATIONS):
            response = self.provider.chat(assembled, tools=tools_schema)

            # 沒有工具呼叫 → 就是最終回答
            if not response.tool_calls:
                self._finalize(response.content)
                return response.content

            # 有工具呼叫 → 執行並把結果餵回去
            assistant_msg = Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            assembled.append(assistant_msg)

            for call in response.tool_calls:
                tool_name = call["function"]["name"]
                try:
                    args = json.loads(call["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                logging.info(">>> [iter %d] Tool call: %s(%s)", i, tool_name, args)

                try:
                    result = self.tools.get(tool_name)(**args)
                except Exception as e:
                    result = f"錯誤：{e}"

                logging.info("<<< [iter %d] Tool result: %s", i, str(result)[:500])

                assembled.append(Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=call["id"],
                    name=tool_name,
                ))

        # 達到最大迭代次數
        fallback = "（ReAct loop 達到最大迭代次數，終止）"
        self._finalize(fallback)
        return fallback

    def chat_stream(self, user_input: str) -> Iterator[str]:
        """串流送出訊息，逐 token 產出，結束後自動記錄"""
        assembled = self._prepare_context(user_input)
        full_response = ""
        for token in self.provider.stream(assembled):
            full_response += token
            yield token
        self._finalize(full_response)

    def _maybe_summarize(self):
        """訊息數超過閾值時，把最舊的一半壓縮成摘要，並從記憶中移除（JSONL 保留）"""
        history_count = len(self.messages) - 1  # 扣掉 system
        if history_count <= self.SUMMARIZE_THRESHOLD:
            return

        half = history_count // 2
        old_messages = self.messages[1:1 + half]

        logging.info(">>> 觸發摘要：壓縮最舊 %d 條訊息", len(old_messages))
        self.summary = self.summarizer.summarize(old_messages, existing=self.summary)
        self._save_summary()
        logging.info("<<< 新摘要:\n%s", self.summary)

        # 從記憶中移除已摘要的舊訊息
        self.messages = [self.messages[0]] + self.messages[1 + half:]

    def list_sessions(self) -> list[dict]:
        """列出當前專案的所有 session"""
        sessions = []
        for f in sorted(os.listdir(self.project_dir)):
            if f.endswith(".jsonl"):
                sid = f.replace(".jsonl", "")
                filepath = os.path.join(self.project_dir, f)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                sessions.append({"id": sid, "modified": mtime.strftime("%Y-%m-%d %H:%M")})
        return sessions

    def clear_history(self):
        """清除記憶中的對話歷史與摘要（JSONL 保留）"""
        system_msg = self.messages[0]
        self.messages = [system_msg]
        self.summary = ""
        if os.path.exists(self._summary_path):
            os.remove(self._summary_path)
