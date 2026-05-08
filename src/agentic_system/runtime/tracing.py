from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Protocol

from runtime.contracts import make_json_safe

TraceEvent = dict[str, Any]
TraceListener = Callable[[TraceEvent], None]
DEFAULT_TRACE_DIR = Path(__file__).resolve().parent.parent / "memory" / "ui_traces"


class TraceSink(Protocol):
    def start_session(
        self,
        session_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...

    def emit(
        self,
        event_type: str,
        *,
        agent: str | None = None,
        phase: str | None = None,
        payload: dict[str, Any] | None = None,
        prompt: dict[str, Any] | None = None,
        response: Any = None,
        raw_response: str | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> TraceEvent | None:
        ...

    def clear_session(self) -> None:
        ...


class NullTraceSink:
    def start_session(
        self,
        session_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None

    def emit(
        self,
        event_type: str,
        *,
        agent: str | None = None,
        phase: str | None = None,
        payload: dict[str, Any] | None = None,
        prompt: dict[str, Any] | None = None,
        response: Any = None,
        raw_response: str | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> TraceEvent | None:
        return None

    def clear_session(self) -> None:
        return None


class SessionTraceSink:
    def __init__(
        self,
        *,
        trace_dir: str | Path = DEFAULT_TRACE_DIR,
        listener: TraceListener | None = None,
    ):
        self.trace_dir = Path(trace_dir)
        self.listener = listener
        self._lock = Lock()
        self._session_id: str | None = None
        self._sequence = 0
        self._trace_path: Path | None = None
        self._metadata: dict[str, Any] = {}

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def trace_path(self) -> Path | None:
        return self._trace_path

    def start_session(
        self,
        session_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            self._session_id = session_id
            self._sequence = 0
            self._metadata = dict(metadata or {})
            self._trace_path = self.trace_dir / f"{session_id}.jsonl"

    def emit(
        self,
        event_type: str,
        *,
        agent: str | None = None,
        phase: str | None = None,
        payload: dict[str, Any] | None = None,
        prompt: dict[str, Any] | None = None,
        response: Any = None,
        raw_response: str | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> TraceEvent | None:
        listener = self.listener
        with self._lock:
            if self._session_id is None or self._trace_path is None:
                return None

            self._sequence += 1
            event: TraceEvent = {
                "session_id": self._session_id,
                "sequence": self._sequence,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "event_type": event_type,
                "agent": agent,
                "phase": phase,
                "payload": make_json_safe(payload or {}),
                "prompt": make_json_safe(prompt) if prompt is not None else None,
                "response": make_json_safe(response) if response is not None else None,
                "raw_response": raw_response,
                "token_usage": make_json_safe(token_usage)
                if token_usage is not None
                else None,
                "metadata": make_json_safe(self._metadata) if self._metadata else None,
            }

            try:
                with self._trace_path.open("a", encoding="utf-8") as trace_file:
                    trace_file.write(json.dumps(event, ensure_ascii=False, default=str))
                    trace_file.write("\n")
            except OSError:
                pass

        if listener is not None:
            try:
                listener(event)
            except Exception:
                pass

        return event

    def clear_session(self) -> None:
        with self._lock:
            self._session_id = None
            self._sequence = 0
            self._trace_path = None
            self._metadata = {}


def load_trace_events(
    session_id_or_path: str | Path,
    *,
    trace_dir: str | Path = DEFAULT_TRACE_DIR,
) -> list[TraceEvent]:
    path = Path(session_id_or_path)
    if path.suffix != ".jsonl":
        path = Path(trace_dir) / f"{path}.jsonl"

    if not path.exists():
        return []

    events: list[TraceEvent] = []
    with path.open("r", encoding="utf-8") as trace_file:
        for line in trace_file:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return events
