from __future__ import annotations

from queue import Empty, Queue
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4

from runtime import build_default_runtime
from runtime.tracing import DEFAULT_TRACE_DIR, SessionTraceSink

RuntimeFactory = Callable[..., object]
TraceSinkFactory = Callable[[Callable[[dict], None]], object]

_ACTIVE_CONTROLLERS: dict[str, "SessionController"] = {}


class SessionController:
    def __init__(
        self,
        *,
        runtime_factory: RuntimeFactory = build_default_runtime,
        trace_dir=DEFAULT_TRACE_DIR,
        trace_sink_factory: TraceSinkFactory | None = None,
    ):
        self.controller_id = uuid4().hex
        self.runtime_factory = runtime_factory
        self.trace_dir = trace_dir
        self.trace_events: list[dict] = []
        self.session_id: str | None = None
        self.status = "empty"
        self.pending_input_kind: str | None = None
        self.pending_prompt: str | None = None
        self.error_message: str | None = None
        self.last_answer: str | None = None
        self._event_queue: Queue = Queue()
        self._input_queue: Queue = Queue()
        self._lock = Lock()
        self._runtime_thread: Thread | None = None

        if trace_sink_factory is None:
            self.trace_sink = SessionTraceSink(
                trace_dir=self.trace_dir,
                listener=self._on_trace_event,
            )
        else:
            self.trace_sink = trace_sink_factory(self._on_trace_event)

    @property
    def is_waiting(self) -> bool:
        return self.status in {"awaiting_user_input", "completed_request"}

    def events_snapshot(self) -> list[dict]:
        with self._lock:
            return list(self.trace_events)

    def submit(self, message: str) -> None:
        cleaned_message = str(message or "").strip()
        if not cleaned_message:
            return

        if self._runtime_thread is None:
            self._start_runtime(cleaned_message)
            return

        self.pending_input_kind = None
        self.pending_prompt = None
        self.status = "running"
        self._input_queue.put(cleaned_message)
        self._event_queue.put({"event_type": "__controller_state__"})

    def wait_for_update(self, timeout: float = 0.15) -> bool:
        changed = False
        try:
            self._event_queue.get(timeout=timeout)
            changed = True
        except Empty:
            return False

        while True:
            try:
                self._event_queue.get_nowait()
                changed = True
            except Empty:
                return changed

    def close(self) -> None:
        if self._runtime_thread and self._runtime_thread.is_alive() and self.is_waiting:
            self._input_queue.put("q")
            self._runtime_thread.join(timeout=3)

        if self._runtime_thread and not self._runtime_thread.is_alive():
            self.status = "ended"

    def _start_runtime(self, initial_request: str) -> None:
        self.status = "starting"
        self.pending_input_kind = None
        self.pending_prompt = None
        runtime = self.runtime_factory(
            input_func=self._blocking_input,
            output_func=self._capture_output,
            sleep_func=lambda _seconds: None,
            trace_sink=self.trace_sink,
        )

        def runner() -> None:
            try:
                self.last_answer = runtime.run(initial_request=initial_request)
                if self.status not in {"awaiting_user_input", "completed_request", "error"}:
                    self.status = "ended"
            except Exception as exc:
                self.error_message = str(exc)
                self.status = "error"
                self.trace_sink.emit(
                    "runtime_error",
                    phase="runtime",
                    payload={"error": self.error_message},
                )
            finally:
                self._event_queue.put({"event_type": "__controller_state__"})

        self._runtime_thread = Thread(target=runner, daemon=True)
        self._runtime_thread.start()
        self._event_queue.put({"event_type": "__controller_state__"})

    def _capture_output(self, _message: str) -> None:
        return None

    def _blocking_input(self, prompt: str) -> str:
        kind = self._classify_prompt(prompt)
        if kind == "clarification":
            self.status = "awaiting_user_input"
        elif kind == "follow_up":
            self.status = "completed_request"
        else:
            self.status = "awaiting_user_input"

        self.pending_input_kind = kind
        self.pending_prompt = prompt
        self._event_queue.put({"event_type": "__controller_state__"})

        response = self._input_queue.get()
        self.pending_input_kind = None
        self.pending_prompt = None
        self.status = "running"
        self._event_queue.put({"event_type": "__controller_state__"})
        return response

    def _classify_prompt(self, prompt: str) -> str:
        if prompt.startswith("Manager needs more information."):
            return "clarification"
        if prompt.startswith("Send the next request:") or prompt.startswith("Your request has been finished."):
            return "follow_up"
        return "input"

    def _on_trace_event(self, event: dict) -> None:
        with self._lock:
            self.trace_events.append(event)
            self.session_id = event.get("session_id", self.session_id)

        event_type = event.get("event_type")
        payload = event.get("payload", {})

        if event_type == "user_input_requested":
            kind = payload.get("kind")
            self.pending_input_kind = kind
            self.pending_prompt = payload.get("prompt")
            self.status = "awaiting_user_input" if kind == "clarification" else "completed_request"
        elif event_type in {"planner_iteration_start", "delegation_start", "tool_call", "model_call", "model_repair_call", "worker_action", "tool_result", "synthesis_start"}:
            if self.status != "error":
                self.status = "running"
        elif event_type == "final_answer":
            self.last_answer = payload.get("answer")
        elif event_type == "session_end":
            self.pending_input_kind = None
            self.pending_prompt = None
            self.status = "ended"
        elif event_type == "runtime_error":
            self.error_message = payload.get("error")
            self.status = "error"

        self._event_queue.put(event)


def create_controller(
    *,
    runtime_factory: RuntimeFactory = build_default_runtime,
    trace_dir=DEFAULT_TRACE_DIR,
    trace_sink_factory: TraceSinkFactory | None = None,
) -> SessionController:
    controller = SessionController(
        runtime_factory=runtime_factory,
        trace_dir=trace_dir,
        trace_sink_factory=trace_sink_factory,
    )
    _ACTIVE_CONTROLLERS[controller.controller_id] = controller
    return controller


def get_controller(controller_id: str | None) -> SessionController | None:
    if not controller_id:
        return None
    return _ACTIVE_CONTROLLERS.get(controller_id)


def remove_controller(controller_id: str | None) -> SessionController | None:
    if not controller_id:
        return None
    return _ACTIVE_CONTROLLERS.pop(controller_id, None)
