"""ResearchSession: Session orchestrator tying together all four core modules.

Architecture:
    ResearchSession
        ├── memory: ResearchMemory      — three-layer memory (context / short-term / long-term)
        ├── planner: ResearchPlanner    — task decomposition + topological execution + fallback
        ├── tool_selector: ToolSelector — MCP + script tool routing
        └── reflector: ResearchReflector — four-dimensional result evaluation

User-facing entry point for the economic research agent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from scripts.core.memory import ResearchMemory
from scripts.core.planner import ResearchPlanner, Task, TaskStatus
from scripts.core.reflector import Evaluation, ResearchReflector
from scripts.core.tool_selector import ToolSelection, ToolSelector


# ─── Session State & Status ────────────────────────────────────────────────────


class SessionState(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class SessionStatus:
    """Snapshot of the current session's progress."""
    state: SessionState
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    avg_score: float | None = None


# ─── Session Config ────────────────────────────────────────────────────────────


@dataclass
class SessionConfig:
    """Configuration for a ResearchSession."""
    session_id: str
    user_goal: str
    workspace_root: Path = Path(".")
    auto_save: bool = True
    max_context_items: int = 20
    max_retries: int = 3
    model: str = "cursor"          # cursor | deepseek | b_ai
    verbose: bool = False
    db_path: str | None = None     # override default .cache/research.db


# ─── ResearchSession ───────────────────────────────────────────────────────────


