import json
import unittest
from pathlib import Path

from runtime.contracts import ToolResult
from runtime.orchestrator import AgentOrchestrator
from runtime import orchestrator as orchestrator_module
from tools.file_handler import read_json


class FakeManager:
    def __init__(self, planned_actions, final_answer="final answer"):
        self.planned_actions = list(planned_actions)
        self.final_answer = final_answer
        self.synthesis_calls = 0

    def plan_next_step(self, user_request, steps_executed):
        return self.planned_actions.pop(0)

    def synthesize_answer(self, user_request, steps_executed):
        self.synthesis_calls += 1
        return self.final_answer


class FakeWorker:
    def __init__(self, thought_action, tool_result=None):
        if isinstance(thought_action, list):
            self.thought_actions = list(thought_action)
        else:
            self.thought_actions = [thought_action]

        if isinstance(tool_result, list):
            self.tool_results = list(tool_result)
        elif tool_result is None:
            self.tool_results = [ToolResult.ok(summary="tool executed")]
        else:
            self.tool_results = [tool_result]

        self.think_calls = []
        self.execute_calls = []

    def think_in_session(
        self,
        manager_instruction,
        execution_history,
        assignment_history,
        user_request,
        worker_step,
        max_worker_steps,
    ):
        self.think_calls.append(
            {
                "manager_instruction": manager_instruction,
                "execution_history": execution_history,
                "assignment_history": assignment_history,
                "user_request": user_request,
                "worker_step": worker_step,
                "max_worker_steps": max_worker_steps,
            }
        )
        if self.thought_actions:
            return self.thought_actions.pop(0)
        return {"type": "done", "summary": "No more work."}

    def execute_tool(self, action):
        self.execute_calls.append(action)
        if self.tool_results:
            return self.tool_results.pop(0)
        return ToolResult.ok(summary="tool executed")


