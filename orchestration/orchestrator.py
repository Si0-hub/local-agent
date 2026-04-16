import logging
from typing import Callable

from providers import LLM
from tools import ToolRegistry
from .planner import PlannerAgent
from .executor import ExecutorAgent
from .verifier import VerifierAgent
from .types import Plan, StepResult, Verdict


class Orchestrator:
    """指揮 Planner / Executor / Verifier 協作完成任務。

    自己不呼叫 LLM，只負責流程控制、狀態管理、重試。
    """

    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        verifier_tools: ToolRegistry | None = None,
        max_retries: int = 1,
    ):
        self.planner = PlannerAgent(llm)
        self.executor = ExecutorAgent(llm, tools)
        self.verifier = VerifierAgent(llm, verifier_tools or tools)
        self.max_retries = max_retries

    def run(self, task: str, on_event: Callable[[str, dict], None] | None = None) -> dict:
        """執行任務，回傳結果 dict。

        on_event: 進度回報 callback, 呼叫形式 (kind, payload)
        kind 可能值：plan_start, plan_done, step_start, step_done,
                    verify_start, verify_done, retry, finish
        """
        def emit(kind: str, payload: dict):
            if on_event:
                on_event(kind, payload)

        current_task = task
        plan: Plan = Plan()
        results: list[StepResult] = []
        verdict: Verdict = Verdict(ok=False)

        for attempt in range(self.max_retries + 1):
            # 1. 規劃
            emit("plan_start", {"task": current_task, "attempt": attempt})
            plan = self.planner.plan(current_task)
            logging.info("[Orchestrator] plan: %s", plan.steps)
            emit("plan_done", {"plan": plan})

            if not plan:
                verdict = Verdict(ok=False, feedback="Planner 未產生任何步驟")
                break

            # 2. 執行
            results = []
            for i, step in enumerate(plan.steps):
                emit("step_start", {"index": i, "step": step})
                result = self.executor.execute(step, prior_results=results)
                results.append(result)
                emit("step_done", {"index": i, "result": result})

            # 3. 驗證
            emit("verify_start", {})
            verdict = self.verifier.verify(task, plan, results)
            emit("verify_done", {"verdict": verdict})

            if verdict.ok:
                break

            # 4. 失敗 → 把失敗原因塞進下一輪的任務描述
            if attempt < self.max_retries:
                emit("retry", {"feedback": verdict.feedback})
                current_task = f"{task}\n\n（前次嘗試失敗的原因：{verdict.feedback}）"

        final = {
            "ok": verdict.ok,
            "task": task,
            "plan": plan,
            "results": results,
            "verdict": verdict,
        }
        emit("finish", final)
        return final
