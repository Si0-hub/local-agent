import ollama
import json
import os
import subprocess
import glob


# ===== 工具定義 =====

def read_file(path: str) -> str:
    """讀取檔案內容"""
    try:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return f"錯誤：檔案不存在 → {path}"
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (檔案過大，僅顯示前 10000 字元)"
        return content
    except Exception as e:
        return f"讀取失敗：{e}"


def search_files(pattern: str, directory: str = ".") -> str:
    """搜尋符合 pattern 的檔案（支援 glob 模式）"""
    try:
        directory = os.path.abspath(directory)
        matches = glob.glob(os.path.join(directory, "**", pattern), recursive=True)
        if not matches:
            return f"沒有找到符合 '{pattern}' 的檔案"
        result = f"找到 {len(matches)} 個檔案：\n"
        for m in matches[:50]:
            result += f"  {m}\n"
        if len(matches) > 50:
            result += f"  ... 還有 {len(matches) - 50} 個檔案"
        return result
    except Exception as e:
        return f"搜尋失敗：{e}"


def search_content(keyword: str, directory: str = ".", file_ext: str = "*") -> str:
    """在檔案中搜尋包含關鍵字的行"""
    try:
        directory = os.path.abspath(directory)
        pattern = os.path.join(directory, "**", f"*.{file_ext}" if file_ext != "*" else "*")
        files = glob.glob(pattern, recursive=True)
        results = []
        for filepath in files:
            if os.path.isdir(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if keyword.lower() in line.lower():
                            results.append(f"{filepath}:{i}: {line.rstrip()}")
                            if len(results) >= 30:
                                break
            except Exception:
                continue
            if len(results) >= 30:
                break
        if not results:
            return f"沒有找到包含 '{keyword}' 的內容"
        return f"找到 {len(results)} 筆結果：\n" + "\n".join(results)
    except Exception as e:
        return f"搜尋失敗：{e}"


def list_directory(path: str = ".") -> str:
    """列出目錄內容"""
    try:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return f"錯誤：不是有效的目錄 → {path}"
        entries = os.listdir(path)
        result = f"目錄：{path}\n"
        dirs = []
        files = []
        for e in sorted(entries):
            full = os.path.join(path, e)
            if os.path.isdir(full):
                dirs.append(f"  📁 {e}/")
            else:
                size = os.path.getsize(full)
                files.append(f"  📄 {e}  ({_format_size(size)})")
        result += "\n".join(dirs + files)
        return result
    except Exception as e:
        return f"列出目錄失敗：{e}"


def run_command(command: str) -> str:
    """執行系統指令"""
    # 安全檢查：封鎖危險指令
    dangerous = ["rm -rf /", "format c:", "del /f /s /q c:", "shutdown", "mkfs"]
    for d in dangerous:
        if d.lower() in command.lower():
            return f"封鎖危險指令：{command}"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.getcwd(),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        if result.returncode != 0:
            output += f"\n[返回碼: {result.returncode}]"
        return output.strip() if output.strip() else "(指令執行完成，無輸出)"
    except subprocess.TimeoutExpired:
        return "錯誤：指令執行超時（30 秒）"
    except Exception as e:
        return f"執行失敗：{e}"


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ===== 工具清單（給模型看的） =====

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "讀取指定檔案的內容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "檔案路徑"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "搜尋符合 pattern 的檔案名稱（支援 glob 模式，例如 *.py）",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "檔案名稱模式，如 *.py, *.txt"},
                    "directory": {"type": "string", "description": "搜尋目錄，預設為目前目錄"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "在檔案內容中搜尋包含關鍵字的行",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "要搜尋的關鍵字"},
                    "directory": {"type": "string", "description": "搜尋目錄，預設為目前目錄"},
                    "file_ext": {"type": "string", "description": "限定副檔名，如 py、txt，預設為 *（全部）"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出指定目錄中的檔案和資料夾",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目錄路徑，預設為目前目錄"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "執行系統終端指令（如 git status, python script.py, dir 等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要執行的指令"},
                },
                "required": ["command"],
            },
        },
    },
]

# 工具名稱對應函式
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "search_files": search_files,
    "search_content": search_content,
    "list_directory": list_directory,
    "run_command": run_command,
}

SYSTEM_PROMPT = """你是一個本地 AI 助手，運行在 Windows 系統上。你必須自己用工具完成任務，絕對不要叫使用者自己去做。
"""


class Agent:
    def __init__(self, model: str = "qwen3:4b"):
        self.model = model
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        # 呼叫模型
        response = ollama.chat(
            model=self.model,
            messages=self.messages,
            tools=TOOLS,
        )

        msg = response["message"]

        # 處理工具呼叫（可能多輪）
        while msg.get("tool_calls"):
            self.messages.append(msg)

            for tool_call in msg["tool_calls"]:
                func_name = tool_call["function"]["name"]
                func_args = tool_call["function"]["arguments"]

                print(f"  🔧 執行工具：{func_name}({func_args})")

                if func_name in TOOL_FUNCTIONS:
                    result = TOOL_FUNCTIONS[func_name](**func_args)
                else:
                    result = f"未知工具：{func_name}"

                self.messages.append({
                    "role": "tool",
                    "content": result,
                })

            # 讓模型根據工具結果繼續回應
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=TOOLS,
            )
            msg = response["message"]

        # 最終回應
        self.messages.append(msg)
        return msg.get("content", "")

    def clear_history(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        print("  對話記錄已清除。")
