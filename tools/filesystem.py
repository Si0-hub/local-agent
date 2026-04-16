import os
import shutil

from .base import tool


@tool(description="讀取指定路徑的檔案內容，回傳完整文字。用於查看程式碼、文件、設定檔等。")
def read_file(path: str) -> str:
    """讀取檔案"""
    if not os.path.exists(path):
        return f"錯誤：檔案不存在 {path}"
    if not os.path.isfile(path):
        return f"錯誤：{path} 不是檔案"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        return f"錯誤：{path} 不是文字檔（二進位或未知編碼）"
    except Exception as e:
        return f"錯誤：{e}"


@tool(description="列出指定資料夾下的檔案與子資料夾。資料夾會以 / 結尾標示。")
def list_directory(path: str) -> str:
    """列出資料夾"""
    if not os.path.exists(path):
        return f"錯誤：路徑不存在 {path}"
    if not os.path.isdir(path):
        return f"錯誤：{path} 不是資料夾"
    try:
        entries = sorted(os.listdir(path))
    except Exception as e:
        return f"錯誤：{e}"

    if not entries:
        return "（空資料夾）"

    lines = []
    for entry in entries:
        full = os.path.join(path, entry)
        if os.path.isdir(full):
            lines.append(f"{entry}/")
        else:
            lines.append(entry)
    return "\n".join(lines)


@tool(description="在指定檔案中搜尋包含關鍵字的行，回傳行號與該行內容。適合大檔案局部查詢。")
def search_file(path: str, keyword: str) -> str:
    """在檔案中搜尋關鍵字"""
    if not os.path.exists(path) or not os.path.isfile(path):
        return f"錯誤：{path} 不是有效的檔案"
    try:
        matches = []
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if keyword in line:
                    matches.append(f"{i}: {line.rstrip()}")
        return "\n".join(matches) if matches else "（找不到符合的行）"
    except Exception as e:
        return f"錯誤：{e}"


@tool(description="將文字內容寫入指定檔案。若檔案已存在會覆蓋，若父資料夾不存在會自動建立。")
def write_file(path: str, content: str) -> str:
    """寫入檔案"""
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已寫入 {path}（{len(content)} 字元）"
    except Exception as e:
        return f"錯誤：{e}"


@tool(description="建立指定路徑的資料夾（含中間路徑）。若已存在則忽略。")
def make_directory(path: str) -> str:
    """建立資料夾"""
    try:
        os.makedirs(path, exist_ok=True)
        return f"已建立資料夾 {path}"
    except Exception as e:
        return f"錯誤：{e}"


@tool(description="將檔案或資料夾從 src 搬移到 dst，也可用於重新命名。目標父資料夾不存在會自動建立。")
def move_file(src: str, dst: str) -> str:
    """搬移檔案或資料夾"""
    if not os.path.exists(src):
        return f"錯誤：來源不存在 {src}"
    try:
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.move(src, dst)
        return f"已搬移 {src} → {dst}"
    except Exception as e:
        return f"錯誤：{e}"
