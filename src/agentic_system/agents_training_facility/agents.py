from __future__ import annotations

from datetime import datetime
import json
import os
import traceback
from pathlib import Path
from typing import Callable, List

from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI
from termcolor import colored

from memory.memory_manager import Memory
from prompts.prompts import (
    agent_choose_tool_system,
    agent_choose_tool_user,
    plan_next_step_system,
    plan_next_step_user,
    synthesis_system,
    synthesis_user,
)
from runtime.contracts import (
    ToolResult,
    make_json_safe,
    validate_planner_action,
    validate_worker_action,
)
from runtime.tracing import NullTraceSink, TraceSink
from toolbox.toolbox import ToolBox
from tools import apis, data_manager, file_handler, programer

load_dotenv()

available_tools = {
    "apis": apis,
    "data_manager": data_manager,
    "file_handler": file_handler,
    "programer": programer,
}

_AGENTIC_ROOT = Path(__file__).resolve().parent.parent
TOKEN_USAGE_PATH = str(_AGENTIC_ROOT / "memory" / "execution_cost" / "token_usage.json")
Path(TOKEN_USAGE_PATH).parent.mkdir(parents=True, exist_ok=True)


class Agent:
    agent_registry = {}
    token_usage = Memory(is_structured=True, has_history=TOKEN_USAGE_PATH)

    def __init__(
        self,
        name: str,
        module_list: List[str],
        agent_mission: str,
        agent_personality: str,
        trace_sink: TraceSink | None = None,
    ):
        self.name = name
        self.module_list = module_list
        self.toolbox = ToolBox()
        self.available_functions: list[str] = []
        self.agent_personality = agent_personality
        self.field_agent = True
        self.agent_mission = agent_mission
        self.trace_sink = trace_sink or NullTraceSink()
        self.model_provider, self.model = self._load_model_settings()
        self.client = self._gpt_client()

        selected_functions: dict[str, object] = {}
        for tool_name in module_list:
            if tool_name not in available_tools:
                continue
            module = available_tools[tool_name]
            module_functions = getattr(module, "TOOLS", {})
            selected_functions.update(module_functions)
            self.available_functions.extend(module_functions.keys())

        self.toolbox.store(selected_functions)

        tools_block = self.toolbox.tools() or "No tools available."

        Agent.agent_registry[self.name] = {
            "mission": self.agent_mission,
            "description": self.agent_mission,
            "tools to use": ", ".join(self.available_functions),
            "tools_detailed": tools_block,
            "field_agent": self.field_agent,
        }

    def _get_required_env(self, env_name: str) -> str:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        raise ValueError(f"Missing required environment variable: {env_name}")

    def _load_model_settings(self):
        provider = os.getenv("MODEL_PROVIDER", "azure").strip().lower()
        if provider not in {"azure", "ollama", "openai"}:
            raise ValueError("MODEL_PROVIDER must be one of: 'azure', 'ollama', 'openai'.")

        if provider == "azure":
            model_name = self._get_required_env("AZURE_OPENAI_DEPLOYMENT")
        elif provider == "openai":
            model_name = self._get_required_env("OPENAI_MODEL")
        else:
            model_name = self._get_required_env("OLLAMA_MODEL")

        return provider, model_name

    def _gpt_client(self):
        if self.model_provider == "azure":
            api_key = self._get_required_env("AZURE_OPENAI_API_KEY")
            azure_endpoint = self._get_required_env("AZURE_OPENAI_ENDPOINT")
            if azure_endpoint.rstrip("/").endswith("/openai/v1"):
                return OpenAI(base_url=azure_endpoint, api_key=api_key)

            api_version = self._get_required_env("AZURE_OPENAI_API_VERSION")
            return AzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version,
            )

        if self.model_provider == "openai":
            api_key = self._get_required_env("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "").strip()
            if base_url:
                return OpenAI(base_url=base_url, api_key=api_key)
            return OpenAI(api_key=api_key)

        ollama_base_url = self._get_required_env("OLLAMA_BASE_URL")
        ollama_api_key = self._get_required_env("OLLAMA_API_KEY")
        return OpenAI(base_url=ollama_base_url, api_key=ollama_api_key)

    def _parse_json_response(self, model_content: str):
        cleaned_content = model_content.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content.strip("`")
            if cleaned_content.startswith("json"):
                cleaned_content = cleaned_content[4:]
            cleaned_content = cleaned_content.strip()
        return json.loads(cleaned_content)

    def _usage_payload(self, response) -> dict:
        usage = getattr(response, "usage", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        total_tokens = None
        if completion_tokens is not None or prompt_tokens is not None:
            total_tokens = (completion_tokens or 0) + (prompt_tokens or 0)
        return {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _emit_trace(
        self,
        event_type: str,
        *,
        phase: str | None = None,
        payload: dict | None = None,
        prompt: dict | None = None,
        response=None,
        raw_response: str | None = None,
        token_usage: dict | None = None,
    ) -> None:
        self.trace_sink.emit(
            event_type,
            agent=self.name,
            phase=phase,
            payload=payload,
            prompt=prompt,
            response=response,
            raw_response=raw_response,
            token_usage=token_usage,
        )

    def _emit_model_trace(
        self,
        event_type: str,
        *,
        phase: str | None,
        system_prompt: str,
        user_prompt: str,
        response,
        model_response,
        raw_response: str | None,
        status: str,
        error: str | None = None,
        extra_payload: dict | None = None,
    ) -> None:
        payload = {
            "model_provider": self.model_provider,
            "model": self.model,
            "status": status,
            "error": error,
        }
        if extra_payload:
            payload.update(make_json_safe(extra_payload))

        self._emit_trace(
            event_type,
            phase=phase,
            payload=payload,
            prompt={"system": system_prompt, "user": user_prompt},
            response=model_response,
            raw_response=raw_response,
            token_usage=self._usage_payload(response),
        )

    def _record_model_response(
        self,
        response,
        *,
        model_response=None,
        status: str = "ok",
        error: str | None = None,
        raw_response: str | None = None,
    ) -> None:
        usage = getattr(response, "usage", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        formatted_time = datetime.now().isoformat(timespec="seconds")
        model_data = {
            "timestamp": formatted_time,
            "agent": self.name,
            "model_provider": self.model_provider,
            "model": self.model,
            "status": status,
            "response": model_response,
            "raw_response": raw_response,
            "error": error,
            "completion_tokens": completion_tokens,
            "prompt_tokens": prompt_tokens,
        }
        self.token_usage.extend_memory(model_data)
        self.token_usage.save_history(TOKEN_USAGE_PATH)

    def _ask_agent(
        self,
        system_prompt,
        prompt="",
        return_json=False,
        validator: Callable[[dict], dict] | None = None,
        phase: str | None = None,
    ):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        request_params = {"model": self.model, "messages": messages}

        if return_json:
            json_contract_suffix = (
                "\nReturn exactly one valid JSON object. "
                "Do not wrap it in markdown fences. "
                "Do not add commentary or any text before or after the JSON object."
            )
            messages[0]["content"] += json_contract_suffix
            if self.model_provider in {"azure", "openai"}:
                request_params["response_format"] = {"type": "json_object"}
            else:
                messages[0]["content"] += "\nUse strict JSON syntax with double quotes."

        response = self.client.chat.completions.create(**request_params)

        if return_json:
            raw_content = response.choices[0].message.content
            try:
                model_response = self._parse_json_response(raw_content)
                if validator is not None:
                    model_response = validator(model_response)
                self._emit_model_trace(
                    "model_call",
                    phase=phase,
                    system_prompt=messages[0]["content"],
                    user_prompt=messages[1]["content"],
                    response=response,
                    model_response=model_response,
                    raw_response=raw_content,
                    status="ok",
                )
            except (json.JSONDecodeError, ValueError) as exc:
                self._record_model_response(
                    response,
                    status="invalid_json_response",
                    error=str(exc),
                    raw_response=raw_content,
                )
                self._emit_model_trace(
                    "model_call",
                    phase=phase,
                    system_prompt=messages[0]["content"],
                    user_prompt=messages[1]["content"],
                    response=response,
                    model_response=None,
                    raw_response=raw_content,
                    status="invalid_json_response",
                    error=str(exc),
                )
                raise ValueError(f"{self.name} returned invalid JSON: {exc}") from exc
        else:
            model_response = response.choices[0].message.content
            self._emit_model_trace(
                "model_call",
                phase=phase,
                system_prompt=messages[0]["content"],
                user_prompt=messages[1]["content"],
                response=response,
                model_response=model_response,
                raw_response=model_response,
                status="ok",
            )

        self._record_model_response(response, model_response=model_response)
        return model_response

    def think_in_session(
        self,
        manager_instruction: str,
        assignment_history: str,
    ):
        tool_descriptions = self.toolbox.tools() or "No tools available."
        agent_system_prompt = agent_choose_tool_system.format(
            agent_descriptions=self.agent_personality,
            tool_descriptions=tool_descriptions,
        )
        prompt = agent_choose_tool_user.format(
            manager_instruction=manager_instruction,
            assignment_history=assignment_history,
        )
        return self._ask_agent(
            agent_system_prompt,
            prompt,
            return_json=True,
            validator=validate_worker_action,
            phase="worker",
        )

    def execute_tool(self, agent_response_dict: dict) -> ToolResult:
        tool_choice = agent_response_dict.get("tool")
        tool_input = agent_response_dict.get("args", {})
        tool_spec = self.toolbox.get(tool_choice)

        if tool_spec is None:
            self._emit_trace(
                "tool_call",
                phase="worker",
                payload={
                    "tool": tool_choice,
                    "args": tool_input,
                    "status": "missing_tool",
                },
            )
            return ToolResult.failure(f"Tool {tool_choice} not found in agent's toolbox.")

        self._emit_trace(
            "tool_call",
            phase="worker",
            payload={
                "tool": tool_choice,
                "args": tool_input,
                "description": tool_spec.description,
                "signature": str(tool_spec.signature),
            },
        )
        if isinstance(self.trace_sink, NullTraceSink):
            print(
                colored(
                    f"| Tool Choice Step | Tool {tool_choice} : Arguments {tool_input}",
                    "light_magenta",
                )
            )

        try:
            response = tool_spec.func(**tool_input)
        except Exception as exc:
            exception_type = type(exc).__name__
            traceback_text = traceback.format_exc()
            self._emit_trace(
                "tool_call_exception",
                phase="worker",
                payload={
                    "tool": tool_choice,
                    "args": tool_input,
                    "error": str(exc),
                    "exception_type": exception_type,
                    "traceback": traceback_text,
                },
            )
            return ToolResult.failure(
                error=(
                    f"Tool {tool_choice} raised {exception_type}: {exc}\n"
                    f"Traceback:\n{traceback_text}"
                ),
                data={
                    "tool": tool_choice,
                    "args": tool_input,
                    "exception_type": exception_type,
                    "exception_message": str(exc),
                    "traceback": traceback_text,
                },
                summary=f"Tool {tool_choice} execution failed with {exception_type}: {exc}",
            )

        if isinstance(response, ToolResult):
            return response

        return ToolResult.ok(
            data=response,
            summary=f"Tool {tool_choice} executed successfully.",
        )


class CommandCentre(Agent):
    def __init__(
        self,
        name,
        tools: list,
        agent_mission: str,
        agent_personality: str,
        trace_sink: TraceSink | None = None,
    ):
        super().__init__(
            name,
            tools,
            agent_mission,
            agent_personality,
            trace_sink=trace_sink,
        )

    def _get_agents_characteristics(self) -> str:
        lines: list[str] = []
        for name, values in self.agent_registry.items():
            if name == self.name:
                continue
            description = values.get("description", "").strip() or "general-purpose agent"
            lines.append(f"- {name}: {description}")
        return "\n".join(lines) + "\n"

    def _manager_system_prompt(self, template: str) -> str:
        return template.format(agent_descriptions=self.agent_personality)

    def plan_next_step(self, conversation_context: str) -> dict:
        formatted_prompt = plan_next_step_user.format(
            conversation_context=conversation_context,
            avaliable_agents=self._get_agents_characteristics(),
        )
        planner_response = self._ask_agent(
            self._manager_system_prompt(plan_next_step_system),
            formatted_prompt,
            return_json=True,
            validator=validate_planner_action,
            phase="planner",
        )
        return planner_response

    def synthesize_answer(self, conversation_context: str) -> str:
        formatted_prompt = synthesis_user.format(
            conversation_context=conversation_context,
        )
        return self._ask_agent(
            self._manager_system_prompt(synthesis_system),
            formatted_prompt,
            phase="synthesis",
        )
