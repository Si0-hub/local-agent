from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from agent import Agent, list_projects
from providers import LLM, ProviderRegistry

console = Console()

# 集中註冊所有 LLM
registry = ProviderRegistry()
registry.register("fast", LLM(model="ollama_chat/qwen3:4b"), default=True)


def select_project() -> dict:
    """讓使用者選擇專案或輸入新路徑，回傳 {"project_path": ..., "project_dir": ...}"""
    projects = list_projects()

    if projects:
        console.print("\n[bold]已有的專案：[/bold]")
        for i, p in enumerate(projects, 1):
            console.print(f"  [cyan]{i}.[/cyan] {p['original_path']}  ({p['sessions']} 個 session)")

    console.print(f"\n輸入編號選擇已有專案，或輸入新的資料夾路徑建立新專案")

    choice = console.input("[bold cyan]專案：[/bold cyan] ").strip()

    # 數字 → 選擇已有專案（直接回傳 project_dir，不重新計算）
    if choice.isdigit() and projects:
        idx = int(choice) - 1
        if 0 <= idx < len(projects):
            p = projects[idx]
            return {"project_path": p["original_path"], "project_dir": p["path"]}

    # 路徑 → 新專案
    import os
    path = os.path.abspath(choice)
    if not os.path.isdir(path):
        console.print(f"[red]路徑不存在：{path}[/red]")
        return select_project()

    return {"project_path": path, "project_dir": None}


def select_session(project_dir: str) -> str | None:
    """讓使用者選擇 session 或建立新的"""
    import os

    if not project_dir or not os.path.exists(project_dir):
        return None

    sessions = []
    for f in sorted(os.listdir(project_dir)):
        if f.endswith(".jsonl"):
            sessions.append(f.replace(".jsonl", ""))

    if not sessions:
        return None

    console.print("\n[bold]已有的 Session：[/bold]")
    for i, sid in enumerate(sessions, 1):
        console.print(f"  [cyan]{i}.[/cyan] {sid}")
    console.print(f"  [cyan]n.[/cyan] 建立新 session")

    choice = console.input("[bold cyan]Session：[/bold cyan] ").strip()

    if choice.lower() == "n" or not choice:
        return None

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            return sessions[idx]

    return None


def main():
    console.print(Panel(
        "[bold green]本地 AI Agent[/bold green]\n"
        f"模型：{registry.get().model}",
        title="🤖 Agent",
    ))

    # 選擇專案
    project_info = select_project()
    project_path = project_info["project_path"]
    project_dir = project_info["project_dir"]

    # 選擇 session
    session_id = select_session(project_dir)

    # 建立 Agent
    agent = Agent(registry=registry, project_path=project_path, session_id=session_id, project_dir=project_dir)

    console.print(Panel(
        f"專案：{agent.project_path}\n"
        f"Session：{agent.session_id}\n\n"
        "指令：\n"
        "  [yellow]/new[/yellow]        建立新 session\n"
        "  [yellow]/sessions[/yellow]   列出所有 session\n"
        "  [yellow]/switch ID[/yellow]  切換 session\n"
        "  [yellow]/clear[/yellow]      清除對話記錄\n"
        "  [yellow]/quit[/yellow]       離開",
        title="🤖 Session",
    ))

    while True:
        try:
            user_input = console.input("\n[bold cyan]你：[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n👋 掰掰！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "exit", "quit"):
            console.print("👋 掰掰！")
            break

        if user_input.lower() == "/clear":
            agent.clear_history()
            console.print("  對話記錄已清除。")
            continue

        if user_input.lower() == "/new":
            agent = Agent(registry=registry, project_path=project_path, project_dir=agent.project_dir)
            console.print(f"  ✅ 新 session：{agent.session_id}")
            continue

        if user_input.lower() == "/sessions":
            sessions = agent.list_sessions()
            if sessions:
                for s in sessions:
                    marker = " ← 目前" if s["id"] == agent.session_id else ""
                    console.print(f"  {s['id']}  ({s['modified']}){marker}")
            else:
                console.print("  （沒有 session）")
            continue

        if user_input.lower().startswith("/switch "):
            sid = user_input[8:].strip()
            if sid:
                agent = Agent(registry=registry, project_path=project_path, session_id=sid, project_dir=agent.project_dir)
                console.print(f"  ✅ 已切換至 session：{agent.session_id}")
            continue

        try:
            response = agent.chat(user_input)
            console.print()
            console.print(Panel(Markdown(response), title="🤖 Agent", border_style="green"))
        except Exception as e:
            console.print(f"\n[red]錯誤：{e}[/red]")


if __name__ == "__main__":
    main()
