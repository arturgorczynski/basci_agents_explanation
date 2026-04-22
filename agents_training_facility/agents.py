from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Callable, List

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    def load_dotenv():
        return None

try:
    from openai import AzureOpenAI, OpenAI
except ImportError:  # pragma: no cover - optional dependency fallback
    AzureOpenAI = None
    OpenAI = None

try:
    from termcolor import colored
except ImportError:  # pragma: no cover - optional dependency fallback
    def colored(text, _color=None):
        return text

from memory.memory_manager import Memory
from prompts.prompts import (
    agent_choose_tool_system,
    agent_choose_tool_user,
    plan_next_step_system,
    plan_next_step_user,
    synthesis_system,
    synthesis_user,
)
from runtime.contracts import ToolResult, validate_planner_action, validate_worker_action
from toolbox.toolbox import ToolBox
from tools import apis, brain, common, file_handler, programer, utils_handler

load_dotenv()

available_tools = {
    "brain": brain,
    "apis": apis,
    "common": common,
    "file_handler": file_handler,
    "programer": programer,
    "utils_handler": utils_handler,
}

TOKEN_USAGE_PATH = "memory/execution_cost/token_usage.json"


class Agent:
    agent_registry = {}
    token_usage = Memory(is_structured=True, has_history=TOKEN_USAGE_PATH)

    def __init__(
        self,
        name: str,
        module_list: List[str],
        agent_mission: str,
        agent_personality: str,
    ):
        self.name = name
        self.module_list = module_list
        self.toolbox = ToolBox()
        self.available_functions: list[str] = []
        self.agent_personality = agent_personality
        self.field_agent = True
        self.agent_mission = agent_mission
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

        Agent.agent_registry[self.name] = {
            "mission": self.agent_mission,
            "tools to use": ", ".join(self.available_functions),
            "field_agent": self.field_agent,
        }

    def _get_required_env(self, env_name: str) -> str:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        raise ValueError(f"Missing required environment variable: {env_name}")

    def _load_model_settings(self):
        provider = os.getenv("MODEL_PROVIDER", "azure").strip().lower()
        if provider not in {"azure", "ollama"}:
            raise ValueError("MODEL_PROVIDER must be either 'azure' or 'ollama'.")

        if provider == "azure":
            model_name = self._get_required_env("AZURE_OPENAI_DEPLOYMENT")
        else:
            model_name = self._get_required_env("OLLAMA_MODEL")

        return provider, model_name

    def _gpt_client(self):
        if self.model_provider == "azure":
            if AzureOpenAI is None:
                raise ImportError("openai package is required for Azure model provider.")
            api_key = self._get_required_env("AZURE_OPENAI_API_KEY")
            azure_endpoint = self._get_required_env("AZURE_OPENAI_ENDPOINT")
            api_version = self._get_required_env("AZURE_OPENAI_API_VERSION")
            return AzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version,
            )

        ollama_base_url = self._get_required_env("OLLAMA_BASE_URL")
        ollama_api_key = self._get_required_env("OLLAMA_API_KEY")
        if OpenAI is None:
            raise ImportError("openai package is required for Ollama model provider.")
        return OpenAI(base_url=ollama_base_url, api_key=ollama_api_key)

    def _parse_json_response(self, model_content: str):
        cleaned_content = model_content.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content.strip("`")
            if cleaned_content.startswith("json"):
                cleaned_content = cleaned_content[4:]
            cleaned_content = cleaned_content.strip()
        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            extracted_json = self._extract_balanced_json_object(cleaned_content)
            if extracted_json is not None:
                return json.loads(extracted_json)
            raise

    def _extract_balanced_json_object(self, text: str) -> str | None:
        start_index = text.find("{")
        if start_index == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for index in range(start_index, len(text)):
            character = text[index]

            if escape_next:
                escape_next = False
                continue

            if character == "\\" and in_string:
                escape_next = True
                continue

            if character == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return text[start_index : index + 1]

        return None

    def _request_json_repair(
        self,
        system_prompt: str,
        prompt: str,
        invalid_response: str,
        error_message: str,
    ):
        repair_system_prompt = (
            f"{system_prompt}\n"
            "Your previous response could not be accepted. "
            "Return only one valid JSON object that matches the requested schema exactly."
        )
        repair_prompt = (
            f"{prompt}\n\n"
            "Problem detected:\n"
            f"{error_message}\n\n"
            "Previous invalid response:\n"
            f"{invalid_response}\n\n"
            "Repair it and return only valid JSON."
        )
        repair_messages = [
            {"role": "system", "content": repair_system_prompt},
            {"role": "user", "content": repair_prompt},
        ]
        repair_request_params = {"model": self.model, "messages": repair_messages}

        if self.model_provider == "azure":
            repair_request_params["response_format"] = {"type": "json_object"}

        repair_response = self.client.chat.completions.create(**repair_request_params)
        repaired_content = repair_response.choices[0].message.content
        return self._parse_json_response(repaired_content), repair_response

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
    ):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        request_params = {"model": self.model, "messages": messages}

        if return_json:
            if self.model_provider == "azure":
                request_params["response_format"] = {"type": "json_object"}
            else:
                messages[0]["content"] += (
                    "\nReturn only a valid JSON object with no markdown fences."
                )

        response = self.client.chat.completions.create(**request_params)

        if return_json:
            raw_content = response.choices[0].message.content
            try:
                model_response = self._parse_json_response(raw_content)
                if validator is not None:
                    model_response = validator(model_response)
            except (json.JSONDecodeError, ValueError) as exc:
                self._record_model_response(
                    response,
                    status="invalid_json_response",
                    error=str(exc),
                    raw_response=raw_content,
                )
                repaired_json, response = self._request_json_repair(
                    system_prompt,
                    prompt,
                    raw_content,
                    str(exc),
                )
                repair_raw_content = response.choices[0].message.content
                try:
                    model_response = repaired_json
                    if validator is not None:
                        model_response = validator(model_response)
                except ValueError as exc:
                    self._record_model_response(
                        response,
                        status="invalid_json_repair",
                        error=str(exc),
                        raw_response=repair_raw_content,
                    )
                    raise ValueError(
                        f"{self.name} returned invalid JSON after repair attempt: {exc}"
                    ) from exc
        else:
            model_response = response.choices[0].message.content

        self._record_model_response(response, model_response=model_response)
        return model_response

    def think(self, manager_instruction: str, execution_history: str, user_request: str):
        return self.think_in_session(
            manager_instruction=manager_instruction,
            execution_history=execution_history,
            assignment_history="No assignment steps yet.",
            user_request=user_request,
            worker_step=1,
            max_worker_steps=1,
        )

    def think_in_session(
        self,
        manager_instruction: str,
        execution_history: str,
        assignment_history: str,
        user_request: str,
        worker_step: int,
        max_worker_steps: int,
    ):
        tool_descriptions = self.toolbox.tools() or "No tools available."
        agent_system_prompt = agent_choose_tool_system.format(
            agent_descriptions=self.agent_personality,
            tool_descriptions=tool_descriptions,
        )
        prompt = agent_choose_tool_user.format(
            manager_instruction=manager_instruction,
            execution_step_history=execution_history,
            assignment_history=assignment_history,
            worker_step=f"{worker_step}/{max_worker_steps}",
            original_request=user_request,
        )
        return self._ask_agent(
            agent_system_prompt,
            prompt,
            return_json=True,
            validator=validate_worker_action,
        )

    def execute_tool(self, agent_response_dict: dict) -> ToolResult:
        tool_choice = agent_response_dict.get("tool")
        tool_input = agent_response_dict.get("args", {})
        tool_spec = self.toolbox.get(tool_choice)

        if tool_spec is None:
            return ToolResult.failure(f"Tool {tool_choice} not found in agent's toolbox.")

        print(
            colored(
                f"| Tool Choice Step | Tool {tool_choice} : Arguments {tool_input}",
                "light_magenta",
            )
        )

        try:
            response = tool_spec.func(**tool_input)
        except Exception as exc:
            return ToolResult.failure(
                error=f"Tool {tool_choice} failed with exception: {exc}",
                summary=f"Tool {tool_choice} execution failed.",
            )

        if isinstance(response, ToolResult):
            return response

        return ToolResult.ok(
            data=response,
            summary=f"Tool {tool_choice} executed successfully.",
        )


class CommandCentre(Agent):
    def __init__(self, name, tools: list, agent_mission: str, agent_personality: str):
        super().__init__(name, tools, agent_mission, agent_personality)

    def _get_agents_characteristics(self) -> str:
        agents_list = ""
        for name, values in self.agent_registry.items():
            if name == self.name:
                continue
            agents_list += (
                f"Agent name -- {name} -- Agent {name} || Mission {values['mission']} "
                f"|| Tools to used: {values['tools to use']} \n"
            )
        return agents_list

    def plan_next_step(self, user_request: str, steps_executed: str) -> dict:
        formatted_prompt = plan_next_step_user.format(
            original_request=user_request,
            steps_executed=steps_executed,
            avaliable_agents=self._get_agents_characteristics(),
        )
        planner_response = self._ask_agent(
            plan_next_step_system,
            formatted_prompt,
            return_json=True,
            validator=validate_planner_action,
        )
        return planner_response

    def synthesize_answer(self, user_request: str, steps_executed: str) -> str:
        formatted_prompt = synthesis_user.format(
            original_request=user_request,
            steps_executed=steps_executed,
        )
        return self._ask_agent(synthesis_system, formatted_prompt)