class ResearchSession:
    """
    Session orchestrator that ties together all four core modules.

    This is the main user-facing entry point for the economic research agent.
    It manages the lifecycle of a research session: decomposition, execution,
    evaluation, and persistence.

    Example usage:
        session = ResearchSession(SessionConfig(
            session_id="茅台财务分析_20260523",
            user_goal="分析贵州茅台2024年财务数据和投资价值",
        ))
        result = session.run("帮我分析茅台的ROE和毛利率")
        print(result["summary"])

        # Follow-up question
        followup = session.ask("再对比一下五粮液")

        # Resume later
        restored = ResearchSession.resume("茅台财务分析_20260523")
    """

    def __init__(self, config: SessionConfig):
        self.config = config
        self.memory = ResearchMemory(
            session_id=config.session_id,
            db_path=config.db_path,
        )
        self.planner = ResearchPlanner(self.memory)
        self.tool_selector = ToolSelector(self.memory)
        self.reflector = ResearchReflector(self.memory)
        self._task_results: dict[str, Any] = {}
        self._state = SessionState.CREATED
        self._created_at = time.time()

    # ── Lifecycle Methods ──────────────────────────────────────────────────────

    def run(self, user_request: str) -> dict[str, Any]:
        """
        Execute a complete research session.

        Main flow:
        1. Planner.decompose(user_request) → task graph
        2. Topological execution of each Task:
           a. ToolSelector.select() → list of ToolSelection
           b. ToolSelector.execute(primary_selection) → ToolResult
           c. Reflection.evaluate() → Evaluation
           d. Memory.push() → store context
           e. Planner._fallback() if failed (up to max_retries)
        3. Return {session_id, tasks, summary, status}

        Parameters
        ----------
        user_request : str
            The user's research request or instruction.

        Returns
        -------
        dict[str, Any]
            {
                "session_id": str,
                "tasks": dict[str, dict],   # task_id → {result, evaluation}
                "summary": str,              # reflector.reflect() output
                "status": SessionStatus,
            }
        """
        self._state = SessionState.RUNNING

        # Decompose user request into task graph
        tasks = self.planner.decompose(user_request)
        if self.config.verbose:
            print(f"[ResearchSession] Decomposed into {len(tasks)} root tasks")

        # Flatten all tasks (including subtasks) for execution
        all_tasks = self._flatten_tasks(tasks)

        # Execute in topological order using planner's sort
        sorted_tasks = self._topological_order(all_tasks)

        for task in sorted_tasks:
            # Check dependencies — skip if not ready
            if not self._dependencies_ready(task, sorted_tasks):
                task.status = TaskStatus.BLOCKED
                continue

            task.status = TaskStatus.RUNNING
            context = self.memory.get_context(
                limit=self.config.max_context_items
            )

            # Step a: Tool selection
            selections = self.tool_selector.select(task, context)
            if not selections:
                # No tool available — treat as soft failure
                if self.config.verbose:
                    print(f"[ResearchSession] No tool found for task {task.id}")
                evaluation = self._create_empty_evaluation(task)
                self._task_results[task.id] = {"result": None, "evaluation": evaluation}
                self._write_context(task, None, evaluation)
                task.status = TaskStatus.FAILED
                task.error = "No suitable tool found"
                continue

            # Step b: Execute primary tool (with fallback)
            result = self._execute_with_fallback(task, selections)

            # Step c: Evaluate result
            evaluation = self.reflector.evaluate(task, result, context)

            # Step d: Write to memory
            self._write_context(task, result, evaluation)

            # Step e: Store result
            self._task_results[task.id] = {
                "result": result,
                "evaluation": evaluation,
            }

            # Mark task complete
            if evaluation.success:
                task.status = TaskStatus.DONE
                task.finished_at = time.time()
            else:
                task.status = TaskStatus.FAILED
                task.error = evaluation.feedback

            # Auto-save
            if self.config.auto_save:
                self.save()

        # Session complete
        if any(r.get("evaluation", Evaluation("", False, 0, "", [], [], time.time())).success
               for r in self._task_results.values()):
            self._state = SessionState.COMPLETED
        else:
            self._state = SessionState.FAILED

        # Generate summary
        summary = self.reflector.reflect(self)

        return {
            "session_id": self.config.session_id,
            "tasks": self._task_results,
            "summary": summary,
            "status": self.status(),
        }

    def ask(self, followup: str) -> dict[str, Any]:
        """
        Handle a follow-up / supplementary instruction on the current session.

        Based on the memory context, understands the follow-up in relation to
        the original user goal and continues the research.

        Parameters
        ----------
        followup : str
            The follow-up question or instruction.

        Returns
        -------
        dict[str, Any]
            Same structure as run(), scoped to the follow-up tasks.
        """
        if self._state not in (SessionState.CREATED, SessionState.RUNNING, SessionState.COMPLETED):
            self._state = SessionState.RUNNING

        context = self.memory.get_context(limit=self.config.max_context_items)
        recent_goal = context[-1].task if context else self.config.user_goal

        if self.config.verbose:
            print(f"[ResearchSession.ask] Context: {recent_goal[:60]}...")
            print(f"[ResearchSession.ask] Follow-up: {followup}")

        # Combine follow-up with context for smarter decomposition
        combined_request = f"{recent_goal} + {followup}"

        # Decompose the follow-up
        tasks = self.planner.decompose(f"{self.config.user_goal}。{followup}")
        all_tasks = self._flatten_tasks(tasks)
        sorted_tasks = self._topological_order(all_tasks)

        for task in sorted_tasks:
            if not self._dependencies_ready(task, sorted_tasks):
                task.status = TaskStatus.BLOCKED
                continue

            task.status = TaskStatus.RUNNING
            current_context = self.memory.get_context(limit=self.config.max_context_items)
            selections = self.tool_selector.select(task, current_context)

            if not selections:
                evaluation = self._create_empty_evaluation(task)
                self._task_results[task.id] = {"result": None, "evaluation": evaluation}
                self._write_context(task, None, evaluation)
                task.status = TaskStatus.FAILED
                task.error = "No suitable tool found"
                continue

            result = self._execute_with_fallback(task, selections)
            evaluation = self.reflector.evaluate(task, result, current_context)
            self._write_context(task, result, evaluation)
            self._task_results[task.id] = {"result": result, "evaluation": evaluation}

            if evaluation.success:
                task.status = TaskStatus.DONE
                task.finished_at = time.time()
            else:
                task.status = TaskStatus.FAILED
                task.error = evaluation.feedback

        if self.config.auto_save:
            self.save()

        summary = self.reflector.reflect(self)

        return {
            "session_id": self.config.session_id,
            "tasks": self._task_results,
            "summary": summary,
            "status": self.status(),
            "followup": followup,
        }

    def status(self) -> SessionStatus:
        """
        Return the current session status snapshot.
        """
        completed = 0
        failed = 0
        pending = 0
        scores: list[float] = []

        for task_result in self._task_results.values():
            evaluation: Evaluation | None = task_result.get("evaluation")
            if evaluation is None:
                continue
            if evaluation.success:
                completed += 1
            else:
                failed += 1
            scores.append(evaluation.score)

        for task in self.planner.tasks.values():
            if task.status == TaskStatus.PENDING:
                pending += 1

        avg_score = sum(scores) / len(scores) if scores else None

        return SessionStatus(
            state=self._state,
            completed_tasks=completed,
            failed_tasks=failed,
            pending_tasks=pending,
            avg_score=avg_score,
        )

    def save(self):
        """
        Manually persist the session to disk.
        Delegates to memory.save_session().
        """
        self.memory.save_session()

    @staticmethod
    def resume(session_id: str, db_path: str | None = None) -> "ResearchSession":
        """
        Restore a historical session from SQLite.

        Creates a new ResearchSession with the same session_id, restoring
        memory state from the sessions table.

        Parameters
        ----------
        session_id : str
            The ID of the session to restore.
        db_path : str | None
            Path to the SQLite database. Defaults to .cache/research.db.

        Returns
        -------
        ResearchSession
            A new ResearchSession instance with restored state.
        """
        path = db_path or ".cache/research.db"

        # Restore memory from disk
        memory = ResearchMemory.load_session(session_id, db_path=path)

        # Reconstruct a config from stored state
        # get_context() may be empty if session wasn't saved, but we still create the session
        context = memory.get_context(limit=1)
        user_goal = "Restored session"
        if context:
            # Try to extract goal from first context unit
            user_goal = context[0].task if context else "Restored session"

        config = SessionConfig(
            session_id=session_id,
            user_goal=user_goal,
            workspace_root=Path("."),
            db_path=path,
        )

        session = ResearchSession(config)

        # Restore the memory from the loaded one
        session.memory = memory
        # Re-initialize planner/tool_selector/reflector with restored memory
        session.planner = ResearchPlanner(session.memory)
        session.tool_selector = ToolSelector(session.memory)
        session.reflector = ResearchReflector(session.memory)

        # Restore task results from context if available
        for unit in session.memory.get_context(limit=100):
            if isinstance(unit.result, dict) and "task_id" in unit.result:
                task_id = unit.result["task_id"]
                session._task_results[task_id] = {
                    "result": unit.result.get("result"),
                    "evaluation": None,  # evaluation may not be stored
                }

        # Infer state from context
        if session._task_results:
            session._state = SessionState.COMPLETED
        else:
            session._state = SessionState.CREATED

        return session

    # ── Internal Helpers ───────────────────────────────────────────────────────

    def _execute_with_fallback(
        self,
        task: Task,
        selections: list[ToolSelection],
    ) -> Any:
        """
        Execute a task using tool selections with fallback on failure.

        Tries each tool in priority order until one succeeds or all fail.
        Respects self.config.max_retries for the whole task.
        """
        attempt = 0
        last_error: str | None = None

        while attempt < self.config.max_retries:
            for selection in selections:
                try:
                    result = self.tool_selector.execute(selection, {"task": task})
                    if result.success:
                        return result.output
                    last_error = result.error
                except NotImplementedError:
                    # MCP or script tool not implemented in this environment
                    # Return a mock result so the session can continue
                    return {
                        "task_id": task.id,
                        "task_type": task.task_type.value,
                        "status": "mocked",
                        "note": f"Tool '{selection.tool_name}' not implemented — returning mock result",
                        "attempt": attempt,
                    }
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)

            attempt += 1

        # All tools failed after max_retries
        return {
            "task_id": task.id,
            "task_type": task.task_type.value,
            "status": "failed",
            "error": last_error or "All tool executions failed",
            "attempts": attempt,
        }

    def _create_empty_evaluation(self, task: Task) -> Evaluation:
        """Create a minimal Evaluation for tasks with no tool available."""
        return Evaluation(
            task_id=task.id,
            success=False,
            score=0.0,
            feedback=f"No tool available for task [{task.task_type.value}] {task.description}",
            suggestions=["Install the required tool or MCP server for this task type."],
            quality_flags=["incomplete_output"],
            timestamp=time.time(),
        )

    def _write_context(
        self,
        task: Task,
        result: Any,
        evaluation: Evaluation,
    ):
        """Push task result and evaluation into memory."""
        tools_used: list[str] = []
        if result and isinstance(result, dict):
            # Try to extract tool name from result
            tool_name = result.get("tool_name", "")
            if tool_name:
                tools_used = [tool_name]

        self.memory.push(
            task=task.description,
            result={
                "task_id": task.id,
                "result": result,
                "score": evaluation.score,
                "success": evaluation.success,
            },
            metadata={
                "tools": tools_used,
                "type": "task_complete",
                "evaluation": evaluation.feedback,
                "quality_flags": evaluation.quality_flags,
            },
        )

        # Update the latest context unit's evaluation field
        context = self.memory.get_context(limit=1)
        if context:
            latest = context[-1]
            self.memory.update_evaluation(latest.timestamp, evaluation.feedback)

    def _flatten_tasks(self, tasks: list[Task]) -> list[Task]:
        """Flatten a task tree into a flat list (BFS)."""
        flat = []
        queue = list(tasks)
        while queue:
            t = queue.pop(0)
            flat.append(t)
            queue.extend(t.subtasks)
        return flat

    def _topological_order(self, tasks: list[Task]) -> list[Task]:
        """
        Kahn's topological sort — tasks with no unmet dependencies come first.
        Falls back to planner's sort for task graphs with no duplicates.
        """
        task_map = {t.id: t for t in tasks}
        in_degree = {t.id: 0 for t in tasks}

        # Compute in-degrees
        for t in tasks:
            for dep_id in t.dependencies:
                if dep_id in in_degree:
                    in_degree[t.id] += 1

        ready = [t for t in tasks if in_degree[t.id] == 0]
        sorted_tasks: list[Task] = []

        dependents: dict[str, list[Task]] = {t.id: [] for t in tasks}
        for t in tasks:
            for dep_id in t.dependencies:
                if dep_id in dependents:
                    dependents[dep_id].append(t)

        while ready:
            task = ready.pop(0)
            sorted_tasks.append(task)
            if task.id in dependents:
                for dep in dependents[task.id]:
                    in_degree[dep.id] -= 1
                    if in_degree[dep.id] == 0 and dep not in sorted_tasks and dep not in ready:
                        ready.append(dep)

        # Append any remaining tasks (cycles or orphaned)
        for t in tasks:
            if t not in sorted_tasks:
                sorted_tasks.append(t)

        return sorted_tasks

    def _dependencies_ready(self, task: Task, all_tasks: list[Task]) -> bool:
        """Check whether all dependencies of a task have been executed."""
        if not task.dependencies:
            return True

        completed_ids = {
            t.id for t in all_tasks
            if t.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.BLOCKED)
        }

        return all(dep_id in completed_ids for dep_id in task.dependencies)

    def __repr__(self) -> str:
        return (
            f"ResearchSession(id={self.config.session_id!r}, "
            f"state={self._state.value}, "
            f"tasks={len(self._task_results)})"
        )
