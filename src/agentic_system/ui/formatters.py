from __future__ import annotations

from collections import defaultdict
import html
import json
from typing import Any

MODEL_EVENT_TYPES = {"model_call"}
HIDDEN_TRACE_EVENT_TYPES = {"session_start", "planner_iteration_start", "delegation_start", "synthesis_start"}
GRAPH_EVENT_TYPES = {
    "user_request",
    "user_clarification",
    "user_input_requested",
    "planner_action",
    "worker_action",
    "tool_call",
    "tool_result",
    "tool_call_exception",
    "worker_done",
    "synthesis_start",
    "final_answer",
    "runtime_stop",
    "runtime_error",
}


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _details(summary: str, body_html: str, *, open_by_default: bool = False) -> str:
    open_attr = " open" if open_by_default else ""
    return (
        f"<details{open_attr}>"
        f"<summary>{summary}</summary>"
        f"{body_html}"
        "</details>"
    )


def _code_block(value: Any) -> str:
    text = value if isinstance(value, str) else _pretty_json(value)
    return f"<pre>{_escape(text)}</pre>"


def _json_block(title: str, value: Any, *, open_by_default: bool = False) -> str:
    return _details(title, _code_block(value), open_by_default=open_by_default)


def _text_block(value: Any) -> str:
    return f"<div class='prompt-section-body'>{_escape('' if value is None else str(value))}</div>"


def _text_details(title: str, value: Any, *, open_by_default: bool = False) -> str:
    return _details(title, _text_block(value), open_by_default=open_by_default)


def _labelize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _agent_label(value: Any) -> str:
    agent = str(value or "").strip()
    labels = {
        "api": "API",
        "manager": "Manager",
        "secretary": "Secretary",
        "data_manager": "Data Manager",
        "pythondeveloper": "Python Developer",
    }
    if not agent:
        return ""
    return labels.get(agent.lower(), _labelize(agent))


