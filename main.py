import os

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from agent import Agent, list_projects
from providers import LLM, Message, ProviderRegistry
from tools import (
    ToolRegistry,
    read_file,
    list_directory,
    search_file,
    write_file,
    make_directory,
    move_file,
)
from orchestration import Orchestrator, Intent, IntentClassifier

console = Console()

# 集中註冊所有 LLM
registry = ProviderRegistry()
registry.register("fast", LLM(model="ollama_chat/qwen3:4b"), default=True)

# 全部工具（含寫入類，給 Executor 用）
tools = ToolRegistry()
tools.register(read_file, list_directory, search_file, write_file, make_directory, move_file)

# 唯讀工具（給 Verifier 用，避免驗證時意外修改檔案）
readonly_tools = ToolRegistry()
readonly_tools.register(read_file, list_directory, search_file)


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


def run_orchestrator(orchestrator: Orchestrator, task: str):
    """執行 Plan → Execute → Verify 流水線，並在 CLI 顯示進度"""
    console.print(Panel(f"[bold]{task}[/bold]", title="🎯 任務", border_style="magenta"))

    def on_event(kind: str, payload: dict):
        if kind == "plan_start":
            attempt = payload["attempt"]
            label = "規劃中" if attempt == 0 else f"重新規劃（第 {attempt + 1} 次）"
            console.print(f"\n[cyan]📋 {label}...[/cyan]")

        elif kind == "plan_done":
            plan = payload["plan"]
            if not plan.steps:
                console.print("  [red]⚠ Planner 沒有產出步驟[/red]")
                return
            console.print("[bold]步驟清單：[/bold]")
            for i, step in enumerate(plan.steps, 1):
                console.print(f"  [dim]{i}.[/dim] {step}")

        elif kind == "step_start":
            console.print(f"\n[cyan]▶ 步驟 {payload['index'] + 1}：{payload['step']}[/cyan]")

        elif kind == "step_done":
            r = payload["result"]
            mark = "[green]✅[/green]" if r.success else "[red]❌[/red]"
            console.print(f"  {mark} {r.output}")

        elif kind == "verify_start":
            console.print("\n[cyan]🔍 驗證中...[/cyan]")

        elif kind == "verify_done":
            v = payload["verdict"]
            if v.ok:
                console.print("  [green]✅ 驗證通過[/green]")
            else:
                console.print(f"  [red]❌ 驗證失敗[/red]：{v.feedback}")

        elif kind == "retry":
            console.print(f"\n[yellow]🔁 準備重試：{payload['feedback']}[/yellow]")

    try:
        result = orchestrator.run(task, on_event=on_event)
    except Exception as e:
        console.print(f"[red]Orchestrator 錯誤：{e}[/red]")
        return None

    # 最終總結
    mark = "[green]✅ 任務完成[/green]" if result["ok"] else "[red]⚠ 任務未完成[/red]"
    console.print(f"\n{mark}")
    if result["verdict"].feedback and not result["ok"]:
        console.print(f"[dim]{result['verdict'].feedback}[/dim]")

    return result


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

    # 切換工作目錄到專案路徑（工具用相對路徑即可操作）
    os.chdir(project_path)

    # 選擇 session
    session_id = select_session(project_dir)

    # 建立 Agent
    agent = Agent(registry=registry, tools=tools, project_path=project_path, session_id=session_id, project_dir=project_dir)

    # 建立 Orchestrator（Plan → Execute → Verify 流水線）
    orchestrator = Orchestrator(
        llm=registry.get(),
        tools=tools,
        verifier_tools=readonly_tools,
        max_retries=1,
    )

    # 建立意圖分類器
    intent_classifier = IntentClassifier(llm=registry.get())

    console.print(Panel(
        f"專案：{agent.project_path}\n"
        f"Session：{agent.session_id}\n\n"
        "指令：\n"
        "  [yellow]/new[/yellow]         建立新 session\n"
        "  [yellow]/sessions[/yellow]    列出所有 session\n"
        "  [yellow]/switch ID[/yellow]   切換 session\n"
        "  [yellow]/clear[/yellow]       清除對話記錄\n"
        "  [yellow]/quit[/yellow]        離開\n\n"
        "提示：現在會自動判斷「詢問」或「執行指令」",
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
            agent = Agent(registry=registry, tools=tools, project_path=project_path, project_dir=agent.project_dir)
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
                agent = Agent(registry=registry, tools=tools, project_path=project_path, session_id=sid, project_dir=agent.project_dir)
                console.print(f"  ✅ 已切換至 session：{agent.session_id}")
            continue

        # 自動判斷意圖
        try:
            with console.status("[dim]正在辨識意圖...[/dim]", spinner="simpleDots"):
                intent = intent_classifier.classify(user_input)
            
            if intent == Intent.DIRECTIVE:
                console.print(f"[dim]⚡ 偵測到執行指令，啟動任務編排...[/dim]")
                result = run_orchestrator(orchestrator, user_input)

                # 把任務結果寫回 agent session，保持對話記憶連貫
                if result:
                    status = "完成" if result["ok"] else "未完成"
                    steps_summary = "\n".join(
                        f"  {i+1}. [{('OK' if r.success else 'FAIL')}] {r.step} → {r.output}"
                        for i, r in enumerate(result["results"])
                    )
                    record = f"[任務執行 - {status}]\n任務：{user_input}\n步驟結果：\n{steps_summary}"
                    agent._append_log("user", user_input)
                    agent._append_log("assistant", record)
                    agent.messages.append(Message(role="user", content=user_input))
                    agent.messages.append(Message(role="assistant", content=record))
            else:
                # 詢問模式
                console.print(f"[dim]💬 偵測到詢問，正在思考回答...[/dim]")
                console.print()
                with console.status("[cyan]思考中...[/cyan]", spinner="dots"):
                    response = agent.chat(user_input)
                console.print(Panel(Markdown(response), title="🤖 Agent", border_style="green"))

                stats = agent.last_stats
                console.print(
                    f"[dim]context: {stats.get('total_tokens', 0)} tokens  |  "
                    f"included: {stats.get('included', 0)}  |  "
                    f"dropped: {stats.get('dropped', 0)}[/dim]"
                )
        except Exception as e:
            console.print(f"\n[red]錯誤：{e}[/red]")


if __name__ == "__main__":
    main()
