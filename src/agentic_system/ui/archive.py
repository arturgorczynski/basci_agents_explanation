from __future__ import annotations

from pathlib import Path

from runtime.tracing import DEFAULT_TRACE_DIR, load_trace_events


def load_session(
    session_id: str,
    *,
    trace_dir: str | Path = DEFAULT_TRACE_DIR,
) -> list[dict]:
    return load_trace_events(session_id, trace_dir=trace_dir)


def session_title(events: list[dict]) -> str:
    for event in events:
        payload = event.get("payload", {})
        if event.get("event_type") == "session_start":
            initial_request = payload.get("initial_request")
            if initial_request:
                return str(initial_request).strip()

    for event in events:
        if event.get("event_type") == "user_request" and event.get("payload", {}).get("request"):
            return str(event["payload"]["request"]).strip()
        if event.get("event_type") == "user_request" and event.get("request"):
            return str(event["request"]).strip()

    return "Untitled session"


def list_sessions(
    *,
    trace_dir: str | Path = DEFAULT_TRACE_DIR,
    limit: int = 30,
) -> list[dict]:
    root = Path(trace_dir)
    if not root.exists():
        return []

    session_paths = sorted(
        root.glob("*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    sessions: list[dict] = []
    for path in session_paths[:limit]:
        events = load_trace_events(path)
        if not events:
            continue

        started_at = events[0].get("timestamp", "")
        updated_at = events[-1].get("timestamp", "")
        title = session_title(events)
        sessions.append(
            {
                "session_id": path.stem,
                "label": f"{path.stem} | {title[:72]}",
                "title": title,
                "path": str(path),
                "started_at": started_at,
                "updated_at": updated_at,
            }
        )

    return sessions


def dropdown_choices(
    *,
    trace_dir: str | Path = DEFAULT_TRACE_DIR,
    limit: int = 30,
) -> list[tuple[str, str]]:
    return [
        (session["label"], session["session_id"])
        for session in list_sessions(trace_dir=trace_dir, limit=limit)
    ]


def purge_all_traces(trace_dir: str | Path = DEFAULT_TRACE_DIR) -> int:
    root = Path(trace_dir)
    if not root.exists():
        return 0
    deleted = 0
    for path in root.glob("*.jsonl"):
        try:
            path.unlink()
            deleted += 1
        except OSError:
            pass
    return deleted