def _truncate(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _status_slug(value: Any) -> str:
    return str(value or "unknown").strip().lower().replace(" ", "_")


def _event_label(event: dict) -> str:
    event_type = event.get("event_type", "event")
    payload = event.get("payload", {})
    if event_type == "model_call" and payload.get("status") == "invalid_json_response":
        return "Invalid JSON"
    labels = {
        "model_call": "LLM Call",
        "planner_iteration_start": "Planner Iteration",
        "planner_action": "Planner Decision",
        "worker_action": "Worker Decision",
        "tool_call": "Tool Call",
        "tool_result": "Tool Result",
        "tool_call_exception": "Tool Exception",
        "delegation_start": "Delegation",
        "user_input_requested": "User Input Requested",
        "user_clarification": "User Clarification",
        "worker_done": "Worker Completed",
        "final_answer": "Final Answer",
        "runtime_stop": "Runtime Stop",
        "runtime_error": "Runtime Error",
        "session_start": "Session Start",
        "session_end": "Session End",
        "conversation_end": "Conversation End",
    }
    return labels.get(event_type, _labelize(str(event_type)))


def _actor_kind(event: dict) -> str:
    event_type = str(event.get("event_type") or "")
    if event_type in {"runtime_error", "runtime_stop", "tool_call_exception"}:
        return "actor-error"
    if event_type in {"tool_call", "tool_result"}:
        return "actor-tool"
    if event_type in {"user_request", "user_clarification"}:
        return "actor-user"
    if event.get("agent") == "manager" or event_type.startswith("planner") or event_type in {
        "delegation_start",
        "final_answer",
        "synthesis_start",
        "user_input_requested",
    }:
        return "actor-manager"
    if event.get("agent"):
        return "actor-worker"
    return "actor-runtime"


def _actor_name(event: dict) -> str:
    event_type = event.get("event_type")
    if event_type == "tool_call":
        return "Tool Runner"
    if event_type == "tool_result":
        return "Tool Output"
    if event_type == "tool_call_exception":
        return "Tool Failure"
    if event_type == "user_request":
        return "User"
    if event_type == "user_clarification":
        return "User"
    agent = event.get("agent")
    if agent:
        return _agent_label(agent)
    return "RUNTIME"


def _actor_group(event: dict) -> tuple[str, str]:
    event_type = str(event.get("event_type") or "")
    if event_type in {"runtime_error", "runtime_stop", "tool_call_exception"}:
        return "Error", "error"
    if event_type in {"user_request", "user_clarification"}:
        return "User", "user"
    if event_type in {
        "planner_action",
        "final_answer",
        "synthesis_start",
        "user_input_requested",
    }:
        return "Manager", "manager"
    if event_type in MODEL_EVENT_TYPES and event.get("agent") == "manager":
        return "Manager", "manager"
    if event.get("agent"):
        label = _agent_label(event.get("agent"))
        return label, _status_slug(label)
    if event_type in {"tool_call", "tool_result"}:
        return "Tool / Runtime", "tool"
    return "Runtime", "runtime"


def _action_detail(event: dict) -> str:
    event_type = event.get("event_type")
    payload = event.get("payload", {})
    action = payload.get("action")

    if event_type == "planner_action" and isinstance(action, dict):
        action_type = action.get("type")
        if action_type == "delegate":
            return f"Delegate to {_agent_label(action.get('agent')) or action.get('agent')}"
        if action_type in {"talk_with_user", "ask_user"}:
            return "Ask user"
        if action_type == "answer_user":
            return "Answer user"
        if action_type == "finish":
            return "Finish and synthesize"
        return _labelize(str(action_type or "Decision"))

    if event_type == "worker_action" and isinstance(action, dict):
        action_type = action.get("type")
        if action_type == "tool":
            return f"Use tool: {action.get('tool')}"
        if action_type == "done":
            return "Return results"
        return _labelize(str(action_type or "Decision"))

    if event_type in {"tool_call", "tool_result", "tool_call_exception"}:
        tool = payload.get("tool")
        if event_type == "tool_result":
            result = "success" if payload.get("success") else "failed"
            return f"{tool} -> {result}" if tool else result
        return str(tool or "")

    if event_type == "model_call":
        return str(payload.get("model") or payload.get("model_provider") or "")
    if event_type == "worker_done":
        return f"{payload.get('steps_taken') or payload.get('step') or '?'} step(s)"
    if event_type == "user_input_requested":
        return _labelize(str(payload.get("kind") or "input"))
    if event_type == "runtime_stop":
        return str(payload.get("reason") or "")
    return ""


def _header_chip(label: str, value: Any, *, slug_prefix: str | None = None) -> str:
    if value in {None, ""}:
        return ""
    classes = "trace-card-chip"
    if slug_prefix:
        classes = f"{classes} {slug_prefix}-{_status_slug(value)}"
    return f"<span class='{classes}'>{_escape(label)} {_escape(value)}</span>"


def _stat(label: str, value: Any) -> str:
    if value in {None, ""}:
        return ""
    return (
        "<div class='trace-stat'>"
        f"<span class='trace-stat-label'>{_escape(label)}</span>"
        f"<span class='trace-stat-value'>{_escape(value)}</span>"
        "</div>"
    )


def _meta_grid(items: list[tuple[str, Any]]) -> str:
    rendered = "".join(_stat(label, value) for label, value in items if value not in {None, ""})
    if not rendered:
        return ""
    return f"<div class='trace-card-grid'>{rendered}</div>"


def _split_prompt_sections(text: Any) -> list[tuple[str, str]]:
    content = str(text or "").strip()
    if not content:
        return [("Content", "")]

    lines = content.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = "Content"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.endswith(":") and stripped[:-1].replace(" ", "").replace("_", "").isupper():
            if current_lines or not sections:
                sections.append((current_title, current_lines))
            current_title = stripped[:-1].replace("_", " ").title()
            current_lines = []
            continue
        current_lines.append(line)

    sections.append((current_title, current_lines))
    normalized = []
    for title, value_lines in sections:
        body = "\n".join(value_lines).strip()
        if body or title != "Content":
            normalized.append((title, body))
    return normalized or [("Content", content)]


def _render_prompt_role(role: str, content: Any) -> str:
    role_title = role.title()
    sections = _split_prompt_sections(content)
    rendered_sections = "".join(
        "<div class='prompt-section'>"
        f"<div class='prompt-section-title'>{_escape(title)}</div>"
        f"{_text_block(body)}"
        "</div>"
        for title, body in sections
    )
    role_class = _escape(role.lower())
    return (
        f"<div class='prompt-role {role_class}'>"
        "<div class='prompt-role-header'>"
        f"<span class='prompt-role-badge'>{_escape(role_title)}</span>"
        f"<span class='prompt-role-title'>{_escape(role_title)} Prompt</span>"
        "</div>"
        f"<div class='prompt-role-body'>{rendered_sections}</div>"
        "</div>"
    )


def _prompt_block(prompt: dict[str, Any]) -> str:
    system_prompt = prompt.get("system")
    user_prompt = prompt.get("user")
    rendered = []
    if system_prompt not in {None, ""}:
        rendered.append(_render_prompt_role("system", system_prompt))
    if user_prompt not in {None, ""}:
        rendered.append(_render_prompt_role("user", user_prompt))
    if not rendered:
        rendered.append(_render_prompt_role("prompt", prompt))
    return _details("Input Prompt", f"<div class='prompt-view'>{''.join(rendered)}</div>")


def _trace_card(event: dict, body_html: str, *, extra_classes: str = "", status: Any = None) -> str:
    classes = f"trace-card {_actor_kind(event)}"
    if extra_classes:
        classes = f"{classes} {extra_classes}"
    detail = _action_detail(event)
    detail_html = f"<span class='trace-card-detail'>{_escape(detail)}</span>" if detail else ""
    header = (
        "<div class='trace-card-header'>"
        f"<span class='trace-card-type'>{_escape(_event_label(event))}</span>"
        f"<span class='trace-card-title'>{_escape(_actor_name(event))}</span>"
        f"{detail_html}"
        f"<span class='trace-card-subtitle'>{_escape(event.get('timestamp'))}</span>"
        f"{_header_chip('Status:', status, slug_prefix='status') if status else ''}"
        "</div>"
    )
    return f"<div class='{classes}'>{header}<div class='trace-card-body'>{body_html}</div></div>"


def chat_messages_from_events(events: list[dict]) -> list[dict]:
    if not events:
        return [
            {
                "role": "assistant",
                "content": (
                    "Start a conversation below. The full manager/worker trace, tool calls, "
                    "console log, and token usage will appear on the right as the run unfolds."
                ),
            }
        ]

    messages: list[dict] = []
    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        if event_type == "user_request":
            request = payload.get("request", event.get("request"))
            if request:
                messages.append({"role": "user", "content": str(request)})
        elif event_type == "user_clarification":
            answer = payload.get("answer", event.get("answer"))
            if answer:
                messages.append({"role": "user", "content": str(answer)})
        elif event_type == "user_input_requested":
            kind = payload.get("kind")
            if kind == "clarification":
                question = payload.get("question", "Please provide more information.")
                reason = payload.get("reason")
                content = f"**Manager needs more information**\n\n{question}"
                if reason:
                    content += f"\n\nReason: {reason}"
                messages.append({"role": "assistant", "content": content})
            elif kind == "follow_up":
                continue
        elif event_type == "final_answer":
            answer = payload.get("answer", event.get("answer"))
            if answer:
                messages.append({"role": "assistant", "content": str(answer)})
        elif event_type == "runtime_stop":
            reason = payload.get("reason", "Runtime stopped before the task finished.")
            messages.append({"role": "assistant", "content": f"Runtime stopped: `{reason}`"})

    return messages or [{"role": "assistant", "content": "No chat messages recorded yet."}]


def token_totals(events: list[dict]) -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0, "per_agent": defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0})}

    for event in events:
        if event.get("event_type") not in MODEL_EVENT_TYPES:
            continue

        usage = event.get("token_usage") or {}
        input_tokens = usage.get("input_tokens") or 0
        output_tokens = usage.get("output_tokens") or 0
        agent = event.get("agent") or "unknown"

        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["per_agent"][agent]["input_tokens"] += input_tokens
        totals["per_agent"][agent]["output_tokens"] += output_tokens

    totals["per_agent"] = dict(totals["per_agent"])
    return totals


