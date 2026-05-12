from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class ConversationHistory:
    SUMMARY_TRIGGER_REQUESTS = 7
    SUMMARY_WINDOW_REQUESTS = 5

    def __init__(self, normalized_path: str, raw_path: str, session_id: str):
        self.normalized_path = Path(normalized_path)
        self.raw_path = Path(raw_path)
        self.reset(session_id)

    def reset(self, session_id: str) -> None:
        self.session_id = session_id
        self.completed_requests: list[dict[str, Any]] = []
        self.active_request: dict[str, Any] | None = None
        self.raw_events: list[dict[str, Any]] = []
        self.history_summary = ""
        self.summarized_through_request_id = 0
        self._next_request_id = 1

    def start_request(self, question: str, *, started_at: str) -> None:
        if self.active_request is not None:
            raise ValueError("Cannot start a new request while another request is active.")

        self.active_request = {
            "request_id": self._next_request_id,
            "question": question,
            "clarifications": [],
            "steps": [],
            "started_at": started_at,
        }
        self._next_request_id += 1

    def record_event(self, event: dict[str, Any]) -> None:
        self.raw_events.append(copy.deepcopy(event))
        if self.active_request is not None:
            self.active_request["steps"].append(copy.deepcopy(event))

    def add_clarification(self, question: str, answer: str) -> None:
        if self.active_request is None:
            return

        self.active_request["clarifications"].append(
            {
                "question": question,
                "answer": answer,
            }
        )

    # Events the manager needs to see when planning the next step:
    # his own decisions (planner_action) and what each worker handed back
    # (worker_done / worker_budget_exhausted), plus user-side context.
    # Internal worker tool calls and per-tool results are tracked but hidden
    # from the manager's view — workers report their findings via worker_done.
    _MANAGER_VISIBLE_EVENTS = frozenset(
        {
            "user_request",
            "user_clarification",
            "planner_action",
            "worker_done",
            "worker_budget_exhausted",
            "routing_error",
            "final_answer",
            "runtime_stop",
        }
    )

    def _active_step_records(self, last_n: int | None = None) -> list[dict[str, Any]]:
        if self.active_request is None:
            return []
        steps = [
            step
            for step in self.active_request["steps"]
            if step.get("event_type") in self._MANAGER_VISIBLE_EVENTS
        ]
        if last_n is not None:
            steps = steps[-last_n:]
        records: list[dict[str, Any]] = []
        for step in steps:
            records.extend(self._event_to_manager_records(step))
        return records

    def render_planner_context(self, last_n: int | None = None) -> str:
        """Single unified block for the manager planner / synthesizer.

        Sections (each omitted when empty):
          SUMMARY                       – rolling compaction of older requests
          RECENTLY COMPLETED REQUESTS   – completed requests not yet summarized
          CURRENT REQUEST               – live request as ONE object that
                                          embeds its own EXECUTION_STEPS
        """
        sections: list[str] = []

        if self.history_summary.strip():
            sections.append(f"SUMMARY:\n{self.history_summary.strip()}")

        recent_requests = [
            self._completed_request_context(request)
            for request in self.completed_requests
            if request["request_id"] > self.summarized_through_request_id
        ]
        if recent_requests:
            sections.append(
                "RECENTLY COMPLETED REQUESTS:\n"
                f"{json.dumps(recent_requests, ensure_ascii=False, indent=2, default=str)}"
            )

        if self.active_request is not None:
            current_request = {
                "request_id": self.active_request["request_id"],
                "USER": self.active_request["question"],
                "CLARIFICATIONS": copy.deepcopy(self.active_request["clarifications"]),
                "EXECUTION_STEPS": self._active_step_records(last_n=last_n),
            }
            sections.append(
                "CURRENT REQUEST:\n"
                f"{json.dumps(current_request, ensure_ascii=False, indent=2, default=str)}"
            )

        if not sections:
            return "No active request."
        return "\n\n".join(sections).strip()

    def active_request_snapshot(self) -> dict[str, Any] | None:
        if self.active_request is None:
            return None
        return copy.deepcopy(self.active_request)

    def active_step_count(self) -> int:
        if self.active_request is None:
            return 0
        return len(self.active_request["steps"])

    def complete_request(self, final_answer: str, summary: str, *, completed_at: str) -> None:
        if self.active_request is None:
            return

        completed_request = {
            "request_id": self.active_request["request_id"],
            "question": self.active_request["question"],
            "summary": summary,
            "final_answer": final_answer,
            "started_at": self.active_request["started_at"],
            "completed_at": completed_at,
        }
        self.completed_requests.append(completed_request)
        self.active_request = None

    def next_history_summary_window(self) -> list[dict[str, Any]]:
        unsummarized_requests = [
            request
            for request in self.completed_requests
            if request["request_id"] > self.summarized_through_request_id
        ]
        if len(unsummarized_requests) < self.SUMMARY_TRIGGER_REQUESTS:
            return []
        return copy.deepcopy(unsummarized_requests[: self.SUMMARY_WINDOW_REQUESTS])

    def apply_history_summary(self, summary: str, summarized_through_request_id: int) -> None:
        cleaned_summary = str(summary or "").strip()
        if not cleaned_summary:
            return
        self.history_summary = cleaned_summary
        self.summarized_through_request_id = max(
            self.summarized_through_request_id,
            summarized_through_request_id,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "history_summary": self.history_summary,
            "summarized_through_request_id": self.summarized_through_request_id,
            "completed_requests": copy.deepcopy(self.completed_requests),
            "active_request": copy.deepcopy(self.active_request),
        }

    def save(self) -> None:
        self._write_json(self.normalized_path, self.snapshot())
        self._write_json(self.raw_path, self.raw_events)

    @staticmethod
    def _completed_request_context(request: dict[str, Any]) -> dict[str, Any]:
        return {
            "request_id": request.get("request_id"),
            "USER_REQUEST": request.get("question"),
            "SUMMARY": request.get("summary"),
            "FINAL_ANSWER": request.get("final_answer"),
        }

    @staticmethod
    def _event_to_manager_records(event: dict[str, Any]) -> list[dict[str, Any]]:
        event_type = event.get("event_type")
        if event_type == "user_request":
            return [{"USER": event.get("request")}]
        if event_type == "user_clarification":
            records = []
            if event.get("question"):
                records.append({"SYSTEM": f"clarification requested: {event.get('question')}"})
            records.append({"USER": f"clarification answer: {event.get('answer')}"})
            return records
        if event_type == "planner_action":
            action = event.get("action", {})
            manager_action = {
                "action": action.get("type"),
                "iteration": event.get("iteration"),
            }
            for key in ("agent", "instruction", "question", "answer", "reason"):
                if action.get(key) not in (None, "", [], {}):
                    manager_action[key] = action.get(key)
            return [{"AI[MANAGER]": manager_action}]
        if event_type == "worker_done":
            tool_call = {
                "agent": event.get("agent"),
                "instruction": event.get("instruction"),
                "result": event.get("request_results") or "No handoff provided.",
            }
            request_raw_data = event.get("request_raw_data")
            if request_raw_data not in (None, "", [], {}):
                tool_call["raw_data"] = request_raw_data
            return [{"TOOL_CALL": tool_call}]
        if event_type == "worker_budget_exhausted":
            return [
                {
                    "TOOL_CALL": {
                        "agent": event.get("agent"),
                        "instruction": event.get("instruction"),
                        "result": "worker budget exhausted",
                    }
                }
            ]
        if event_type == "routing_error":
            return [{"SYSTEM": f"routing error: unknown agent {event.get('agent')}"}]
        if event_type == "final_answer":
            return [{"FINAL_ANSWER": event.get("answer")}]
        if event_type == "runtime_stop":
            return [{"SYSTEM": f"runtime stopped: {event.get('reason')}"}]
        return [{"SYSTEM": event}]

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4, ensure_ascii=False)
