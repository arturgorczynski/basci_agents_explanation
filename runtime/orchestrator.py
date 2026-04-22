from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Callable

try:
    from termcolor import colored
except ImportError:  # pragma: no cover - optional dependency fallback
    def colored(text, _color=None):
        return text

from agents_training_facility import agents, personalities
from memory.memory_manager import Memory
from runtime.contracts import ToolResult, make_json_safe, summarize_tool_result

PromptInput = Callable[[str], str]
PromptOutput = Callable[[str], None]

CONVERSATION_HISTORY_PATH = "memory/conversation_history.json"


class AgentOrchestrator:
    EXIT_COMMANDS = {"q", "quit", "exit", "bye", "no", "thanks", "thank you"}

    def __init__(
        self,
        manager,
        agents_dict: dict[str, object],
        *,
        steps_to_track: int = 15,
        max_iterations: int = 12,
        max_worker_steps: int = 4,
        input_func: PromptInput = input,
        output_func: PromptOutput = print,
        sleep_func: Callable[[float], None] = time.sleep,
    ):
        self.manager = manager
        self.agents_dict = agents_dict
        self.steps_to_track = steps_to_track
        self.max_iterations = max_iterations
        self.max_worker_steps = max_worker_steps
        self.input_func = input_func
        self.output_func = output_func
        self.sleep_func = sleep_func

        self.step_history = Memory(is_structured=True)
        self.requests_history = Memory(is_structured=False)
        self.long_history = Memory(is_structured=False)
        self.conversation_history = Memory(is_structured=True)
        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    def _emit(self, message: str, color: str | None = None) -> None:
        if color:
            self.output_func(colored(message, color))
            return
        self.output_func(message)

    def _request_context(self) -> str:
        return self.requests_history.recall_all()

    def _execution_context(self) -> str:
        return self.step_history.recall_all()

    def _make_event(self, event_type: str, **payload) -> dict:
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "event_type": event_type,
            **payload,
        }

    def _record_step(self, event_type: str, **payload) -> None:
        event = self._make_event(event_type, **payload)
        self.step_history.extend_memory(event)
        self.conversation_history.extend_memory(event)
        self._save_conversation_history()

    def _ask_user(self, question: str, reason: str) -> str:
        prompt = (
            f"Manager needs more information.\n"
            f"Reason: {reason}\n"
            f"Question: {question}\n> "
        )
        user_reply = self.input_func(prompt)
        self.requests_history.extend_memory(user_reply)
        self._record_step(
            "user_clarification",
            question=question,
            reason=reason,
            answer=user_reply,
        )
        return user_reply

    def _run_synthesis(self) -> str:
        final_answer = self.manager.synthesize_answer(
            self._request_context(),
            self._execution_context(),
        )
        self._emit(final_answer)
        self._record_step("final_answer", answer=final_answer)
        return final_answer

    def _should_exit(self, user_input: str) -> bool:
        return user_input.strip().lower() in self.EXIT_COMMANDS

    def _prompt_for_next_request(self) -> str | None:
        next_request = self.input_func(
            "Your request has been finished. Shall I help with anything else?: "
        )
        if self._should_exit(next_request):
            self._record_step("conversation_end", user_input=next_request)
            self._save_execution_history()
            return None
        return next_request

    def _save_execution_history(self) -> None:
        with open("memory.txt", "w", encoding="utf-8") as history_file:
            history_file.write(self.step_history.recall_last_actions(self.steps_to_track))

    def _save_conversation_history(self) -> None:
        self.conversation_history.save_history(CONVERSATION_HISTORY_PATH)

    def _reset_conversation_state(self) -> None:
        self.step_history = Memory(is_structured=True)
        self.requests_history = Memory(is_structured=False)
        self.long_history = Memory(is_structured=False)
        self.conversation_history = Memory(is_structured=True)
        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        if os.path.exists("memory.txt"):
            os.remove("memory.txt")

        if os.path.exists(CONVERSATION_HISTORY_PATH):
            os.remove(CONVERSATION_HISTORY_PATH)

    def _assignment_history_text(self, assignment_history: Memory) -> str:
        text = assignment_history.recall_all()
        return text or "No assignment steps yet."

    def _record_assignment_event(self, assignment_history: Memory, event_type: str, **payload) -> None:
        assignment_history.extend_memory(self._make_event(event_type, **payload))

    def _run_worker_session(self, agent_name: str, active_agent, instruction: str) -> str | None:
        assignment_history = Memory(is_structured=True)

        for worker_step in range(1, self.max_worker_steps + 1):
            worker_action = active_agent.think_in_session(
                manager_instruction=instruction,
                execution_history=self.step_history.recall_last_actions(
                    self.steps_to_track + 2
                ),
                assignment_history=self._assignment_history_text(assignment_history),
                user_request=self._request_context(),
                worker_step=worker_step,
                max_worker_steps=self.max_worker_steps,
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

            if worker_action["type"] == "needs_user_input":
                self._ask_user(worker_action["question"], worker_action["reason"])
                return "awaiting_user"

            if worker_action["type"] == "done":
                self._record_assignment_event(
                    assignment_history,
                    "worker_done",
                    agent=agent_name,
                    step=worker_step,
                    summary=worker_action["summary"],
                )
                self._record_step(
                    "worker_done",
                    agent=agent_name,
                    instruction=instruction,
                    steps_taken=worker_step,
                    summary=worker_action["summary"],
                    assignment_history=assignment_history.recall_raw(),
                )
                return "done"

            tool_result = active_agent.execute_tool(worker_action)
            if not isinstance(tool_result, ToolResult):
                tool_result = ToolResult.failure(
                    error="Tool execution returned an unexpected result type.",
                    data=tool_result,
                )

            tool_summary = summarize_tool_result(tool_result)
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
            self._emit(f"| Step Execution | {tool_summary}", "magenta")
            self._emit(" ")
            self._save_execution_history()
            self.sleep_func(0 if self.sleep_func is None else 2)

        self._record_step(
            "worker_budget_exhausted",
            agent=agent_name,
            instruction=instruction,
            max_worker_steps=self.max_worker_steps,
            assignment_history=assignment_history.recall_raw(),
        )
        return "budget_exhausted"

    def run(self, initial_request: str | None = None) -> str | None:
        self._reset_conversation_state()

        user_request = initial_request or self.input_func(
            "Hello user, I am here to assist. Please tell how can I help you?: "
        )
        last_answer: str | None = None

        while True:
            self.requests_history.extend_memory(user_request)
            self._emit(f"| User requested |: {user_request}", "light_blue")
            self._record_step("user_request", request=user_request)

            request_finished = False
            for count in range(1, self.max_iterations + 1):
                self._emit(f"Step {count}")
                planner_action = self.manager.plan_next_step(
                    self._request_context(),
                    self.step_history.recall_last_actions(self.steps_to_track),
                )
                self._record_step(
                    "planner_action",
                    iteration=count,
                    action=planner_action,
                )
                self._emit(f"| Planning Result | Next Step: {planner_action}", "green")

                if planner_action["type"] == "ask_user":
                    self._ask_user(planner_action["question"], planner_action["reason"])
                    continue

                if planner_action["type"] == "finish":
                    last_answer = self._run_synthesis()
                    request_finished = True
                    break

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
                self._emit("Maximum number of steps reached before finishing the task.", "red")
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
    output_func: PromptOutput = print,
    sleep_func: Callable[[float], None] = time.sleep,
    max_worker_steps: int = 4,
) -> AgentOrchestrator:
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
    intern = agents.Agent(
        "intern",
        ["utils_handler"],
        personalities.intern_desc,
        personalities.intern_system,
    )
    api_agent = agents.Agent(
        "api",
        ["apis"],
        personalities.communicator_desc,
        personalities.communicator_system,
    )

    agents_dict = {
        manager.name: manager,
        python_developer.name: python_developer,
        secretary.name: secretary,
        intern.name: intern,
        api_agent.name: api_agent,
    }

    return AgentOrchestrator(
        manager,
        agents_dict,
        input_func=input_func,
        output_func=output_func,
        sleep_func=sleep_func,
        max_worker_steps=max_worker_steps,
    )