def _latest_focus(events: list[dict]) -> tuple[str, str]:
    for event in reversed(events):
        agent = event.get("agent")
        phase = event.get("phase")
        if agent or phase:
            return str(agent or "runtime"), str(phase or event.get("event_type", "idle"))
    return "runtime", "idle"


def status_html(
    events: list[dict],
    *,
    status: str,
    session_id: str | None,
    pending_input_kind: str | None = None,
    archived: bool = False,
) -> str:
    status_labels = {
        "empty": "Ready",
        "running": "Running",
        "awaiting_user_input": "Waiting For Clarification",
        "completed_request": "Waiting For Next Request",
        "ended": "Session Ended",
        "error": "Error",
        "archived": "Archived Session",
    }
    agent, phase = _latest_focus(events)
    label = status_labels.get(status, status.replace("_", " ").title())
    hint = ""
    if pending_input_kind == "clarification":
        hint = "Manager is waiting for an answer."
    elif pending_input_kind == "follow_up":
        hint = "You can send the next request now."
    elif archived:
        hint = "Read-only trace loaded from disk. Sending starts a new live session."

    return (
        "<div class='status-panel'>"
        f"<div class='status-pill status-{_escape(status)}'>{_escape(label)}</div>"
        f"<div class='status-meta'><strong>Session:</strong> {_escape(session_id or 'Not started')}</div>"
        f"<div class='status-meta'><strong>Current Focus:</strong> {_escape(agent.upper())} / {_escape(phase.upper())}</div>"
        f"<div class='status-hint'>{_escape(hint)}</div>"
        "</div>"
    )


