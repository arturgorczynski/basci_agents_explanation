from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency
    pd = None


@dataclass(frozen=True)
class ToolResult:
    success: bool
    data: Any = None
    summary: str = ""
    error: str | None = None

    @classmethod
    def ok(cls, data: Any = None, summary: str = "") -> "ToolResult":
        return cls(success=True, data=data, summary=summary)

    @classmethod
    def failure(
        cls,
        error: str,
        data: Any = None,
        summary: str = "",
    ) -> "ToolResult":
        final_summary = summary or error
        return cls(success=False, data=data, summary=final_summary, error=error)


def _preview_value(value: Any) -> str:
    if pd is not None and isinstance(value, pd.DataFrame):
        preview = value.head(5).to_string(index=False)
        return f"DataFrame shape={value.shape}\n{preview}"

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)

    return str(value)


def summarize_tool_result(result: ToolResult) -> str:
    parts: list[str] = []

    if result.summary:
        parts.append(result.summary)

    if result.success and result.data is not None:
        parts.append(_preview_value(result.data))

    if not result.success and result.data not in (None, "", [], {}):
        parts.append(f"data={_preview_value(result.data)}")

    if not result.success and result.error:
        parts.append(f"error={result.error}")

    return "\n".join(parts).strip() or "No result returned."


def make_json_safe(value: Any) -> Any:
    if pd is not None and isinstance(value, pd.DataFrame):
        return {
            "type": "dataframe",
            "shape": list(value.shape),
            "preview": value.head(5).to_dict(orient="records"),
        }

    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [make_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def validate_planner_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("Planner action must be a JSON object.")

    action_type = action.get("type")
    if action_type == "answer_user":
        if not action.get("answer"):
            raise ValueError("answer_user action must include 'answer'.")
        return {
            "type": "answer_user",
            "answer": str(action["answer"]),
        }

    if action_type == "delegate":
        if not action.get("agent") or not action.get("instruction"):
            raise ValueError("Delegate action must include 'agent' and 'instruction'.")
        return {
            "type": "delegate",
            "agent": str(action["agent"]),
            "instruction": str(action["instruction"]),
        }

    if action_type == "talk_with_user":
        if not action.get("question"):
            raise ValueError("talk_with_user action must include 'question'.")
        return {
            "type": "talk_with_user",
            "question": str(action["question"]),
        }

    if action_type == "finish":
        if not action.get("reason"):
            raise ValueError("finish action must include 'reason'.")
        return {"type": "finish", "reason": str(action["reason"])}

    raise ValueError(f"Unsupported planner action type: {action_type}")


def validate_worker_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("Worker action must be a JSON object.")

    action_type = action.get("type")
    if action_type == "tool":
        args = action.get("args", {})
        if not action.get("tool"):
            raise ValueError("Tool action must include 'tool'.")
        if not isinstance(args, dict):
            raise ValueError("Tool action args must be a JSON object.")
        return {
            "type": "tool",
            "tool": str(action["tool"]),
            "args": args,
        }

    if action_type == "done":
        if not action.get("request_results"):
            raise ValueError("done action must include 'request_results'.")
        normalized_action = {
            "type": "done",
            "request_results": str(action["request_results"]),
        }
        if "request_raw_data" in action:
            normalized_action["request_raw_data"] = make_json_safe(action["request_raw_data"])
        return normalized_action

    raise ValueError(f"Unsupported worker action type: {action_type}")
