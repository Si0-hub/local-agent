import ollama
import json
import os
import uuid
import logging
from datetime import datetime

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
    def __init__(self, model: str, project_path: str, session_id: str | None = None, project_dir: str | None = None):
        self.model = model
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

        # 載入對話歷史
        self.messages = [{"role": "system", "content": system_prompt}]
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

    def _load_history(self):
        """從 JSONL 載入對話歷史，只取最近 20 輪（40 條訊息）"""
        path = self._session_path
        if not os.path.exists(path):
            return

        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("role") in ("user", "assistant"):
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        # 只取最近 20 輪（40 條）
        recent = entries[-40:]
        for entry in recent:
            self.messages.append({"role": entry["role"], "content": entry["content"]})

    def _append_log(self, role: str, content: str):
        """追加一行到 JSONL"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        with open(self._session_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def chat(self, user_input: str) -> str:
        """送出訊息，取得回應"""
        self.messages.append({"role": "user", "content": user_input})
        self._append_log("user", user_input)

        logging.info(">>> 送出給模型的 messages:\n%s", json.dumps(self.messages, ensure_ascii=False, indent=2))

        response = ollama.chat(
            model=self.model,
            messages=self.messages,
        )

        reply = response["message"]["content"]
        logging.info("<<< 模型回應:\n%s", reply)

        self.messages.append({"role": "assistant", "content": reply})
        self._append_log("assistant", reply)
        return reply

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
        """清除記憶中的對話歷史（JSONL 保留）"""
        system_prompt = self.messages[0]["content"]
        self.messages = [{"role": "system", "content": system_prompt}]
