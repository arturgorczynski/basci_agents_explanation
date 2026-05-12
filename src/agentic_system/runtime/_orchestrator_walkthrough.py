from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from agents_training_facility import agents, personalities
from memory.conversation_history import ConversationHistory
from memory.memory_manager import Memory
from runtime.contracts import ToolResult, make_json_safe
from tools import data_manager as data_manager_tools


"""
Documentation-only walkthrough of the agentic runtime.

This file mirrors the important control flow from `orchestrator.py`, but removes
UI tracing, console output, colored messages, sleeps, and display concerns.

Use this file to explain the runtime to the team:

1. A user request starts a new active request in ConversationHistory.
2. The manager sees the planner context and chooses the next action.
3. The manager can answer directly, ask the user, delegate to a worker, or finish.
4. Workers receive one manager instruction and their own assignment history.
5. Workers either call tools or return `done` with findings for the manager.
6. When enough evidence exists, the manager synthesizes the final answer.
"""


PromptInput = Callable[[str], str]

_MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
CONVERSATION_HISTORY_PATH = str(_MEMORY_DIR / "conversation_history.json")
CONVERSATION_RAW_EVENTS_PATH = str(_MEMORY_DIR / "conversation_raw_events.json")


class AgentOrchestrator:
    EXIT_COMMANDS = {"q", "quit", "exit", "bye", "no", "thanks", "thank you"}

    def __init__(
        self,
        manager,
        agents_dict: dict[str, object],
        *,
        steps_to_track: int = 15,
        max_iterations: int = 12,
        max_worker_steps: int = 6,
        input_func: PromptInput = input,
    ):
        # The manager plans the work. The workers actually use tools.
        self.manager = manager
        self.agents_dict = agents_dict

        # Limits protect the runtime from looping forever.
        self.steps_to_track = steps_to_track
        self.max_iterations = max_iterations
        self.max_worker_steps = max_worker_steps
        self.input_func = input_func

        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.conversation_history = ConversationHistory(
            CONVERSATION_HISTORY_PATH,
            CONVERSATION_RAW_EVENTS_PATH,
            self.session_id,
        )

    def _planner_context(self, last_n: int | None = None) -> str:
        # This is the manager's view of the world: user request, clarifications,
        # previous manager choices, worker handoffs, and compact older history.
        return self.conversation_history.render_planner_context(last_n=last_n)

    def _make_event(self, event_type: str, **payload) -> dict:
        # ConversationHistory stores plain event dictionaries. Those events later
        # become the planner context the manager reads.
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "event_type": event_type,
            **payload,
        }

    def _record_step(self, event_type: str, **payload) -> None:
        # Every important runtime decision is stored so the manager can reason
        # from the actual execution history instead of guessing.
        event = self._make_event(event_type, **payload)
        self.conversation_history.record_event(event)
        self._save_conversation_history()

    def _talk_with_user(self, question: str) -> str:
        # Only the manager is allowed to ask the user follow-up questions.
        # Workers never talk to the user directly.
        prompt = (
            f"Manager needs more information.\n"
            f"Question: {question}\n> "
        )
        user_reply = self.input_func(prompt)
        self.conversation_history.add_clarification(question, user_reply)
        self._record_step(
            "user_clarification",
            question=question,
            answer=user_reply,
        )
        return user_reply

    def _run_synthesis(self) -> str:
        # The manager switches from planning mode to answer-writing mode.
        # It receives the full planner context and writes the final response.
        final_answer = self.manager.synthesize_answer(self._planner_context())
        self._record_step("final_answer", answer=final_answer)
        return final_answer

    def _fallback_request_summary(self) -> str:
        return (
            "The request was completed and a final answer was produced after "
            f"{self.conversation_history.active_step_count()} recorded steps."
        )

    def _summarize_active_request(self, _final_answer: str) -> str:
        active_request = self.conversation_history.active_request_snapshot()
        if active_request is None:
            return self._fallback_request_summary()

        question = str(active_request.get("question") or "").strip()
        if question:
            return f"User asked: {question!r}. Final answer was provided."
        return self._fallback_request_summary()

    def _finalize_completed_request(self, final_answer: str) -> None:
        # Once an answer exists, the active request becomes a completed request.
        # Completed requests can later be shown as recent context or compacted.
        self.conversation_history.complete_request(
            final_answer=final_answer,
            summary=self._summarize_active_request(final_answer),
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._maybe_compact_completed_history()
        self._save_conversation_history()

    def _fallback_history_window_summary(
        self,
        previous_summary: str,
        completed_requests: list[dict],
    ) -> str:
        parts: list[str] = []
        if previous_summary.strip():
            parts.append(previous_summary.strip())

        for request in completed_requests:
            parts.append(
                "Request "
                f"{request.get('request_id')}: user asked {request.get('question')!r}; "
                f"outcome: {request.get('summary') or 'completed'}."
            )
        return " ".join(parts).strip()

    def _maybe_compact_completed_history(self) -> None:
        # Long conversations can get expensive. This compacts older completed
        # requests into a short rolling summary when enough requests accumulate.
        summary_window = self.conversation_history.next_history_summary_window()
        if not summary_window:
            return

        previous_summary = self.conversation_history.history_summary
        summary_text = self._fallback_history_window_summary(
            previous_summary,
            summary_window,
        )
        self.conversation_history.apply_history_summary(
            summary_text,
            summarized_through_request_id=summary_window[-1]["request_id"],
        )

    def _should_exit(self, user_input: str) -> bool:
        return user_input.strip().lower() in self.EXIT_COMMANDS

    def _prompt_for_next_request(self) -> str | None:
        # After one request finishes, the same runtime can accept another one.
        next_request = self.input_func("Send the next request: ")
        if self._should_exit(next_request):
            self._record_step("conversation_end", user_input=next_request)
            self._save_execution_history()
            return None
        return next_request

    def _save_execution_history(self) -> None:
        # This simple text file is the human-readable planner context snapshot.
        if self.conversation_history.active_request_snapshot() is None:
            return
        with open("memory.txt", "w", encoding="utf-8") as history_file:
            history_file.write(self._planner_context(last_n=self.steps_to_track))

    def _save_conversation_history(self) -> None:
        # ConversationHistory writes both normalized state and raw event history.
        self.conversation_history.save()

    def _reset_conversation_state(self) -> None:
        # A fresh run starts with a fresh session id and no active request state.
        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        if os.path.exists("memory.txt"):
            os.remove("memory.txt")
        if os.path.exists(CONVERSATION_HISTORY_PATH):
            os.remove(CONVERSATION_HISTORY_PATH)
        if os.path.exists(CONVERSATION_RAW_EVENTS_PATH):
            os.remove(CONVERSATION_RAW_EVENTS_PATH)

        self.conversation_history = ConversationHistory(
            CONVERSATION_HISTORY_PATH,
            CONVERSATION_RAW_EVENTS_PATH,
            self.session_id,
        )

    def _assignment_history_text(self, assignment_history: Memory) -> str:
        # Workers do not receive the whole global history. They only see the
        # manager instruction plus this short history of their own assignment.
        items = assignment_history.recall_raw()
        if not items:
            return "No assignment steps yet."

        lines: list[str] = []
        for index, item in enumerate(items, start=1):
            event_type = item.get("event_type")
            if event_type == "worker_action":
                action = item.get("action", {})
                lines.append(
                    f"{index}. Worker step {item.get('step')}: chose {action.get('type')}."
                )
            elif event_type == "tool_result":
                result = item.get("result", {})
                status = "success" if result.get("success") else "failure"
                summary = result.get("summary") or result.get("error") or "No summary."
                data = result.get("data")
                error = result.get("error")
                line = f"{index}. Tool {item.get('tool')} -> {status}: {summary}"
                if data not in (None, "", [], {}):
                    line += f" | Data: {make_json_safe(data)}"
                if error:
                    line += f" | Error: {error}"
                lines.append(line)
            elif event_type == "worker_done":
                request_results = item.get("request_results") or "No handoff provided."
                request_raw_data = item.get("request_raw_data")
                if request_raw_data not in (None, "", [], {}):
                    lines.append(
                        f"{index}. Worker completed: {request_results} | Raw data: {make_json_safe(request_raw_data)}"
                    )
                    continue
                lines.append(f"{index}. Worker completed: {request_results}")
            else:
                lines.append(f"{index}. {event_type}")
        return "\n".join(lines)

    def _record_assignment_event(
        self,
        assignment_history: Memory,
        event_type: str,
        **payload,
    ) -> None:
        assignment_history.extend_memory(self._make_event(event_type, **payload))

    def _run_worker_session(self, agent_name: str, active_agent, instruction: str) -> str:
        # A worker session is a small loop. The worker can call tools, observe
        # their results, and eventually return `done` to hand facts back.
        assignment_history = Memory(is_structured=True)

        for worker_step in range(1, self.max_worker_steps + 1):
            worker_action = active_agent.think_in_session(
                manager_instruction=instruction,
                assignment_history=self._assignment_history_text(assignment_history),
            )
            self._record_assignment_event(
                assignment_history,
                "worker_action",
                agent=agent_name,
                step=worker_step,
                action=worker_action,
            )
            self._record_step(
                "worker_action",
                agent=agent_name,
                instruction=instruction,
                step=worker_step,
                action=worker_action,
            )

            if worker_action["type"] == "done":
                self._record_assignment_event(
                    assignment_history,
                    "worker_done",
                    agent=agent_name,
                    step=worker_step,
                    request_results=worker_action["request_results"],
                    request_raw_data=worker_action.get("request_raw_data"),
                )
                self._record_step(
                    "worker_done",
                    agent=agent_name,
                    instruction=instruction,
                    steps_taken=worker_step,
                    request_results=worker_action["request_results"],
                    request_raw_data=worker_action.get("request_raw_data"),
                    assignment_history=assignment_history.recall_raw(),
                )
                return "done"

            # If the worker chose a tool, the agent object executes that tool
            # and returns a standard ToolResult.
            tool_result = active_agent.execute_tool(worker_action)
            if not isinstance(tool_result, ToolResult):
                tool_result = ToolResult.failure(
                    error="Tool execution returned an unexpected result type.",
                    data=tool_result,
                )

            self._record_assignment_event(
                assignment_history,
                "tool_result",
                agent=agent_name,
                step=worker_step,
                tool=worker_action["tool"],
                args=worker_action.get("args", {}),
                result={
                    "success": tool_result.success,
                    "summary": tool_result.summary,
                    "error": tool_result.error,
                    "data": make_json_safe(tool_result.data),
                },
            )
            self._record_step(
                "tool_result",
                agent=agent_name,
                instruction=instruction,
                step=worker_step,
                tool=worker_action["tool"],
                args=worker_action.get("args", {}),
                success=tool_result.success,
                summary=tool_result.summary,
                error=tool_result.error,
                data=make_json_safe(tool_result.data),
            )
            self._save_execution_history()

        self._record_step(
            "worker_budget_exhausted",
            agent=agent_name,
            instruction=instruction,
            max_worker_steps=self.max_worker_steps,
            assignment_history=assignment_history.recall_raw(),
        )
        return "budget_exhausted"

    def run(self, initial_request: str | None = None) -> str | None:
        # Outer loop: one runtime session can handle many user requests.
        self._reset_conversation_state()
        user_request = initial_request or self.input_func(
            "Hello user, I am here to assist. Please tell how can I help you?: "
        )
        last_answer: str | None = None

        while True:
            self.conversation_history.start_request(
                user_request,
                started_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._record_step("user_request", request=user_request)

            request_finished = False

            # Inner loop: the manager repeatedly picks the next best action for
            # the current request until the request is answered or the budget ends.
            for count in range(1, self.max_iterations + 1):
                planner_action = self.manager.plan_next_step(
                    self._planner_context(last_n=self.steps_to_track),
                )
                self._record_step(
                    "planner_action",
                    iteration=count,
                    action=planner_action,
                )

                if planner_action["type"] == "answer_user":
                    last_answer = planner_action["answer"]
                    self._record_step("final_answer", answer=last_answer)
                    self._finalize_completed_request(last_answer)
                    request_finished = True
                    break

                if planner_action["type"] == "talk_with_user":
                    self._talk_with_user(planner_action["question"])
                    continue

                if planner_action["type"] == "finish":
                    last_answer = self._run_synthesis()
                    self._finalize_completed_request(last_answer)
                    request_finished = True
                    break

                # Delegate means the manager chose a named worker agent and gave
                # it one self-contained instruction.
                active_agent = self.agents_dict.get(planner_action["agent"])
                if active_agent is None:
                    self._record_step("routing_error", agent=planner_action["agent"])
                    continue

                session_status = self._run_worker_session(
                    planner_action["agent"],
                    active_agent,
                    planner_action["instruction"],
                )
                if session_status == "done":
                    continue

            if not request_finished:
                self._record_step("runtime_stop", reason="Maximum number of steps reached.")
                self._save_execution_history()
                return last_answer

            self._save_execution_history()
            next_request = self._prompt_for_next_request()
            if next_request is None:
                return last_answer

            user_request = next_request


def build_default_runtime(
    *,
    input_func: PromptInput = input,
    max_worker_steps: int = 6,
) -> AgentOrchestrator:
    # Startup prepares the local document vector DB because the data_manager
    # worker depends on it for document search.
    vector_db_result = data_manager_tools.ensure_documents_vector_db()
    if not vector_db_result.success:
        raise RuntimeError(
            f"Vector DB initialization failed before runtime start: {vector_db_result.error}"
        )

    manager = agents.CommandCentre(
        "manager",
        [],
        personalities.brain_desc,
        personalities.brain_system,
    )
    python_developer = agents.Agent(
        "pythondeveloper",
        ["programer"],
        personalities.python_developer_desc,
        personalities.python_developer_system,
    )
    secretary = agents.Agent(
        "secretary",
        ["file_handler"],
        personalities.secretary_desc,
        personalities.secretary_system,
    )
    data_manager_agent = agents.Agent(
        "data_manager",
        ["data_manager"],
        personalities.data_manager_desc,
        personalities.data_manager_system,
    )
    api_agent = agents.Agent(
        "api",
        ["apis"],
        personalities.api_desc,
        personalities.api_system,
    )

    agents_dict = {
        manager.name: manager,
        python_developer.name: python_developer,
        secretary.name: secretary,
        data_manager_agent.name: data_manager_agent,
        api_agent.name: api_agent,
    }

    return AgentOrchestrator(
        manager,
        agents_dict,
        input_func=input_func,
        max_worker_steps=max_worker_steps,
    )
