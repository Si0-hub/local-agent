from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from agent import Agent

console = Console()


def main():
    console.print(Panel(
        "[bold green]本地 AI Agent[/bold green]\n"
        "模型：qwen3:4b | 功能：對話 / 檔案助手 / 指令執行\n\n"
        "指令：\n"
        "  [yellow]/clear[/yellow]  清除對話記錄\n"
        "  [yellow]/cd 路徑[/yellow]  切換工作目錄\n"
        "  [yellow]/quit[/yellow]   離開",
        title="🤖 Agent",
    ))

    agent = Agent(model="qwen3:4b")

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
            continue

        if user_input.lower().startswith("/cd "):
            import os
            path = user_input[4:].strip()
            try:
                os.chdir(path)
                console.print(f"  工作目錄切換至：{os.getcwd()}")
            except Exception as e:
                console.print(f"  [red]切換失敗：{e}[/red]")
            continue

        try:
            response = agent.chat(user_input)
            console.print()
            console.print(Panel(Markdown(response), title="🤖 Agent", border_style="green"))
        except Exception as e:
            console.print(f"\n[red]錯誤：{e}[/red]")


if __name__ == "__main__":
    main()