def token_html(events: list[dict]) -> str:
    totals = token_totals(events)
    chips = []
    for agent, usage in sorted(totals["per_agent"].items()):
        chips.append(
            "<div class='token-chip'>"
            f"<span class='token-chip-title'>{_escape(agent.upper())}</span>"
            f"<span>In {usage['input_tokens']}</span>"
            f"<span>Out {usage['output_tokens']}</span>"
            "</div>"
        )

    chips_html = "".join(chips) or "<div class='token-chip empty'>No model calls yet</div>"
    return (
        "<div class='token-panel'>"
        f"<div class='token-total'><strong>Input</strong> {totals['input_tokens']}</div>"
        f"<div class='token-total'><strong>Output</strong> {totals['output_tokens']}</div>"
        f"<div class='token-total'><strong>Total</strong> {totals['input_tokens'] + totals['output_tokens']}</div>"
        f"<div class='token-chip-row'>{chips_html}</div>"
        "</div>"
    )


def _event_body(event: dict) -> str:
    event_type = event.get("event_type")
    payload = event.get("payload", {})
    prompt = event.get("prompt") or {}
    response = event.get("response")
    raw_response = event.get("raw_response")
    token_usage = event.get("token_usage") or {}

    if event_type in MODEL_EVENT_TYPES:
        error = payload.get("error")
        info = _meta_grid(
            [
                ("Provider", payload.get("model_provider")),
                ("Model", payload.get("model")),
                ("Input Tokens", token_usage.get("input_tokens")),
                ("Output Tokens", token_usage.get("output_tokens")),
                ("Total Tokens", token_usage.get("total_tokens")),
            ]
        )
        sections = [
            _json_block(
                "Output",
                response if response is not None else {"status": payload.get("status")},
                open_by_default=True,
            ),
            _prompt_block(prompt),
        ]
        if raw_response not in {None, ""}:
            show_raw = False
            raw_label = "Raw Response"
            if payload.get("status") == "invalid_json_response":
                raw_label = "Invalid JSON"
                show_raw = True
            elif response is None:
                show_raw = True
            elif isinstance(response, str) and response != raw_response:
                show_raw = True
            if show_raw:
                sections.append(_json_block(raw_label, raw_response))
        if error:
            sections.append(_json_block("Error", {"message": error}))
        return info + "".join(sections)

    if event_type == "planner_iteration_start":
        body = _meta_grid([("Iteration", payload.get("iteration")), ("Phase", event.get("phase"))])
        body += _json_block("Output", {"message": f"Planner iteration {payload.get('iteration')} started."}, open_by_default=True)
        return body

    if event_type == "planner_action":
        action = payload.get("action", payload)
        info = _meta_grid([("Iteration", payload.get("iteration")), ("Decision Type", (action or {}).get("type") if isinstance(action, dict) else None)])
        if isinstance(action, dict):
            output = (
                f"Agent: {action.get('agent')}\nInstruction: {action.get('instruction')}"
                if action.get("type") == "delegate"
                else action.get("reason") or action.get("question") or _pretty_json(action)
            )
        else:
            output = action
        return info + _text_details("Output", output, open_by_default=True)

    if event_type == "worker_action":
        action = payload.get("action", payload)
        info = _meta_grid(
            [
                ("Step", payload.get("step")),
                ("Instruction", payload.get("instruction")),
                ("Decision Type", (action or {}).get("type") if isinstance(action, dict) else None),
            ]
        )
        output = action.get("request_results") if isinstance(action, dict) and action.get("request_results") else _pretty_json(action)
        sections = [_text_details("Output", output, open_by_default=True)]
        if isinstance(action, dict) and action.get("request_raw_data") not in (None, "", [], {}):
            sections.append(_json_block("Raw Data", action.get("request_raw_data")))
        return info + "".join(sections)

    if event_type == "tool_call":
        status = payload.get("status") or "ready"
        info = _meta_grid(
            [
                ("Tool", payload.get("tool")),
                ("Signature", payload.get("signature")),
                ("Description", payload.get("description")),
                ("Step", payload.get("step")),
            ]
        )
        return (
            info
            + _text_details(
                "Output",
                f"Tool {payload.get('tool')} is ready to run.",
                open_by_default=True,
            )
            + _json_block("Tool Input", payload.get("args", {}))
        )

    if event_type == "tool_result":
        info = _meta_grid(
            [
                ("Tool", payload.get("tool")),
                ("Step", payload.get("step")),
                ("Success", payload.get("success")),
                ("Summary", payload.get("summary")),
            ]
        )
        sections = [
            _text_details(
                "Output",
                payload.get("summary") or ("Tool succeeded." if payload.get("success") else "Tool failed."),
                open_by_default=True,
            ),
            _json_block("Tool Input", payload.get("args", {})),
        ]
        tool_data = payload.get("data")
        if tool_data is not None and tool_data != "":
            sections.append(_json_block("Tool Output", tool_data))
        if payload.get("error"):
            sections.append(_json_block("Error", {"message": payload.get("error")}))
        return info + "".join(sections)

    if event_type == "tool_call_exception":
        info = _meta_grid(
            [
                ("Tool", payload.get("tool")),
                ("Exception", payload.get("exception_type")),
            ]
        )
        return (
            info
            + _text_details(
                "Output",
                payload.get("error"),
                open_by_default=True,
            )
            + _json_block("Tool Input", payload.get("args", {}))
            + _json_block("Error", {"traceback": payload.get("traceback")})
        )

    if event_type == "user_input_requested":
        if payload.get("kind") == "clarification":
            return _meta_grid([("Kind", "Clarification")]) + _text_details(
                "Output",
                f"Question: {payload.get('question')}",
                open_by_default=True,
            )
        return _meta_grid([("Kind", payload.get("kind"))]) + _json_block(
            "Output",
            {"prompt": payload.get("prompt")},
            open_by_default=True,
        )

    if event_type == "user_clarification":
        return _text_details(
            "Output",
            payload.get("answer"),
            open_by_default=True,
        )

    if event_type == "user_request":
        return _text_details("Output", payload.get("request"), open_by_default=True)

    if event_type == "worker_done":
        info = _meta_grid([("Steps Taken", payload.get("steps_taken")), ("Instruction", payload.get("instruction"))])
        sections = [
            _text_details("Output", payload.get("request_results"), open_by_default=True),
        ]
        if payload.get("request_raw_data") not in (None, "", [], {}):
            sections.append(_json_block("Raw Data", payload.get("request_raw_data")))
        return info + "".join(sections)

    if event_type == "final_answer":
        return _text_details("Output", payload.get("answer", event.get("answer")), open_by_default=True)

    if event_type == "runtime_error":
        return _json_block("Output", {"error": payload.get("error")}, open_by_default=True)

    if event_type == "runtime_stop":
        return _text_details("Output", payload.get("reason"), open_by_default=True)

    if event_type in {"session_end", "conversation_end"}:
        return _json_block("Output", payload, open_by_default=True)

    body = _json_block("Output", payload, open_by_default=True)
    metadata = event.get("metadata")
    if metadata:
        body += _json_block("Metadata", metadata)
    return body