class RuntimeTests(unittest.TestCase):
    def _make_input(self, responses):
        iterator = iter(responses)

        def fake_input(_prompt):
            return next(iterator)

        return fake_input

    def test_tool_route_executes_with_validated_args_and_finishes(self):
        outputs = []
        manager = FakeManager(
            [
                {"type": "delegate", "agent": "worker", "instruction": "Read the data"},
                {"type": "finish", "reason": "Enough information is available."},
            ]
        )
        worker = FakeWorker(
            [
                {"type": "tool", "tool": "read_json", "args": {"filename": "sample.json"}},
                {"type": "done", "summary": "The delegated task is complete."},
            ],
            [ToolResult.ok(data={"ok": True}, summary="Read JSON file.")],
        )

        runtime = AgentOrchestrator(
            manager,
            {"worker": worker},
            input_func=self._make_input(["q"]),
            output_func=outputs.append,
            sleep_func=lambda _: None,
            max_iterations=3,
        )
        runtime._save_execution_history = lambda: None
        runtime._save_conversation_history = lambda: None

        final_answer = runtime.run(initial_request="Please inspect the file")

        self.assertEqual(final_answer, "final answer")
        self.assertEqual(
            worker.execute_calls,
            [{"type": "tool", "tool": "read_json", "args": {"filename": "sample.json"}}],
        )
        self.assertEqual(len(worker.think_calls), 2)
        self.assertEqual(manager.synthesis_calls, 1)

    def test_needs_user_input_routes_through_manager(self):
        prompts = []
        manager = FakeManager(
            [
                {"type": "delegate", "agent": "worker", "instruction": "Need one detail"},
                {"type": "finish", "reason": "The clarification was collected."},
            ]
        )
        worker = FakeWorker(
            {
                "type": "needs_user_input",
                "question": "Which file should I open?",
                "reason": "The request does not specify the filename.",
            }
        )

        def fake_input(prompt):
            prompts.append(prompt)
            if len(prompts) == 1:
                return "data.json"
            return "q"

        runtime = AgentOrchestrator(
            manager,
            {"worker": worker},
            input_func=fake_input,
            output_func=lambda message: None,
            sleep_func=lambda _: None,
            max_iterations=3,
        )
        runtime._save_execution_history = lambda: None
        runtime._save_conversation_history = lambda: None

        runtime.run(initial_request="Open the file for me")

        self.assertTrue(prompts)
        self.assertIn("Which file should I open?", prompts[0])
        self.assertIn("data.json", runtime.requests_history.recall_all())

    def test_done_action_triggers_synthesis_without_tool_execution(self):
        manager = FakeManager(
            [
                {"type": "delegate", "agent": "worker", "instruction": "Summarize findings"},
                {"type": "finish", "reason": "The delegated work is complete."},
            ]
        )
        worker = FakeWorker({"type": "done", "summary": "The answer is ready."})

        runtime = AgentOrchestrator(
            manager,
            {"worker": worker},
            input_func=self._make_input(["q"]),
            output_func=lambda message: None,
            sleep_func=lambda _: None,
            max_iterations=2,
        )
        runtime._save_execution_history = lambda: None
        runtime._save_conversation_history = lambda: None

        final_answer = runtime.run(initial_request="What did you learn?")

        self.assertEqual(final_answer, "final answer")
        self.assertEqual(worker.execute_calls, [])
        self.assertEqual(manager.synthesis_calls, 1)

    def test_worker_can_take_multiple_steps_in_one_delegate_session(self):
        manager = FakeManager(
            [
                {"type": "delegate", "agent": "worker", "instruction": "Locate and read the file"},
                {"type": "finish", "reason": "The file contents are now available."},
            ]
        )
        worker = FakeWorker(
            [
                {"type": "tool", "tool": "check_if_file_exists", "args": {"filename": "my_wardrobe.json"}},
                {
                    "type": "tool",
                    "tool": "read_json",
                    "args": {"filename": "F:/repo/data/my_wardrobe.json"},
                },
                {"type": "done", "summary": "The file was located and parsed."},
            ],
            [
                ToolResult.ok(
                    data="F:/repo/data/my_wardrobe.json",
                    summary="Found the file path.",
                ),
                ToolResult.ok(
                    data={"Upper Body": ["T-shirt"]},
                    summary="Read the wardrobe JSON.",
                ),
            ],
        )

        runtime = AgentOrchestrator(
            manager,
            {"worker": worker},
            input_func=self._make_input(["q"]),
            output_func=lambda message: None,
            sleep_func=lambda _: None,
            max_iterations=2,
            max_worker_steps=4,
        )
        runtime._save_execution_history = lambda: None
        runtime._save_conversation_history = lambda: None

        final_answer = runtime.run(initial_request="Open the wardrobe file")

        self.assertEqual(final_answer, "final answer")
        self.assertEqual(
            worker.execute_calls,
            [
                {"type": "tool", "tool": "check_if_file_exists", "args": {"filename": "my_wardrobe.json"}},
                {
                    "type": "tool",
                    "tool": "read_json",
                    "args": {"filename": "F:/repo/data/my_wardrobe.json"},
                },
            ],
        )
        self.assertIn("Found the file path.", worker.think_calls[1]["assignment_history"])
        self.assertEqual(worker.think_calls[0]["max_worker_steps"], 4)

    def test_structured_history_keeps_event_metadata(self):
        manager = FakeManager(
            [
                {"type": "delegate", "agent": "worker", "instruction": "Read the data"},
                {"type": "finish", "reason": "Enough information is available."},
            ]
        )
        worker = FakeWorker(
            [
                {"type": "tool", "tool": "read_json", "args": {"filename": "sample.json"}},
                {"type": "done", "summary": "Completed."},
            ],
            [ToolResult.ok(data={"ok": True}, summary="Read JSON file.")],
        )

        runtime = AgentOrchestrator(
            manager,
            {"worker": worker},
            input_func=self._make_input(["q"]),
            output_func=lambda message: None,
            sleep_func=lambda _: None,
            max_iterations=2,
        )
        runtime._save_execution_history = lambda: None
        runtime._save_conversation_history = lambda: None

        runtime.run(initial_request="Please inspect the file")

        raw_history = runtime.step_history.recall_raw()
        self.assertTrue(raw_history)
        self.assertEqual(raw_history[0]["event_type"], "user_request")
        self.assertIn("timestamp", raw_history[0])
        self.assertTrue(any(entry["event_type"] == "tool_result" for entry in raw_history))

    def test_conversation_stays_open_for_second_question_until_exit(self):
        manager = FakeManager(
            [
                {"type": "finish", "reason": "First answer is ready."},
                {"type": "finish", "reason": "Second answer is ready."},
            ],
            final_answer="final answer",
        )

        runtime = AgentOrchestrator(
            manager,
            {},
            input_func=self._make_input(["Second question", "q"]),
            output_func=lambda message: None,
            sleep_func=lambda _: None,
            max_iterations=1,
        )
        runtime._save_execution_history = lambda: None
        runtime._save_conversation_history = lambda: None

        final_answer = runtime.run(initial_request="First question")

        self.assertEqual(final_answer, "final answer")
        self.assertIn("First question", runtime.requests_history.recall_all())
        self.assertIn("Second question", runtime.requests_history.recall_all())
        self.assertEqual(manager.synthesis_calls, 2)

    def test_read_json_returns_standard_tool_result(self):
        temp_dir = Path("tests/.tmp")
        temp_dir.mkdir(exist_ok=True)
        json_file = temp_dir / "sample.json"
        json_file.write_text(json.dumps({"name": "Ada"}), encoding="utf-8")

        try:
            result = read_json(str(json_file))
        finally:
            if json_file.exists():
                json_file.unlink()

        self.assertIsInstance(result, ToolResult)
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"name": "Ada"})

    def test_record_step_persists_conversation_history_to_json(self):
        temp_dir = Path("tests/.tmp")
        temp_dir.mkdir(exist_ok=True)
        conversation_file = temp_dir / "conversation_history_test.json"
        if conversation_file.exists():
            conversation_file.unlink()

        original_path = orchestrator_module.CONVERSATION_HISTORY_PATH
        orchestrator_module.CONVERSATION_HISTORY_PATH = str(conversation_file)

        try:
            manager = FakeManager([])
            runtime = AgentOrchestrator(
                manager,
                {},
                input_func=self._make_input(["q"]),
                output_func=lambda message: None,
                sleep_func=lambda _: None,
                max_iterations=1,
            )
            runtime._record_step("user_request", request="Hello there")

            self.assertTrue(conversation_file.exists())
            payload = json.loads(conversation_file.read_text(encoding="utf-8"))
            self.assertEqual(payload[-1]["event_type"], "user_request")
            self.assertEqual(payload[-1]["request"], "Hello there")
            self.assertIn("session_id", payload[-1])
        finally:
            orchestrator_module.CONVERSATION_HISTORY_PATH = original_path
            if conversation_file.exists():
                conversation_file.unlink()

    def test_run_resets_conversation_history_file_to_current_conversation_only(self):
        temp_dir = Path("tests/.tmp")
        temp_dir.mkdir(exist_ok=True)
        conversation_file = temp_dir / "conversation_history_reset_test.json"
        conversation_file.write_text(
            json.dumps([{"event_type": "old_event", "request": "stale"}], indent=4),
            encoding="utf-8",
        )

        original_path = orchestrator_module.CONVERSATION_HISTORY_PATH
        orchestrator_module.CONVERSATION_HISTORY_PATH = str(conversation_file)

        try:
            manager = FakeManager(
                [{"type": "finish", "reason": "Done."}],
                final_answer="fresh final answer",
            )
            runtime = AgentOrchestrator(
                manager,
                {},
                input_func=self._make_input(["q"]),
                output_func=lambda message: None,
                sleep_func=lambda _: None,
                max_iterations=1,
            )

            runtime.run(initial_request="Fresh request")

            payload = json.loads(conversation_file.read_text(encoding="utf-8"))
            self.assertTrue(payload)
            self.assertFalse(any(entry.get("event_type") == "old_event" for entry in payload))
            self.assertEqual(payload[0]["event_type"], "user_request")
            self.assertEqual(payload[0]["request"], "Fresh request")
        finally:
            orchestrator_module.CONVERSATION_HISTORY_PATH = original_path
            if conversation_file.exists():
                conversation_file.unlink()


if __name__ == "__main__":
    unittest.main()
