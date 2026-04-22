from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents_training_facility import agents
from runtime.contracts import ToolResult, validate_planner_action
from tools import file_handler


class AgentTests(unittest.TestCase):
    def setUp(self):
        agents.Agent.agent_registry.clear()
        self.load_model_patch = patch.object(
            agents.Agent,
            "_load_model_settings",
            lambda _self: ("ollama", "test"),
        )
        self.client_patch = patch.object(
            agents.Agent,
            "_gpt_client",
            lambda _self: SimpleNamespace(),
        )
        self.load_model_patch.start()
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()
        self.load_model_patch.stop()
        agents.Agent.agent_registry.clear()

    def test_parse_json_response_handles_fenced_json_and_extra_text(self):
        agent = agents.Agent.__new__(agents.Agent)

        fenced = """```json
        {"type":"finish","reason":"done"}
        ```"""
        self.assertEqual(
            agent._parse_json_response(fenced),
            {"type": "finish", "reason": "done"},
        )

        noisy = 'Before text {"type":"done","summary":"ready"} after text'
        self.assertEqual(
            agent._parse_json_response(noisy),
            {"type": "done", "summary": "ready"},
        )

    def test_agent_loads_only_declared_tools(self):
        agent = agents.Agent("secretary", ["file_handler"], "mission", "personality")

        self.assertEqual(set(agent.available_functions), set(file_handler.TOOLS.keys()))
        self.assertNotIn("Path", agent.available_functions)
        self.assertNotIn("datetime", agent.available_functions)

    def test_execute_tool_wraps_exceptions(self):
        def boom():
            raise RuntimeError("kaboom")

        fake_module = SimpleNamespace(TOOLS={"boom": boom})
        with patch.dict(agents.available_tools, {"fake_tools": fake_module}, clear=False):
            agent = agents.Agent("tester", ["fake_tools"], "mission", "personality")
            result = agent.execute_tool({"type": "tool", "tool": "boom", "args": {}})

        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.success)
        self.assertIn("kaboom", result.error)

    def test_ask_agent_saves_structured_token_usage_to_json_path(self):
        class FakeCompletions:
            def create(self, **_kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"type":"done","summary":"ok"}'))],
                    usage=SimpleNamespace(completion_tokens=12, prompt_tokens=34),
                )

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

        with patch.object(agents.Agent, "_gpt_client", lambda _self: fake_client):
            saved_paths = []

            def fake_save_history(file_path):
                saved_paths.append(file_path)

            agents.Agent.token_usage.memory = []
            agents.Agent.token_usage.save_history = fake_save_history

            agent = agents.Agent("tester", ["utils_handler"], "mission", "personality")
            response = agent._ask_agent("system", "prompt", return_json=True)

        self.assertEqual(response, {"type": "done", "summary": "ok"})
        self.assertTrue(agents.Agent.token_usage.memory)
        last_entry = agents.Agent.token_usage.memory[-1]
        self.assertEqual(last_entry["agent"], "tester")
        self.assertEqual(last_entry["completion_tokens"], 12)
        self.assertEqual(last_entry["prompt_tokens"], 34)
        self.assertEqual(saved_paths[-1], agents.TOKEN_USAGE_PATH)

    def test_ask_agent_retries_when_model_returns_invalid_json(self):
        class FakeCompletions:
            def __init__(self):
                self.calls = 0

            def create(self, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    content = '{"type":"delegate","agent":"api","instruction":"Use'
                else:
                    content = '{"type":"delegate","agent":"api","instruction":"Use weather tool"}'

                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                    usage=SimpleNamespace(completion_tokens=3, prompt_tokens=7),
                )

        fake_completions = FakeCompletions()
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

        with patch.object(agents.Agent, "_gpt_client", lambda _self: fake_client):
            agents.Agent.token_usage.memory = []
            agents.Agent.token_usage.save_history = lambda _path: None

            agent = agents.Agent("tester", ["utils_handler"], "mission", "personality")
            response = agent._ask_agent("system", "prompt", return_json=True)

        self.assertEqual(
            response,
            {"type": "delegate", "agent": "api", "instruction": "Use weather tool"},
        )
        self.assertEqual(fake_completions.calls, 2)

    def test_ask_agent_retries_when_json_schema_is_invalid(self):
        class FakeCompletions:
            def __init__(self):
                self.calls = 0

            def create(self, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    content = '{"type":"delegate","agent":"api"}'
                else:
                    content = '{"type":"delegate","agent":"api","instruction":"Use weather tool"}'

                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                    usage=SimpleNamespace(completion_tokens=5, prompt_tokens=11),
                )

        fake_completions = FakeCompletions()
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

        with patch.object(agents.Agent, "_gpt_client", lambda _self: fake_client):
            agents.Agent.token_usage.memory = []
            agents.Agent.token_usage.save_history = lambda _path: None

            agent = agents.Agent("tester", ["utils_handler"], "mission", "personality")
            response = agent._ask_agent(
                "system",
                "prompt",
                return_json=True,
                validator=validate_planner_action,
            )

        self.assertEqual(
            response,
            {"type": "delegate", "agent": "api", "instruction": "Use weather tool"},
        )
        self.assertEqual(fake_completions.calls, 2)
        self.assertEqual(agents.Agent.token_usage.memory[0]["status"], "invalid_json_response")
        self.assertIn("instruction", agents.Agent.token_usage.memory[0]["error"])


if __name__ == "__main__":
    unittest.main()