def _request_text(event: dict | None, fallback: str = "Session events") -> str:
    if not event:
        return fallback
    payload = event.get("payload", {})
    return str(payload.get("request") or event.get("request") or fallback)


def _request_groups(events: list[dict]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    request_index = 0

    for event in events:
        if event.get("event_type") == "user_request":
            request_index += 1
            current = {
                "index": request_index,
                "request_event": event,
                "events": [event],
            }
            groups.append(current)
            continue

        if current is None:
            current = {
                "index": 0,
                "request_event": None,
                "events": [],
            }
            groups.append(current)
        current["events"].append(event)

    return [group for group in groups if group["events"]]


def _request_header(group: dict[str, Any]) -> str:
    index = group.get("index", 0)
    request_event = group.get("request_event")
    if index:
        title = f"========== REQUEST {index} =========="
        request = _request_text(request_event)
    else:
        title = "========== SESSION EVENTS =========="
        request = "Runtime events recorded before the first user request."

    return (
        "<div class='request-section-header'>"
        f"<div class='request-section-title'>{_escape(title)}</div>"
        f"<div class='request-section-text'>{_escape(_truncate(request, 360))}</div>"
        "</div>"
    )


def step_trace_html(events: list[dict]) -> str:
    trace_events = [
        event
        for event in events
        if event.get("event_type") not in {"console_output", *HIDDEN_TRACE_EVENT_TYPES}
    ]
    if not trace_events:
        return "<div class='empty-state'>No execution trace yet.</div>"

    rendered_requests = []
    for request_group in _request_groups(trace_events):
        rendered_cards = []
        for event in request_group["events"]:
            payload = event.get("payload", {})
            status = payload.get("status")
            if event.get("event_type") == "tool_result":
                status = "success" if payload.get("success") else "failed"
            if event.get("event_type") == "tool_call_exception":
                status = "error"
            rendered_cards.append(_trace_card(event, _event_body(event), status=status))

        rendered_requests.append(
            "<section class='request-section'>"
            f"{_request_header(request_group)}"
            f"<div class='request-timeline'><div class='timeline'>{''.join(rendered_cards)}</div></div>"
            "</section>"
        )

    return "".join(rendered_requests)


def _graph_node_from_event(event: dict) -> list[dict[str, str]]:
    event_type = event.get("event_type")
    payload = event.get("payload", {})
    action = payload.get("action")
    actor_label, _slug = _actor_group(event)

    if event_type == "user_input_requested" and payload.get("kind") == "follow_up":
        return []

    if event_type == "user_request":
        return [
            {
                "actor": "User",
                "title": "User Request",
                "detail": _truncate(_request_text(event), 180),
                "kind": "actor-user",
            }
        ]
    if event_type == "user_clarification":
        return [
            {
                "actor": "User",
                "title": "Clarification",
                "detail": _truncate(payload.get("answer"), 180),
                "kind": "actor-user",
            }
        ]
    if event_type == "user_input_requested":
        return [
            {
                "actor": "Manager",
                "title": "Ask User",
                "detail": _truncate(payload.get("question") or payload.get("prompt"), 180),
                "kind": "actor-manager",
            }
        ]
    if event_type == "planner_action" and isinstance(action, dict):
        return [
            {
                "actor": "Manager",
                "title": "Manager Decision",
                "detail": _action_detail(event),
                "kind": "actor-manager",
            }
        ]
    if event_type == "worker_action" and isinstance(action, dict):
        return [
            {
                "actor": _agent_label(event.get("agent")) or actor_label,
                "title": "Worker Decision",
                "detail": _action_detail(event),
                "kind": "actor-worker",
            }
        ]
    if event_type == "tool_call":
        return [
            {
                "actor": str(payload.get("tool") or "Tool"),
                "title": "Tool Call",
                "detail": _truncate(json.dumps(payload.get("args", {}), ensure_ascii=False, default=str), 180),
                "kind": "actor-tool",
            }
        ]
    if event_type == "tool_result":
        result = "Success" if payload.get("success") else "Failed"
        return [
            {
                "actor": _agent_label(event.get("agent") or payload.get("agent")) or "Tool Output",
                "title": f"Tool Result: {result}",
                "detail": _truncate(payload.get("summary") or payload.get("error"), 180),
                "kind": "actor-worker" if event.get("agent") else "actor-tool",
            }
        ]
    if event_type == "tool_call_exception":
        return [
            {
                "actor": str(payload.get("tool") or "Tool"),
                "title": "Tool Exception",
                "detail": _truncate(payload.get("error"), 180),
                "kind": "actor-error",
            }
        ]
    if event_type == "worker_done":
        return [
            {
                "actor": _agent_label(event.get("agent")) or actor_label,
                "title": "Worker Completed",
                "detail": _truncate(payload.get("request_results"), 180),
                "kind": "actor-worker",
            }
        ]
    if event_type == "synthesis_start":
        return [
            {
                "actor": "Synthesis",
                "title": "Synthesis Start",
                "detail": "Manager prepares the final response.",
                "kind": "actor-manager",
            }
        ]
    if event_type == "final_answer":
        answer = payload.get("answer", event.get("answer"))
        return [
            {
                "actor": "Manager",
                "title": "Final Answer",
                "detail": _truncate(answer, 180),
                "kind": "actor-manager",
            },
            {
                "actor": "User",
                "title": "Receives Answer",
                "detail": _truncate(answer, 180),
                "kind": "actor-user",
            },
        ]
    if event_type == "runtime_stop":
        return [
            {
                "actor": "Runtime",
                "title": "Runtime Stop",
                "detail": _truncate(payload.get("reason"), 180),
                "kind": "actor-error",
            }
        ]
    if event_type == "runtime_error":
        return [
            {
                "actor": "Runtime",
                "title": "Runtime Error",
                "detail": _truncate(payload.get("error"), 180),
                "kind": "actor-error",
            }
        ]

    return [
        {
            "actor": actor_label,
            "title": _event_label(event),
            "detail": _action_detail(event),
            "kind": _actor_kind(event),
        }
    ]


def execution_graph_html(events: list[dict]) -> str:
    graph_events = [
        event
        for event in events
        if event.get("event_type") in GRAPH_EVENT_TYPES
    ]
    if not graph_events:
        return "<div class='empty-state'>No execution graph yet.</div>"

    rendered_requests = []
    for request_group in _request_groups(graph_events):
        nodes = []
        for event in request_group["events"]:
            nodes.extend(_graph_node_from_event(event))

        rendered_nodes = []
        for index, node in enumerate(nodes, start=1):
            rendered_nodes.append(
                f"<div class='graph-node {node['kind']}'>"
                f"<div class='graph-node-number'>{index}</div>"
                "<div class='graph-node-content'>"
                f"<div class='graph-node-actor'>{_escape(node['actor'])}</div>"
                f"<div class='graph-node-title'>{_escape(node['title'])}</div>"
                f"<div class='graph-node-detail'>{_escape(node['detail'])}</div>"
                "</div>"
                "</div>"
            )

        rendered_requests.append(
            "<section class='request-section graph-request-section'>"
            f"{_request_header(request_group)}"
            f"<div class='execution-graph'>{''.join(rendered_nodes)}</div>"
            "</section>"
        )

    return "".join(rendered_requests)


def console_html(events: list[dict]) -> str:
    console_events = [event for event in events if event.get("event_type") == "console_output"]
    if not console_events:
        return "<div class='empty-state'>No console output yet.</div>"

    rendered = []
    for event in console_events:
        message = str((event.get("payload") or {}).get("message", ""))
        if not message.strip():
            rendered.append("<div class='console-spacer'></div>")
            continue

        body = (
            f"<div class='console-entry-meta'>{_escape(event.get('timestamp'))}</div>"
            f"{_code_block(message)}"
        )
        rendered.append(_trace_card(event, body, extra_classes="console-entry"))

    return "".join(rendered)


def raw_session_json(events: list[dict]) -> str:
    return _pretty_json(events)
