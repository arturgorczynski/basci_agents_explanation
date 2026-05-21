# End-to-end explanation of the multi-agent runtime

This document explains, end to end, the codebase that lives in this repository.
Read it top to bottom and you can confidently explain to anyone:

- what the project is,
- how a single user message becomes a final answer,
- what every module does and why it exists,
- which agent sees what,
- how the history is built and persisted,
- how the runtime keeps itself safe.

Every reference is a clickable link to the actual source.

---

## Table of contents

1. [TL;DR](#1-tldr--what-this-codebase-is)
2. [Repository map](#2-repository-map)
3. [End-to-end lifecycle of one request](#3-end-to-end-lifecycle-of-one-request)
4. [Module-by-module reference](#4-module-by-module-reference)
   1. [runtime/orchestrator.py](#41-runtimeorchestratorpy)
   2. [runtime/contracts.py](#42-runtimecontractspy)
   3. [runtime/tracing.py](#43-runtimetracingpy)
   4. [agents_training_facility/agents.py](#44-agents_training_facilityagentspy)
   5. [agents_training_facility/personalities.py](#45-agents_training_facilitypersonalitiespy)
   6. [prompts/prompts.py](#46-promptspromptspy)
   7. [memory/conversation_history.py](#47-memoryconversation_historypy)
   8. [memory/memory_manager.py](#48-memorymemory_managerpy)
   9. [toolbox/toolbox.py](#49-toolboxtoolboxpy)
   10. [tools/path_policy.py](#410-toolspath_policypy)
   11. [tools/file_handler.py — Secretary](#411-toolsfile_handlerpy--secretary)
   12. [tools/programer.py — Python Developer](#412-toolsprogramerpy--python-developer)
   13. [tools/data_manager.py — Data Manager](#413-toolsdata_managerpy--data-manager)
   14. [tools/apis.py — API agent](#414-toolsapispy--api-agent)
   15. [ui/app.py — Gradio app](#415-uiapppy--gradio-app)
   16. [ui/controller.py — SessionController](#416-uicontrollerpy--sessioncontroller)
   17. [ui/formatters.py and ui/archive.py](#417-uiformatterspy-and-uiarchivepy)
   18. [ui/styles.py](#418-uistylespy)
5. [Who sees what — the visibility model](#5-who-sees-what--the-visibility-model)
6. [How history is built — the event lifecycle](#6-how-history-is-built--the-event-lifecycle)
7. [Runtime safety rails](#7-runtime-safety-rails)
8. [Configuration surface (`.env`)](#8-configuration-surface-env)
9. [Cheat sheet — short talking points](#9-cheat-sheet--short-talking-points)

---

## 1. TL;DR — what this codebase is

This is a **manager-led multi-agent runtime**. One LLM agent named **Bob the Manager** plans the work one step at a time. It never calls a tool itself. Instead, it delegates each step to one of four specialist worker agents, each backed by its own private toolbox:

- **`pythondeveloper`** — writes and runs Python inside the project `.venv`.
- **`secretary`** — finds and reads files, writes text files.
- **`data_manager`** — semantic search over a local FAISS document index plus NewsData news lookup.
- **`api`** — geolocation, weather, and Tavily web search.

Every LLM-to-runtime message is **strict JSON** validated against a schema. Every tool returns the same shape — a `ToolResult` dataclass. Every interesting event is recorded both in a structured `ConversationHistory` (used to build the manager's "planner context") and in a per-session JSONL trace file (used by the optional Gradio UI). File access is enforced by a central policy module, and the only writable directory is `coding_output/`.

```
                            ┌───────────────────────────────────┐
   user ────────────────────►  Manager  (CommandCentre)         │
                            │       plan_next_step (JSON)       │
                            └───┬───────────────┬───────────────┘
                                │               │
                       delegate │               │ answer_user / finish / talk_with_user
                                ▼               │
                ┌──────────────────────┐        │
                │   Worker (Agent)     │        │
                │   think_in_session   │        │
                │   tool → ToolResult  │        │
                │   …loop up to 6×…    │        │
                │   done (results)     │        │
                └──────────┬───────────┘        │
                           │  request_results   │
                           └────────────────────► manager re-plans …
                                                 │
                                                 ▼
                                       synthesize_answer
                                                 │
                                                 ▼
                                              user
```

The manager loops until it can either answer directly, call `finish` (which triggers the synthesis pass), give up due to budget, or ask the user for clarification. The runtime supports running on Azure OpenAI, plain OpenAI, or local Ollama — chosen by `MODEL_PROVIDER`.

---

## 2. Repository map

The repo is a flat layout: a top-level entrypoint (`main.py`) plus everything else under `src/agentic_system/`. The `.venv/` directory is the project's Python virtual environment and is intentionally fenced off from the runtime.

```
basci_agents_explanation-main/
├── main.py                              ← entrypoint
├── README.md
├── hooman/
│   ├── explanation.md                   ← THIS FILE
│   └── pres/                            ← slide-deck presentation app
└── src/agentic_system/
    ├── runtime/
    │   ├── __init__.py                  ← re-exports AgentOrchestrator, build_default_runtime
    │   ├── orchestrator.py              ← control loop
    │   ├── contracts.py                 ← ToolResult, JSON validators, make_json_safe
    │   ├── tracing.py                   ← TraceSink protocol + JSONL session traces
    │   └── _orchestrator_walkthrough.py ← simplified mirror used purely as documentation
    ├── agents_training_facility/
    │   ├── agents.py                    ← Agent base + CommandCentre (manager)
    │   └── personalities.py             ← system prompts/descriptions per role
    ├── prompts/
    │   └── prompts.py                   ← six prompt templates (system + user)
    ├── memory/
    │   ├── conversation_history.py      ← structured session history + planner context renderer
    │   └── memory_manager.py            ← minimal Memory list with persistence
    ├── toolbox/
    │   └── toolbox.py                   ← ToolSpec / ToolBox registry
    ├── tools/
    │   ├── path_policy.py               ← sandbox rules (read/write/exec + .venv)
    │   ├── file_handler.py              ← Secretary tools
    │   ├── programer.py                 ← Python Developer tools
    │   ├── data_manager.py              ← FAISS + NewsData tools
    │   └── apis.py                      ← geolocation, weather, Tavily
    ├── ui/
    │   ├── app.py                       ← Gradio Blocks app
    │   ├── controller.py                ← threaded SessionController
    │   ├── formatters.py                ← event→HTML formatters
    │   ├── archive.py                   ← load/list session traces
    │   └── styles.py                    ← injected CSS/JS
    ├── data/                            ← sample inputs + documents/ for the vector DB
    └── coding_output/                   ← the only directory the runtime is allowed to write to
```

Live entry points:

- [main.py](../main.py) — CLI entrypoint.
- [src/agentic_system/ui/app.py](../src/agentic_system/ui/app.py) — UI entrypoint via `.venv\Scripts\python.exe -m ui.app`.

---

## 3. End-to-end lifecycle of one request

Follow a single user message from keystroke to final answer.

### 3.1 Boot

[main.py](../main.py) does three things:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "agentic_system"))
load_dotenv()
from runtime import build_default_runtime
build_default_runtime().run()
```

It (a) prepends `src/agentic_system/` to `sys.path` so that internal imports like `from runtime import …` resolve, (b) loads `.env`, and (c) builds the default runtime and starts it. Stdout/stderr are reconfigured to UTF-8 so Polish characters survive on Windows consoles.

### 3.2 Runtime build

[`build_default_runtime` in src/agentic_system/runtime/orchestrator.py:486-552](../src/agentic_system/runtime/orchestrator.py#L486-L552):

1. **Vector DB warm-up.** Calls `data_manager_tools.ensure_documents_vector_db()` — if the FAISS index does not exist yet, it is built immediately so that the first user query is fast.
2. **Manager construction.** `CommandCentre("manager", [], brain_desc, brain_system)` — the manager has *no* tools (empty `module_list`).
3. **Four workers.** Each `Agent(name, [tool_module_name], desc, system)` registers itself in the class-level `Agent.agent_registry`.
4. **Agents dict.** Maps `name → instance` for the orchestrator's delegation lookup.
5. Returns an `AgentOrchestrator` wired with `max_iterations=12` and `max_worker_steps=6`.

### 3.3 Session start

[`AgentOrchestrator.run` in orchestrator.py:367-484](../src/agentic_system/runtime/orchestrator.py#L367-L484):

- `_reset_conversation_state()` mints a fresh `session_id` (`YYYYMMDD-HHMMSS`), deletes `memory.txt`, `conversation_history.json`, and `conversation_raw_events.json`, then constructs a new `ConversationHistory`.
- If no `initial_request` was provided programmatically, the user is prompted for one.
- The trace sink emits `session_start` with the iteration/budget metadata.

### 3.4 Outer loop — one runtime, many requests

```python
while True:
    self.conversation_history.start_request(user_request, started_at=...)
    self._record_step("user_request", request=user_request)
    ...
```

A single runtime can serve many user requests in sequence. After every finished request the user is prompted with `"Send the next request:"`. Words in `EXIT_COMMANDS` (`q`, `quit`, `exit`, `bye`, `no`, `thanks`, `thank you`) end the session.

### 3.5 Inner loop — manager plans one step at a time

Per request, the runtime runs up to `max_iterations=12` planner iterations:

```python
planner_action = self.manager.plan_next_step(
    self._planner_context(last_n=self.steps_to_track),
)
```

`_planner_context` calls `ConversationHistory.render_planner_context(last_n=15)`, which produces a single string with up to three labeled sections — `SUMMARY`, `RECENTLY COMPLETED REQUESTS`, and `CURRENT REQUEST` (whose `EXECUTION_STEPS` only contains events the manager is allowed to see — see [Section 5](#5-who-sees-what--the-visibility-model)).

The manager's reply MUST be one of four JSON shapes ([validated in contracts.py:87-122](../src/agentic_system/runtime/contracts.py#L87-L122)):

```json
{"type":"answer_user","answer":"..."}
{"type":"delegate","agent":"...","instruction":"..."}
{"type":"talk_with_user","question":"..."}
{"type":"finish","reason":"..."}
```

What happens for each:

| Action | Effect |
| --- | --- |
| `answer_user` | Print the answer, record `final_answer`, finalize the request. Done. |
| `talk_with_user` | Call `_talk_with_user(question)`: prompt the user, record `user_clarification`, keep iterating. |
| `finish` | Call `_run_synthesis()` → `manager.synthesize_answer(context)`. Final answer written and request finalized. |
| `delegate` | Look up the named worker in `agents_dict`; if missing, record `routing_error`; otherwise run `_run_worker_session(agent_name, worker, instruction)`. |

### 3.6 Worker session

[`_run_worker_session` in orchestrator.py:276-365](../src/agentic_system/runtime/orchestrator.py#L276-L365) creates a fresh `Memory(is_structured=True)` named `assignment_history`. This is the only context the worker will see besides its system prompt and the manager's `instruction`. Up to `max_worker_steps=6` iterations:

1. `worker_action = active_agent.think_in_session(manager_instruction, assignment_history_text)`.
2. Validate (`validate_worker_action`) — must be one of:

   ```json
   {"type":"tool","tool":"<name>","args":{...}}
   {"type":"done","request_results":"<string>", "request_raw_data": <optional any>}
   ```

3. Record the worker_action in both the assignment_history (private to this session) and the global `ConversationHistory` (`worker_action` event type — *not* visible to the manager).
4. If `done`: record `worker_done` (visible to the manager), return.
5. Otherwise: `tool_result = active_agent.execute_tool(worker_action)`. Every tool returns a `ToolResult`. Non-`ToolResult` returns are wrapped; exceptions become `ToolResult.failure(...)` with traceback.
6. Record `tool_result` in the assignment_history (visible to the worker on its next iteration) and in the global history (hidden from the manager).
7. Sleep 2 seconds (configurable via `sleep_func`; UI sets it to 0).

If the worker exhausts its 6 steps without returning `done`, `worker_budget_exhausted` is recorded — and *that* event is one of the manager's visible events.

### 3.7 Synthesis

When the manager returns `finish`, `_run_synthesis` calls `manager.synthesize_answer(_planner_context())`. The `synthesize_answer` method is the *only* place where the manager runs the LLM in plain-text mode (no JSON contract). It receives the same three-section context plus a different system prompt ([prompts.py:120-132](../src/agentic_system/prompts/prompts.py#L120-L132)) instructing it to write the final reply.

### 3.8 Persistence at every step

- After every `_record_step`, the orchestrator calls `self._save_conversation_history()` which writes both `memory/conversation_history.json` (normalized snapshot) and `memory/conversation_raw_events.json` (the raw event log).
- `memory.txt` — a human-readable plain-text dump of `render_planner_context(last_n=15)` — is rewritten after every worker step and after every request completes.
- `memory/execution_cost/token_usage.json` — every `_record_model_response` appends one entry with `prompt_tokens`, `completion_tokens`, and the model's raw response (see [agents.py:213-239](../src/agentic_system/agents_training_facility/agents.py#L213-L239)).
- `memory/ui_traces/<session_id>.jsonl` — one line per emitted trace event.

### 3.9 The ASCII sequence

```
 USER ──"do X"──► AgentOrchestrator.run
                         │
                         ▼
                  start_request(active=X)
                         │
                ┌────────┴────────────────────────────────────────────────┐
                │  for iteration in 1..12:                                │
                │                                                         │
                │    Manager._ask_agent(plan_next_step_*) ──► JSON action │
                │                                                         │
                │    answer_user ──► final_answer ──► finalize ─► break   │
                │    talk_with_user ──► _talk_with_user ─► loop continues │
                │    finish ──► synthesize_answer ──► finalize ─► break   │
                │    delegate ──► _run_worker_session(name, instruction): │
                │                                                         │
                │       for step in 1..6:                                 │
                │          Worker._ask_agent(agent_choose_tool_*)         │
                │          if "done": record worker_done; return          │
                │          else execute_tool → ToolResult                 │
                │          assignment_history.extend(tool_result)         │
                │       record worker_budget_exhausted                    │
                └─────────────────────────────────────────────────────────┘
                         │
                         ▼
                  _prompt_for_next_request  ─── exit word? ─► stop
                         │
                         └────────────────────► loop with new user_request
```

---

## 4. Module-by-module reference

For each module I follow the same structure: **purpose → why it exists → what it exposes → how others use it.**

### 4.1 `runtime/orchestrator.py`

[src/agentic_system/runtime/orchestrator.py](../src/agentic_system/runtime/orchestrator.py)

**Purpose.** The control loop. Owns the user-facing CLI prompts, the manager–worker delegation, the request bookkeeping, and the persistence hooks.

**Why it exists.** Agents are just LLM-backed JSON producers; the orchestrator is what gives the system a deterministic shape. It is the only place that knows *when* to call the manager, *which* worker handles a delegation, *how many* iterations are allowed, and *what* to write to disk.

**Key surfaces.**

- `class AgentOrchestrator` (line 30). Constructor parameters: the manager, the `agents_dict`, `steps_to_track=15` (how many recent events to expose to the planner), `max_iterations=12` (planner cap), `max_worker_steps=6` (worker cap), `input_func`/`output_func`/`sleep_func` (so the UI can replace stdin/stdout/sleep), and a `trace_sink`.
- `EXIT_COMMANDS` class attribute — the only place exit words live.
- `_emit(message, color)` — writes to `output_func` *and* emits a `console_output` trace event so the UI can replay console output.
- `_planner_context(last_n)` — thin wrapper around `ConversationHistory.render_planner_context`.
- `_make_event(event_type, **payload)` — adds `timestamp` and `session_id`. Every event recorded passes through here.
- `_record_step(event_type, **payload)` — records the event into `ConversationHistory`, saves both JSON files, and emits the same event to the trace sink.
- `_talk_with_user(question)` — emits a `user_input_requested` trace, blocks on `input_func`, records a `user_clarification` event.
- `_run_synthesis()` — emits `synthesis_start`, calls the manager's `synthesize_answer`, records `final_answer`.
- `_finalize_completed_request(final_answer)` — moves the active request to `completed_requests`, then calls `_maybe_compact_completed_history`.
- `_maybe_compact_completed_history()` — at ≥ 7 unsummarized completed requests, summarizes the oldest 5 by concatenating their per-request `summary` strings into the rolling `history_summary` (the LLM is NOT used for this compaction — it is purely deterministic string assembly via `_fallback_history_window_summary`).
- `_run_worker_session(agent_name, worker, instruction)` — the per-worker loop described in [Section 3.6](#36-worker-session).
- `run(initial_request=None)` — the public driver.
- `build_default_runtime(...)` — factory function; only place that knows which agents exist by default.

**Where the file-level constants come from.**

```python
_MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
CONVERSATION_HISTORY_PATH = str(_MEMORY_DIR / "conversation_history.json")
CONVERSATION_RAW_EVENTS_PATH = str(_MEMORY_DIR / "conversation_raw_events.json")
```

These resolve relative to the source file, not the user's working directory, which is what lets you launch the runtime from anywhere.

**Companion file.** [runtime/_orchestrator_walkthrough.py](../src/agentic_system/runtime/_orchestrator_walkthrough.py) is **not** imported anywhere. It is a stripped, comment-heavy mirror of the orchestrator with no UI/trace concerns. It exists purely so a maintainer can read the runtime in 200 lines and understand the structure before going into the noisy production version. Treat it as live documentation.

### 4.2 `runtime/contracts.py`

[src/agentic_system/runtime/contracts.py](../src/agentic_system/runtime/contracts.py)

**Purpose.** The lingua franca between the runtime, tools, and LLM JSON.

**What it exposes.**

- `class ToolResult` — `frozen=True` dataclass:
  ```python
  @dataclass(frozen=True)
  class ToolResult:
      success: bool
      data: Any = None
      summary: str = ""
      error: str | None = None
  ```
  Plus two class methods: `ToolResult.ok(data, summary)` and `ToolResult.failure(error, data, summary)`. **Every** tool either returns one of these or its return is wrapped by `Agent.execute_tool`. Nothing else crosses the tool/agent boundary.
- `summarize_tool_result(result)` — produces the console-friendly preview line. Used by `orchestrator._emit("| Step Execution | ...", "magenta")`.
- `make_json_safe(value)` — recursively coerces pandas DataFrames (into `{type, shape, preview}`), tuples/lists/dicts, and anything else into JSON-serializable forms. This is critical because the conversation history is JSON, but tools occasionally return DataFrames.
- `validate_planner_action(action)` — accepts only the four planner shapes (`answer_user`, `delegate`, `talk_with_user`, `finish`). Raises `ValueError` otherwise. The orchestrator never has to defensively parse the manager's output — the validator is the gate.
- `validate_worker_action(action)` — same idea for worker actions (`tool` or `done`).

**Why it exists.** Strict contracts at the LLM boundary mean every "the model said something weird" failure becomes a single, well-located `invalid_json_response` event with a known error message instead of a cascade of `AttributeError` deep inside the orchestrator. If the JSON is invalid the call site (`_ask_agent` in agents.py) records the failure, emits a `model_call` trace with `status="invalid_json_response"`, and raises a `ValueError` carrying the agent's name.

### 4.3 `runtime/tracing.py`

[src/agentic_system/runtime/tracing.py](../src/agentic_system/runtime/tracing.py)

**Purpose.** A pluggable event log decoupled from any UI.

**What it exposes.**

- `TraceSink` protocol — three methods: `start_session(session_id, metadata=None)`, `emit(event_type, *, agent, phase, payload, prompt, response, raw_response, token_usage)`, `clear_session()`.
- `NullTraceSink` — default for the CLI; every method is a no-op.
- `SessionTraceSink` — writes one JSONL line per event into `memory/ui_traces/<session_id>.jsonl`, holds an in-memory `sequence` counter, and forwards each event to an optional `listener` callable. The UI uses the listener hook to push events into a `queue.Queue` that drives Gradio rendering.
- `load_trace_events(session_id_or_path)` — reads a previously persisted JSONL trace file back into a Python list. Used by `ui/archive.py` to replay archived sessions in read-only mode.
- `DEFAULT_TRACE_DIR` — `<repo>/src/agentic_system/memory/ui_traces/`.

**Why it exists.** The orchestrator should not know whether a UI is attached. By dependency-injecting a `TraceSink`, the same orchestrator runs identically with a `NullTraceSink` (CLI) or a `SessionTraceSink` (UI). The trace format is JSONL on purpose: each line is a complete event, so appending is atomic, partial sessions are still readable, and replay is trivially streamable.

The full event schema written to disk:

```python
event = {
    "session_id": str,
    "sequence": int,             # monotonic per session
    "timestamp": "YYYY-MM-DDTHH:MM:SS",
    "event_type": str,
    "agent": str | None,
    "phase": str | None,         # "manager" | "worker" | "synthesis" | "runtime" | None
    "payload": dict,             # event-specific data (always JSON-safe via make_json_safe)
    "prompt": {"system": ..., "user": ...} | None,
    "response": Any | None,
    "raw_response": str | None,
    "token_usage": {"input_tokens": int, "output_tokens": int, "total_tokens": int} | None,
    "metadata": dict | None,
}
```

### 4.4 `agents_training_facility/agents.py`

[src/agentic_system/agents_training_facility/agents.py](../src/agentic_system/agents_training_facility/agents.py)

**Purpose.** The actual LLM-backed agents.

**Two classes.**

- `Agent` — the base class used for every worker.
- `CommandCentre(Agent)` — the manager; same machinery but with extra methods `plan_next_step` and `synthesize_answer`, plus the ability to enumerate registered peers.

**Construction (`Agent.__init__`).**

The constructor takes `name`, `module_list` (the tool *module* names the agent is allowed to use — for example `["file_handler"]`), `agent_mission` (a short description string), `agent_personality` (the long system prompt), and an optional `trace_sink`. It:

1. Loads model provider/model from env (`_load_model_settings`).
2. Constructs the OpenAI/AzureOpenAI/Ollama-via-OpenAI client (`_gpt_client`).
3. Loops through `module_list`, looks each name up in the module-level `available_tools` dict, and pulls that module's `TOOLS` mapping (a `{tool_name: callable}` dict every tool module exposes). Those callables are bulk-registered into a fresh `ToolBox`.
4. Stores the agent in the class-level `Agent.agent_registry` dictionary, mapping `name → {mission, description, tools to use, tools_detailed, field_agent}`. The manager later reads this registry to learn its delegation surface.

**Class-level shared state.**

```python
class Agent:
    agent_registry = {}
    token_usage = Memory(is_structured=True, has_history=TOKEN_USAGE_PATH)
```

`agent_registry` and `token_usage` are class attributes — every agent shares them. The token ledger is rehydrated from disk on the first import, so token usage survives runs.

**Model provider selection (`_load_model_settings`, `_gpt_client`).**

`MODEL_PROVIDER` is one of `azure`, `openai`, `ollama`. The model name comes from the matching env variable. Azure endpoints ending in `/openai/v1` use the new OpenAI-compatible Azure shape; otherwise an `AzureOpenAI` client is used with `api_version`. OpenAI honors an optional `OPENAI_BASE_URL`. Ollama goes through its OpenAI-compatible endpoint.

**`_ask_agent` — the only LLM call site.**

```python
def _ask_agent(self, system_prompt, prompt="", return_json=False,
               validator=None, phase=None):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": prompt},
    ]
    request_params = {"model": self.model, "messages": messages}

    if return_json:
        messages[0]["content"] += (
            "\nReturn exactly one valid JSON object. "
            "Do not wrap it in markdown fences. "
            "Do not add commentary or any text before or after the JSON object."
        )
        if self.model_provider in {"azure", "openai"}:
            request_params["response_format"] = {"type": "json_object"}
        else:
            messages[0]["content"] += "\nUse strict JSON syntax with double quotes."

    response = self.client.chat.completions.create(**request_params)
    ...
```

Note the two paths: when JSON is required, the *system* prompt gets the "exactly one valid JSON object" suffix appended, and the API's `response_format` is set to `json_object` on Azure/OpenAI. On Ollama (no `response_format` support) the suffix is supplemented with a strict-JSON reminder. After the call, the JSON branch (a) strips optional ```` ``` ```` fencing, (b) `json.loads`, (c) runs the validator. Failures raise `ValueError` after recording the bad attempt as an `invalid_json_response` token-usage entry and a `model_call` trace with `status="invalid_json_response"`.

Every successful call invokes both:

- `_record_model_response(response, ...)` — appends to the persistent `token_usage` ledger.
- `_emit_model_trace("model_call", ...)` — emits a structured trace event with prompts, response, and usage.

**`think_in_session` (worker planning).**

```python
def think_in_session(self, manager_instruction, assignment_history):
    tool_descriptions = self.toolbox.tools() or "No tools available."
    agent_system_prompt = agent_choose_tool_system.format(
        agent_descriptions=self.agent_personality,
        tool_descriptions=tool_descriptions,
    )
    prompt = agent_choose_tool_user.format(
        manager_instruction=manager_instruction,
        assignment_history=assignment_history,
    )
    return self._ask_agent(agent_system_prompt, prompt,
                           return_json=True,
                           validator=validate_worker_action,
                           phase="worker")
```

The worker sees exactly two things: its system prompt (with tools injected) and a user prompt containing only the manager's instruction + the worker's own short assignment history. Nothing else.

**`execute_tool` (the tool-call surface).**

Looks up the tool by name in the worker's `ToolBox`; if missing, returns `ToolResult.failure(...)` and emits a `tool_call` trace with `status="missing_tool"`. Otherwise emits a `tool_call` trace with the signature/description and runs the tool. Any non-`ToolResult` return is wrapped as `ToolResult.ok(data=response, summary=...)`. Any exception is caught, formatted with traceback, and turned into `ToolResult.failure(...)` plus a `tool_call_exception` trace.

**`CommandCentre`.**

- `_get_agents_characteristics()` walks `Agent.agent_registry` excluding itself and produces the bulleted "AVAILABLE AGENTS" block embedded in the planner user prompt.
- `plan_next_step(conversation_context)` — formats `plan_next_step_system` and `plan_next_step_user`, calls `_ask_agent` with `return_json=True`, `validator=validate_planner_action`, `phase="planner"`.
- `synthesize_answer(conversation_context)` — formats the `synthesis_*` templates, calls `_ask_agent` *without* JSON mode and *without* a validator, returns the plain string. This is the only LLM call that returns natural language to the user.

### 4.5 `agents_training_facility/personalities.py`

[src/agentic_system/agents_training_facility/personalities.py](../src/agentic_system/agents_training_facility/personalities.py)

**Purpose.** Long system prompts and short descriptions for each agent.

**Why it exists.** Two separate strings per agent:

- `<name>_desc` — short, fed into the manager's "AVAILABLE AGENTS" list via the registry. The manager uses it to decide *whether* to delegate to this agent.
- `<name>_system` — long, used as the agent's actual system prompt. Encodes filesystem rules, tone, and behavior policy.

**The five entries.**

- `brain_desc` / `brain_system` — Bob the Manager. Friendly but rule-following: reuse facts already in execution history, restate constraints when delegating, never invent.
- `python_developer_desc` / `python_developer_system` — must use `.venv`, write to `coding_output/pythondeveloper_code/`, overwrite scripts on amend rather than littering, prefer UTF-8 output.
- `secretary_desc` / `secretary_system` — read only from `data/` and `coding_output/`, write only to `coding_output/`; if a path is provided, check that exact path before broadening the search.
- `data_manager_desc` / `data_manager_system` — encodes that the local vector DB currently contains *only* Nemotron 3 NVIDIA documents, so the manager should not over-trust it for unrelated queries.
- `api_desc` / `api_system` — be cautious with arguments, return high-quality links with descriptions.

**Defense in depth.** Each system prompt *describes* the rule (e.g. "Write only to `coding_output/`") and the runtime *enforces* the same rule in code via `path_policy.py`. Even if the LLM disobeys the prompt, the tool refuses.

### 4.6 `prompts/prompts.py`

[src/agentic_system/prompts/prompts.py](../src/agentic_system/prompts/prompts.py)

**Purpose.** The exact LLM prompt templates. Six of them, in three pairs.

**Pair 1 — worker decision (`agent_choose_tool_*`).**

The worker's system prompt embeds:

- `{agent_descriptions}` — the worker's personality block.
- `{tool_descriptions}` — the lines from `ToolBox.tools()` (one per tool: `name(signature): docstring`).

The required reply shape is one of:

```json
{"type":"tool","tool":"<tool_name>","args":{"arg_name":"value"}}
{"type":"done","request_results":"<concrete results that were requested from MANAGER>"}
```

The user prompt embeds `MANAGER INSTRUCTION` (`{manager_instruction}`) and `ASSIGNMENT HISTORY` (`{assignment_history}`). The system prompt is explicit that `done.request_results` is the *only* information the manager will see, so the worker must include the raw tool data.

**Pair 2 — manager decision (`plan_next_step_*`).**

Manager system prompt embeds `{agent_descriptions}` (the manager's personality). The reply shape is one of:

```json
{"type":"answer_user","answer":"..."}
{"type":"delegate","agent":"<actual_agent_name>","instruction":"..."}
{"type":"talk_with_user","question":"..."}
{"type":"finish","reason":"..."}
```

The decision procedure is explicitly numbered in the prompt itself — re-read CURRENT REQUEST, try to answer if simple, finish if enough evidence exists, otherwise delegate, otherwise talk_with_user. This is what makes the manager use `answer_user` for greetings instead of asking pointless clarifications.

The user prompt is `{conversation_context}` + an `AVAILABLE AGENTS:` block from `_get_agents_characteristics()`.

**Pair 3 — synthesis (`synthesis_*`).**

Used only when the manager returned `finish`. The system prompt instructs the manager to act as a "master analyst", to synthesize from EXECUTION_STEPS and clearly completed worker summaries, and to be honest about failures rather than inventing facts. The user prompt is just `{conversation_context}`.

**The contract between code and LLM lives here.** Every behavior promise ("manager never asks for clarification on a greeting", "worker returns raw tool data") is enforced by the wording of these templates plus the JSON validators in `contracts.py`.

### 4.7 `memory/conversation_history.py`

[src/agentic_system/memory/conversation_history.py](../src/agentic_system/memory/conversation_history.py)

**The manager's memory.** This file owns the structured world-model the manager plans against — the only thing it sees besides its system prompt and the `AVAILABLE AGENTS` block.

**Memory at a glance.** Before diving in, here is every memory surface in the runtime — only the first two are *core* (the manager/worker split); the other two are bookkeeping.

| Surface | Class | Scope | Lifetime | On disk? |
| --- | --- | --- | --- | --- |
| Manager's structured history | `ConversationHistory` | One session | Whole session | `memory/conversation_history.json` + `memory/conversation_raw_events.json` |
| Worker's assignment history | `Memory` | One delegation | One worker session | No — RAM only |
| Global token ledger | `Memory` (class attribute on `Agent`) | Process-wide | Accumulates across runs | `memory/execution_cost/token_usage.json` |
| UI trace | JSONL stream via `TraceSink` | One session | Whole session | `memory/ui_traces/<session_id>.jsonl` |

Manager memory and worker memory are **two different objects of two different classes**, not one filtered view. The rest of 4.7 covers the first row; [4.8](#48-memorymemory_managerpy) covers rows 2 and 3.

**State.**

```python
class ConversationHistory:
    SUMMARY_TRIGGER_REQUESTS = 7   # only knobs that change
    SUMMARY_WINDOW_REQUESTS  = 5   # compaction behaviour

    def __init__(self, normalized_path, raw_path, session_id):
        ...
        self.completed_requests = []   # list[dict]
        self.active_request    = None  # dict | None
        self.raw_events        = []    # flat append-only log
        self.history_summary   = ""    # rolling compaction text
        self.summarized_through_request_id = 0
        self._next_request_id  = 1
```

An "active request" is a dict:

```python
{
    "request_id": int,
    "question": str,
    "clarifications": [{"question": ..., "answer": ...}, ...],
    "steps": [event_dict, ...],   # filled by record_event
    "started_at": "YYYY-MM-DDTHH:MM:SS",
}
```

After completion it migrates to `completed_requests` as:

```python
{
    "request_id": int,
    "question": str,
    "summary": str,
    "final_answer": str,
    "started_at": str,
    "completed_at": str,
}
```

Note: the per-request `summary` is built **deterministically** by `_summarize_active_request` — the literal string `"User asked: 'X'. Final answer was provided."` No LLM is called.

**The visibility filter — what separates manager from worker memory.**

```python
_MANAGER_VISIBLE_EVENTS = frozenset({
    "user_request",
    "user_clarification",
    "planner_action",
    "worker_done",
    "worker_budget_exhausted",
    "routing_error",
    "final_answer",
    "runtime_stop",
})
```

This frozenset is the single source of truth for what the manager sees in its planner context. `worker_action`, `tool_call`, `tool_result`, `tool_call_exception` are all *recorded* into `ConversationHistory.raw_events` (so the UI can render them and the audit log is complete), but they are filtered out before the planner string is built.

Plain rule: **the manager sees its own decisions, user messages, worker handoffs, and runtime errors — never the worker's tool calls.** A successful delegation collapses into one `TOOL_CALL` record: the `worker_done` event. The worker's six tool steps are physically invisible to the planner.

**`_event_to_manager_records` — the projection layer.**

Each visible event becomes one or more role records:

- `user_request` → `{"USER": "..."}`.
- `user_clarification` → `{"SYSTEM": "clarification requested: ..."}` + `{"USER": "clarification answer: ..."}`.
- `planner_action` → `{"AI[MANAGER]": {"action": "...", "iteration": N, "agent": ..., "instruction": ..., ...}}`.
- `worker_done` → `{"TOOL_CALL": {"agent": ..., "instruction": ..., "result": ..., "raw_data": ...}}`.
- `worker_budget_exhausted` → `{"TOOL_CALL": {"agent": ..., "result": "worker budget exhausted"}}`.
- `routing_error` → `{"SYSTEM": "routing error: unknown agent X"}`.
- `final_answer` → `{"FINAL_ANSWER": ...}`.
- `runtime_stop` → `{"SYSTEM": "runtime stopped: ..."}`.

The framing is deliberate: from the planner's perspective, calling a worker looks identical to calling a tool. The manager treats workers as opaque black boxes that return one string per delegation.

**`render_planner_context(last_n=None)` — what the LLM actually sees.**

A single string with up to three sections, each omitted if empty:

```
SUMMARY:
<rolling summary of older completed requests>

RECENTLY COMPLETED REQUESTS:
[ {request_id, USER_REQUEST, SUMMARY, FINAL_ANSWER}, ... ]

CURRENT REQUEST:
{
  "request_id": N,
  "USER": "...",
  "CLARIFICATIONS": [...],
  "EXECUTION_STEPS": [ {"USER": ...}, {"AI[MANAGER]": {...}}, {"TOOL_CALL": {...}}, ... ]
}
```

The orchestrator always calls this with `last_n=15` (the `steps_to_track` constructor argument). That truncates `EXECUTION_STEPS` to the **last 15 raw events from the active request** *before* the visibility filter runs — so the planner sees, at most, the manager-visible projection of the most recent 15 events of the current request. Everything older within the active request still lives in `raw_events` and on disk.

**Rolling compaction — when, how, why deterministic.**

*When.* `_finalize_completed_request` runs after every `final_answer` (manager either `answer_user`-ed or `finish`-ed). It calls `_maybe_compact_completed_history`, which asks `next_history_summary_window()` whether enough requests have stacked up:

```python
if len(unsummarized_requests) < self.SUMMARY_TRIGGER_REQUESTS:   # < 7
    return []
return unsummarized_requests[: self.SUMMARY_WINDOW_REQUESTS]     # oldest 5
```

So nothing happens until at least **7** unsummarized completed requests exist. When the 7th finishes, the oldest **5** are returned.

*How.* The orchestrator's `_fallback_history_window_summary` concatenates the previous `history_summary` with one-line per-request synopses:

```
Request 1: user asked '...'; outcome: User asked: '...'. Final answer was provided.
Request 2: ...
...
```

The result becomes the new `history_summary`; `summarized_through_request_id` advances to the last summarised request's id. `RECENTLY COMPLETED REQUESTS` then drops those entries naturally because the list-builder filters by `request_id > summarized_through_request_id`.

*Why no LLM call.* Every other "summary" string in the project — the per-request summary, the worker's `request_results` — is also deterministic. Compaction is a **budget defence**, not a reasoning step. Calling the LLM here would (a) cost tokens to save tokens, (b) make context bounds non-deterministic between runs, and (c) introduce a new failure mode (compaction LLM call dying mid-finalize). The raw event log on disk still has everything if a human needs detail; the planner just gets a compact pointer.

**Every buffer number in one place.**

| Knob | Value | What it bounds |
| --- | --- | --- |
| `last_n` (`steps_to_track`) | 15 | Raw events from the **active** request that survive into the planner string |
| `SUMMARY_TRIGGER_REQUESTS` | 7 | Minimum unsummarized completed requests before compaction fires |
| `SUMMARY_WINDOW_REQUESTS` | 5 | Oldest requests folded into the summary each time compaction fires |
| `max_iterations` | 12 | Planner steps per request (a loop bound, not a memory bound) |
| `max_worker_steps` | 6 | Worker steps per delegation (a loop bound, not a memory bound) |

Only the first three are memory bounds. The first bounds prompt size **within** a request; the second two bound prompt size **across** requests.

**Worked example — walking through requests 1 → 13.**

Sketches of `render_planner_context()` shape at four cut-points; the active request shown only when one is mid-flight.

*After request 1 finishes.* Trigger is 7; compaction never considered.
```
RECENTLY COMPLETED REQUESTS:
[ {request_id: 1, USER_REQUEST: ..., SUMMARY: "User asked: ...", FINAL_ANSWER: ...} ]
```

*After request 6 finishes.* Still 6 < 7, no compaction.
```
RECENTLY COMPLETED REQUESTS:
[ req 1, req 2, req 3, req 4, req 5, req 6 ]
```

*After request 7 finishes — compaction fires for the first time.* Oldest 5 (req 1–5) are concatenated into `history_summary`; `summarized_through_request_id = 5`.
```
SUMMARY:
Request 1: user asked '...'; outcome: ...
Request 2: user asked '...'; outcome: ...
Request 3: user asked '...'; outcome: ...
Request 4: user asked '...'; outcome: ...
Request 5: user asked '...'; outcome: ...

RECENTLY COMPLETED REQUESTS:
[ req 6, req 7 ]
```

*Mid request 8, after 22 events have been recorded into the active request.* Same SUMMARY + RECENTLY COMPLETED. CURRENT REQUEST's `EXECUTION_STEPS` shows the **last 15** raw events from request 8 only, filtered through `_MANAGER_VISIBLE_EVENTS`:
```
CURRENT REQUEST:
{ request_id: 8,
  USER: "...",
  CLARIFICATIONS: [...],
  EXECUTION_STEPS: [ <last 15 raw events, visible only> ] }
```

*After request 13 finishes — compaction fires a second time.* Requests 6–12 = 7 unsummarized; oldest 5 (6–10) get appended onto the previous summary.
```
SUMMARY:
<previous summary covering req 1–5>
Request 6: ...
Request 7: ...
Request 8: ...
Request 9: ...
Request 10: ...

RECENTLY COMPLETED REQUESTS:
[ req 11, req 12, req 13 ]
```

The shape never blows up: `RECENTLY COMPLETED REQUESTS` is always between 0 and 11 entries (right before the next compaction). `SUMMARY` grows linearly with completed requests but stays a flat string.

**Persistence.** `save()` writes two JSON files atomically (overwrite, indent=4, UTF-8) after every `_record_step`:

- `memory/conversation_history.json` — `snapshot()` (current session id, summary, completed_requests, active_request).
- `memory/conversation_raw_events.json` — the raw event list as recorded.

Note that `memory.txt` (a human-readable mirror of `render_planner_context(last_n=15)`) is written by the *orchestrator*'s `_save_execution_history`, not by `ConversationHistory` itself. It exists for debugging only — nothing reads it back.

### 4.8 `memory/memory_manager.py`

[src/agentic_system/memory/memory_manager.py](../src/agentic_system/memory/memory_manager.py)

**The worker's notebook and the global token ledger.** A minimal list-backed memory with optional disk persistence. Used in **two completely different lifecycles** — and that asymmetry is the point.

**API.**

- `Memory(is_structured: bool = True, has_history: str = None)` — if `has_history` points to an existing `.json` or `.txt` file, it is read into `self.memory` on construction.
- `extend_memory(new_memory)` — append; rejects non-dict values when `is_structured=True`.
- `recall_raw(steps: int | None = None)` — returns `list(self.memory)` or the last `steps` entries.
- `save_history(file_path)` — writes JSON or newline-joined TXT.

**The two lifecycles, side by side.**

|  | Per-worker assignment history | Global token ledger |
| --- | --- | --- |
| Where it lives | Local variable inside `_run_worker_session` | Class attribute on `Agent` (`Agent.token_usage`) |
| Created | Once per delegation | Once at module import |
| Dies | When the worker returns `done` or budget-exhausts | Never — persists across sessions and runs |
| Records | `worker_action`, `tool_result`, `worker_done` events | One entry per LLM call: agent, model, status, prompt/completion tokens, raw response |
| Read by | Only the current worker, via `_assignment_history_text(...)` | The UI (reads `token_usage.json`) — never by an agent |
| On disk | No — RAM only | Yes — `memory/execution_cost/token_usage.json`, rewritten after every append |

**Usage 1 — per-worker assignment history (the worker's notebook).**

Inside `_run_worker_session`:

```python
assignment_history = Memory(is_structured=True)
```

The worker **always** starts a delegation amnesic. Before each worker turn, `_assignment_history_text(assignment_history)` renders the recorded events as a numbered text block — that string is what the worker sees as `ASSIGNMENT HISTORY:` in its user prompt.

Three event types land here:

- `worker_action` — the worker's own most recent decision (so it can see what it just chose).
- `tool_result` — the outcome the worker needs to plan its next step.
- `worker_done` — appended just before return; kept for symmetry, not strictly needed.

**Cross-worker amnesia.** Two consecutive delegations get **two separate** `Memory` instances — they are not connected. If request 8 delegates to `secretary` first and then to `pythondeveloper`, the second worker cannot see what the first one read. The manager must restate any relevant facts in the second `instruction` string. This is the design rule `brain_system` enforces: "When delegating, restate every constraint the worker would not otherwise know."

**Usage 2 — global token ledger.**

In `agents.py`:

```python
class Agent:
    agent_registry = {}
    token_usage = Memory(is_structured=True, has_history=TOKEN_USAGE_PATH)
```

Because Python evaluates class attributes once at import, **every Agent (manager + every worker) shares the same `Memory` instance**. The file at `memory/execution_cost/token_usage.json` is loaded on first import, so the ledger accumulates across runtime invocations.

`_record_model_response` appends one entry per successful LLM call and re-saves the whole list to disk:

```python
self.token_usage.extend_memory(model_data)
self.token_usage.save_history(TOKEN_USAGE_PATH)
```

The UI reads the file directly (see `ui/app.py:260`); no agent reads it back.

**Worked example — a 3-step worker session.**

The manager has just delegated to `pythondeveloper` with the instruction *"Read data/sales.csv and report the mean of the 'amount' column."* A fresh `Memory()` is created. The token ledger keeps growing throughout.

*Step 1.* Worker emits `{"type":"tool","tool":"read_file_content","args":{"path":"data/sales.csv"}}`. Two records get appended to `assignment_history`: a `worker_action` and the subsequent `tool_result`. The ledger gets one entry (the LLM call that produced the action). The text fed into step 2's prompt:

```
1. Worker step 1: chose tool.
2. Tool read_file_content -> success: Read 1024 bytes from data/sales.csv | Data: ...
```

(Note: `_assignment_history_text` formats the action line as `chose tool` — the tool *name* lives on the next line, in the `tool_result` rendering.)

*Step 2.* Worker emits `{"type":"tool","tool":"run_python_script", ...}`. Two more records appended; ledger gets one more entry. Step 3 now sees:

```
1. Worker step 1: chose tool.
2. Tool read_file_content -> success: Read 1024 bytes from data/sales.csv | Data: ...
3. Worker step 2: chose tool.
4. Tool run_python_script -> success: ... | Data: {"mean": 12.4}
```

*Step 3.* Worker emits `{"type":"done","request_results":"Sales 'amount' mean = 12.4"}`. A `worker_done` record is appended to `assignment_history` (for symmetry) **and** a `worker_done` event is recorded in the manager-side `ConversationHistory`. **This `worker_done` event is the only crossing point between worker memory and manager memory** — the only way information escapes the worker's scope. `_run_worker_session` returns; the local `assignment_history` is dropped on the next garbage collection. The token ledger keeps the three LLM-call entries forever.

**Why a second memory class?** Two reasons.

1. **Physical separation beats filter-based separation.** The worker is handed a different *object*, not a filtered view of the global one. If a bug leaks state into `assignment_history`, that leak cannot reach the manager's planner context — they live in different scopes. A visibility filter has to be correct on every event type; physical separation is correct by construction.
2. **Same shape, different responsibilities.** The token ledger reuses `Memory` because its semantics happen to match: append-only list of dicts, optional disk persistence. Two responsibilities, one tiny class.

### 4.9 `toolbox/toolbox.py`

[src/agentic_system/toolbox/toolbox.py](../src/agentic_system/toolbox/toolbox.py)

**Purpose.** Turn Python callables into LLM-discoverable tools.

**API.**

- `ToolSpec(name, func, signature, description)` — frozen dataclass; `prompt_description` returns the prompt-injected line `name(signature): description`.
- `ToolBox.store(functions_list)` — bulk-register from a `{name: callable}` dict; pulls the cleaned-up `__doc__` and inspects `signature(func)`.
- `ToolBox.tools()` — newline-joined list of `prompt_description` strings, ready to be `.format(...)`-ed into the worker system prompt.
- `ToolBox.get(name)` — returns the `ToolSpec` for a name or `None`.

**Why it exists.** Tools are advertised to the LLM with their actual signature and docstring. There is no separate JSON schema file — the truth is the Python source. Add a tool function with a useful docstring and it shows up in the system prompt automatically.

### 4.10 `tools/path_policy.py`

[src/agentic_system/tools/path_policy.py](../src/agentic_system/tools/path_policy.py)

**Purpose.** The single source of truth for filesystem access. Every tool that touches disk consults this module.

**Roots.**

```python
AGENTIC_ROOT              = .../src/agentic_system/
PROJECT_ROOT              = .../basci_agents_explanation-main/
DATA_ROOT                 = AGENTIC_ROOT / "data"
CODING_OUTPUT_ROOT        = AGENTIC_ROOT / "coding_output"
PYTHONDEVELOPER_CODE_ROOT = CODING_OUTPUT_ROOT / "pythondeveloper_code"
READ_ROOTS                = (DATA_ROOT, CODING_OUTPUT_ROOT)
WRITE_ROOT                = CODING_OUTPUT_ROOT
VENV_ROOT                 = PROJECT_ROOT / ".venv"
```

**Policy summary.**

- Reads: must resolve under `data/` or `coding_output/`.
- Writes: must resolve under `coding_output/`.
- Python script execution: must resolve under `coding_output/pythondeveloper_code/`.
- Python interpreter for `run_python_script`: must be the `.venv` interpreter.

**Functions.**

- `resolve_read_path(value, default_to_data=True)` — given a bare filename, prefers `data/` if the file exists there, otherwise `coding_output/`, otherwise defaults to `data/`. Given a known top-level folder name (`data`/`coding_output`) it joins under `AGENTIC_ROOT`. Absolute paths pass through.
- `resolve_write_path(value)` — same idea but biased to `coding_output/`.
- `resolve_pythondeveloper_code_path(value)` — same idea but under `coding_output/pythondeveloper_code/`.
- `is_allowed_read_path(path)`, `is_allowed_write_path(path)`, `is_allowed_pythondeveloper_code_path(path)` — boolean guards used in tool bodies.
- `ensure_runtime_directories()` — `mkdir -p` for the writable directories.
- `validate_project_venv()` — checks for `.venv`, `pyvenv.cfg`, and a usable Python executable.
- `resolve_venv_python()` — picks Windows (`.venv\Scripts\python.exe`) or POSIX (`.venv/bin/python`).
- `is_running_from_project_venv()` — verifies `sys.executable` is inside `VENV_ROOT`.
- `validate_runtime_interpreter()` — combined check used at startup.

**Why this matters.** The runtime is *not* a sandbox in the OS sense. There is no chroot, no Docker. But every tool that writes/reads disk passes through these helpers and returns `ToolResult.failure(READ_ACCESS_DENIED | WRITE_ACCESS_DENIED | EXECUTE_ACCESS_DENIED)` when the resolved path leaves the allowed root. That is the *only* enforcement layer, and it lives here.

### 4.11 `tools/file_handler.py` — Secretary

[src/agentic_system/tools/file_handler.py](../src/agentic_system/tools/file_handler.py)

The Secretary's toolbox. All tools return `ToolResult` and pre-check paths against the policy.

| Tool | Purpose |
| --- | --- |
| `check_if_file_exists(filename)` | Search `data/` and `coding_output/` for a file. If only a bare name is given, walks both roots recursively. Returns the resolved absolute path. |
| `search_files(pattern, root=None)` | `rglob` matching `pattern` (e.g. `*.csv`). When `root` is omitted, scans both read roots; otherwise scans only the resolved root. |
| `text_writer(message, filename="results.txt")` | Append-or-create timestamped lines inside `coding_output/`. Mode is `"a"` if file exists else `"w"`. |
| `read_text(filename="coding_output/results.txt")` | Read a text file's full contents. |
| `csv_reader(filepath="data.csv", **kwargs)` | `pd.read_csv` with arbitrary kwargs forwarded. Returns the DataFrame. (Note: `make_json_safe` later converts it to a preview before it is written to history.) |
| `read_json(filename="data.json")` | `json.load`. |

The exported registry:

```python
TOOLS = {
    "check_if_file_exists": check_if_file_exists,
    "search_files":         search_files,
    "text_writer":          text_writer,
    "read_text":            read_text,
    "csv_reader":           csv_reader,
    "read_json":            read_json,
}
```

This is exactly what `Agent.__init__` reads when the secretary is constructed with `module_list=["file_handler"]`.

### 4.12 `tools/programer.py` — Python Developer

[src/agentic_system/tools/programer.py](../src/agentic_system/tools/programer.py)

Three tools, all funneled through path policy and `.venv` validation.

- `write_python_code(code, filename="generated_script.py")` — `code.encode().decode("unicode_escape")` to honor `\n` literals coming from the LLM, then writes the file under `coding_output/pythondeveloper_code/`. Refuses paths outside that folder.
- `run_python_script(filename)` — verifies the script lives inside `coding_output/pythondeveloper_code/`, verifies `.venv` is valid, and runs `subprocess.run([venv_python, script_path])` with `cwd=AGENTIC_ROOT`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`. Captures stdout/stderr/return code. On `CalledProcessError` returns `ToolResult.failure(...)` with the captured output so the worker can read the actual error.
- `list_installed_packages(refresh=False)` — calls `pip list --format=json` inside `.venv`, caches the result in `memory/venv_packages_cache.json`. With `refresh=False` and an existing cache, returns cached data instantly. Useful when the developer agent wants to know "do I have pandas?" before writing import lines.

```python
TOOLS = {
    "write_python_code":      write_python_code,
    "run_python_script":      run_python_script,
    "list_installed_packages": list_installed_packages,
}
```

### 4.13 `tools/data_manager.py` — Data Manager

[src/agentic_system/tools/data_manager.py](../src/agentic_system/tools/data_manager.py)

The most complex tool module. It owns the local document vector DB and one news API.

**Vector DB layout.**

- `data/documents/*.{pdf,txt,md}` — source files.
- `coding_output/vector_db/documents.index` — FAISS `IndexFlatIP` (inner product == cosine similarity after L2 normalization).
- `coding_output/vector_db/documents_metadata.json` — `{embedding_model, documents_dir, chunks: [{source, chunk_id, text}, ...]}`.

**Embedding provider switching.**

`_model_provider()` reads `MODEL_PROVIDER`. Then:

- Azure → POST to `{endpoint}/openai/deployments/{deployment}/embeddings` (or the new `/openai/v1/embeddings` shape) with `api-key` header.
- OpenAI → POST to `{OPENAI_BASE_URL or default}/embeddings` with `Authorization: Bearer ...`.
- Ollama → POST to `{OLLAMA_BASE_URL}/api/embed` (or fallback to `/api/embeddings` one-at-a-time).

**Build flow (`build_documents_vector_db`).**

1. Read all supported files from `data/documents/` (sorted, lowercased extension match).
2. Chunk: collapse whitespace, slide a `chunk_size=1100` window with `chunk_overlap=200`.
3. Embed in batches of 16.
4. `faiss.normalize_L2(matrix)` + `IndexFlatIP(d)` + `index.add(matrix)`.
5. `faiss.write_index(...)` and write the metadata JSON. Returns a `ToolResult.ok` with documents count, chunks count, and the on-disk paths.

**Startup hook (`ensure_documents_vector_db`).**

If both `documents.index` and `documents_metadata.json` exist, returns `{"status": "existing"}` immediately. Otherwise it builds. This is what `build_default_runtime` calls before constructing agents.

**Query flow (`query_documents_vector_db`).**

1. If index files are missing and `rebuild_if_missing=True`, build first.
2. Load index + metadata, embed the query.
3. **Compatibility check**: if the stored `embedding_model` differs from the current one, or the query vector dimension differs from `index.d`, rebuild the index. This is the "user switched provider" safety net.
4. `index.search(query_matrix, k=top_k)` and pair the indices back to chunks. Returns `{query, top_k, embedding_model, matches: [{source, chunk_id, score, text}, ...]}`.

**News (`check_news`).**

`https://newsdata.io/api/1/latest` with `q`, `language`, `size`. Normalizes results to `[{title, url, description, published_at, source}]` capped at 10. Requires `NEWSDATA_API_KEY`.

```python
TOOLS = {
    "query_documents_vector_db": query_documents_vector_db,
    "check_news":                check_news,
}
```

### 4.14 `tools/apis.py` — API agent

[src/agentic_system/tools/apis.py](../src/agentic_system/tools/apis.py)

Three external HTTP integrations:

- `address_to_geolocation(address_details)` — `http://api.positionstack.com/v1/forward` with `POSITIONSTACK_API_KEY`. Returns `{latitude, longitude}`.
- `get_weather_forecast(lat, lon)` — `https://api.open-meteo.com/v1/forecast` with a fixed list of "current" fields (temperature, humidity, apparent temp, is_day, precipitation, rain, cloud cover, pressure, wind speed/direction/gusts) plus `timezone=Europe/Berlin`. The result interleaves each metric with its descriptive `_info` sibling (e.g. `temperature_2m`/`temperature_2m_info`), so the LLM can read units inline.
- `search_internet(query, max_results=3, search_depth="advanced", include_answer=True)` — Tavily POST `https://api.tavily.com/search`. Returns `{query, answer, results: [{title, url, description}]}`.

```python
TOOLS = {
    "address_to_geolocation": address_to_geolocation,
    "get_weather_forecast":   get_weather_forecast,
    "search_internet":        search_internet,
}
```

### 4.15 `ui/app.py` — Gradio app

[src/agentic_system/ui/app.py](../src/agentic_system/ui/app.py)

**Purpose.** Optional Gradio frontend that displays a live trace of an active session and lets the user browse archived sessions.

**Layout.** A two-column Blocks app:

- Left panel — Status pill, token totals, Chatbot, message textbox, Send / New Session / Delete-All-History buttons.
- Right panel — Saved sessions dropdown + four tabs: Step Trace, Execution Graph, Console, Raw Session JSON.

**State machine.**

A `gr.State` dict tracks `{mode, controller_id, session_id, selected_session_id}` where `mode ∈ {"empty", "live", "archived"}`. The helpers `acquire_live_session` and `resolve_view_state` decide:

- whether to start a new live session for the next message,
- which placeholder text to show in the textbox,
- whether Send/New Session should be enabled,
- whether the session dropdown should be interactive,
- and which trace events to render (live controller events or archived JSONL).

**Refresh loop.** A `gr.Timer(value=0.35)` fires every 350 ms; on each tick it calls `refresh_outputs` which reads the controller's events snapshot and re-renders all panels. This is how the user sees live updates while the orchestrator thread runs.

**Two-step delete.** The Delete All History button is `armed=False` initially. Click 1 sets `armed=True`, relabels the button "Click again to confirm DELETE ALL", and starts a 5-second `delete_disarm_timer` that returns it to idle. Click 2 (while armed) actually deletes `memory/ui_traces/*.jsonl`, `conversation_history.json`, `conversation_raw_events.json`, and `token_usage.json`.

**Entry point.** `python -m ui.app` calls `main()` → `build_app().launch()`.

### 4.16 `ui/controller.py` — SessionController

[src/agentic_system/ui/controller.py](../src/agentic_system/ui/controller.py)

**Purpose.** Run the orchestrator in a background thread and bridge its `input()`/`print()` calls to the Gradio UI through two queues.

**Class fields.**

- `controller_id` (uuid4 hex), `session_id`, `status` ∈ `{"empty", "starting", "running", "awaiting_user_input", "completed_request", "ended", "error"}`.
- `pending_input_kind` ∈ `{"clarification", "follow_up", "input"}` and `pending_prompt`.
- `trace_events: list[dict]` — buffer of every event the trace sink emits.
- `_event_queue: Queue` and `_input_queue: Queue`.
- `_runtime_thread: Thread`.
- `trace_sink: SessionTraceSink` constructed with `listener=self._on_trace_event` so every emit pushes into both the local buffer and the event queue.

**Methods.**

- `submit(message)` — if no thread is running yet, calls `_start_runtime(message)`. Otherwise, this is a reply to a pending `input()` call: put the message on `_input_queue` and signal a state change.
- `_start_runtime(initial_request)` — calls `build_default_runtime(input_func=self._blocking_input, output_func=self._capture_output, sleep_func=lambda _: None, trace_sink=self.trace_sink)` and spawns a daemon thread running `runtime.run(initial_request=...)`.
- `_blocking_input(prompt)` — classifies the prompt (`Manager needs more information.` → `clarification`; `Send the next request:` or `Your request has been finished.` → `follow_up`; else `input`), sets `pending_input_kind`/`pending_prompt`, signals state change, then blocks on `_input_queue.get()`. When the UI calls `submit`, the value flows back here and the orchestrator unblocks.
- `_capture_output(_message)` — no-op. The UI does not need console output because it reads the trace sink instead.
- `_on_trace_event(event)` — listener registered with the trace sink; appends to `trace_events`, syncs `session_id`, and updates `status` based on event type (`final_answer`, `session_end`, `runtime_error`, etc.).
- `wait_for_update(timeout=0.15)` — drained by Gradio's `handle_send` to yield UI refreshes only when something actually changed.
- `close()` — best-effort termination: if the thread is waiting on input, sends `"q"`, joins for 3 s.

The module also holds a module-level `_ACTIVE_CONTROLLERS` dict keyed by `controller_id` (`create_controller` / `get_controller` / `remove_controller`).

### 4.17 `ui/formatters.py` and `ui/archive.py`

[src/agentic_system/ui/formatters.py](../src/agentic_system/ui/formatters.py)

**Purpose.** Pure functions that turn a list of trace events into HTML.

**Outputs.**

- `chat_messages_from_events(events)` — replays user_request/user_clarification/user_input_requested(`clarification`)/final_answer/runtime_stop into the Gradio chatbot's `{"role", "content"}` format.
- `token_html(events)` — sums per-agent `input_tokens` and `output_tokens` from `model_call` events. Renders the totals + per-agent chips at the top of the left panel.
- `status_html(events, status, session_id, pending_input_kind, archived)` — status pill, session id, "current focus" agent/phase derived from the latest event, and a hint string.
- `step_trace_html(events)` — the long, nested timeline. Groups events into `request_groups` (split on each `user_request`), and renders each event into a `<details>`-collapsible card with metadata grid, prompt block, output, raw response, errors, etc. Hides `console_output`, `session_start`, `planner_iteration_start`, `delegation_start`, `synthesis_start` (those are internal markers).
- `execution_graph_html(events)` — a compact sequential graph using `_graph_node_from_event` (one or two nodes per event). User events go on the user lane, manager events on the manager lane, workers on the worker lane.
- `console_html(events)` — shows just `console_output` events (`_emit` calls from the orchestrator).
- `raw_session_json(events)` — pretty-printed JSON dump.

[src/agentic_system/ui/archive.py](../src/agentic_system/ui/archive.py)

**Purpose.** Read-only access to past JSONL traces.

- `load_session(session_id, trace_dir=...)` → `list[dict]` of events.
- `list_sessions(trace_dir=..., limit=30)` — sorts `*.jsonl` files by mtime descending, derives a title from the first `session_start` or `user_request` event, returns `[{session_id, label, title, path, started_at, updated_at}]`.
- `dropdown_choices(...)` — flattens to `(label, session_id)` tuples for Gradio's Dropdown.
- `purge_all_traces(trace_dir)` — `unlink` every `*.jsonl` and count successes.

### 4.18 `ui/styles.py`

The CSS and JS injected into Gradio's `<head>`. Purely cosmetic — colors, spacing, dark theme; the cards in `step_trace_html` are styled via `trace-card`/`actor-manager`/`actor-worker`/`actor-tool`/`actor-error` classes defined here. Not load-bearing; if you understand `formatters.py` you understand the structure.

---

## 5. Who sees what — the visibility model

The runtime has *four* nested visibility scopes.

```
  ┌──────────────────────────────────────────────────────────────────┐
  │ USER                                                             │
  │   sees: console output (_emit) or the Gradio panels              │
  │                                                                  │
  │   ┌──────────────────────────────────────────────────────────┐   │
  │   │ MANAGER (CommandCentre)                                  │   │
  │   │   sees: render_planner_context() — three sections:       │   │
  │   │     SUMMARY                                              │   │
  │   │     RECENTLY COMPLETED REQUESTS                          │   │
  │   │     CURRENT REQUEST.EXECUTION_STEPS  (filtered through   │   │
  │   │       _MANAGER_VISIBLE_EVENTS — NO tool_call/tool_result)│   │
  │   │   plus AVAILABLE AGENTS block from agent_registry         │   │
  │   │                                                          │   │
  │   │   ┌──────────────────────────────────────────────────┐   │   │
  │   │   │ WORKER (Agent)                                   │   │   │
  │   │   │   sees: its own system prompt (personality +     │   │   │
  │   │   │         tool list) +                             │   │   │
  │   │   │         MANAGER INSTRUCTION +                    │   │   │
  │   │   │         ASSIGNMENT HISTORY (this session only)   │   │   │
  │   │   │                                                  │   │   │
  │   │   │   ┌──────────────────────────────────────────┐   │   │   │
  │   │   │   │ TOOL (Python function)                   │   │   │   │
  │   │   │   │   sees: only the args dict it was called │   │   │   │
  │   │   │   │   with. Returns ToolResult.              │   │   │   │
  │   │   │   └──────────────────────────────────────────┘   │   │   │
  │   │   └──────────────────────────────────────────────────┘   │   │
  │   └──────────────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────────────┘
```

Tabular form:

| Actor | Sees | Does not see |
| --- | --- | --- |
| User | `_emit` console output (CLI) or all UI panels (UI). | Internal LLM prompts unless they open the Step Trace tab. |
| Manager | `SUMMARY` + `RECENTLY COMPLETED REQUESTS` + `CURRENT REQUEST.EXECUTION_STEPS` projected through `_MANAGER_VISIBLE_EVENTS`. Plus the `AVAILABLE AGENTS` block from `agent_registry`. | `worker_action`, `tool_call`, `tool_result`, `tool_call_exception`. The only window into a worker is `worker_done.request_results` (and `worker_budget_exhausted` when things go sideways). |
| Worker | Its own personality+tools (system) + the manager's `instruction` + its own assignment history numbered list. | Anything from other workers, the global `ConversationHistory`, the manager's reasoning, the user's clarifications. |
| Tool | The `args` dict the worker chose. | Anything else. |

Cross-worker amnesia is a feature: when the manager delegates to a second worker for a task that needs facts the first worker discovered, the manager must re-state those facts in the new `instruction` (that's what `brain_system` insists on: "When delegating, restate every constraint the worker would not otherwise know").

---

## 6. How history is built — the event lifecycle

Every interesting moment in the runtime fires one event. Each event lands in:

- the structured `ConversationHistory` (which feeds the manager),
- the `raw_events` list (the flat, complete audit log),
- the per-worker `assignment_history` (only worker-scoped events; only seen by the current worker),
- the JSONL trace file via `trace_sink.emit` (which feeds the UI).

Event-by-event:

### `user_request`
- **Triggered by**: `AgentOrchestrator.run` for each iteration of the outer loop.
- **Side effects**: `ConversationHistory.start_request(...)` mints a new `active_request`; `_record_step("user_request", request=...)` writes it to history *and* emits the trace.
- **Visibility**: Manager (`USER` role record).

### `user_clarification`
- **Triggered by**: `_talk_with_user(question)` after the manager returns `talk_with_user`.
- **Side effects**: `ConversationHistory.add_clarification(question, answer)` plus `_record_step("user_clarification", question=..., answer=...)`.
- **Visibility**: Manager (`SYSTEM` then `USER` role records).
- **Trace pairing**: A `user_input_requested` trace event is emitted *before* this one, carrying the question and prompt — the UI uses that to show the manager-asks-user bubble.

### `planner_action`
- **Triggered by**: each iteration of the inner planner loop.
- **Side effects**: `_record_step("planner_action", iteration=N, action=action)`.
- **Visibility**: Manager (`AI[MANAGER]` role record).

### `worker_action`
- **Triggered by**: every step inside `_run_worker_session`, before the tool runs.
- **Side effects**: extends the worker's local `assignment_history` *and* records the event in the global `ConversationHistory`.
- **Visibility**: Worker (via assignment history text). Not visible to the manager.

### `tool_call` (trace-only)
- **Triggered by**: `Agent.execute_tool` just before calling the function. Includes the tool's `description` and `signature`.
- **Side effects**: Trace-sink emit only. Not stored in `ConversationHistory` (the meaningful record is the subsequent `tool_result`).

### `tool_result`
- **Triggered by**: `_run_worker_session` after `execute_tool` returns.
- **Side effects**: assignment_history append + `_record_step("tool_result", agent=..., tool=..., args=..., success=..., summary=..., error=..., data=make_json_safe(data))`.
- **Visibility**: Worker. The DataFrame previews and other non-trivial structures are flattened through `make_json_safe`.

### `tool_call_exception` (trace-only)
- **Triggered by**: `Agent.execute_tool` exception handler.
- **Side effects**: Trace-sink only. The matching `tool_result` (built from `ToolResult.failure(...)`) carries the error into `assignment_history` and `ConversationHistory`.

### `worker_done`
- **Triggered by**: worker returns `{"type":"done", ...}`.
- **Side effects**: `assignment_history.extend({"event_type":"worker_done", "request_results":..., "request_raw_data":...})` and `_record_step("worker_done", agent=..., instruction=..., steps_taken=..., request_results=..., request_raw_data=..., assignment_history=assignment_history.recall_raw())`.
- **Visibility**: Manager (as a `TOOL_CALL` role record with `agent`, `instruction`, `result`, and optionally `raw_data`). **This is the one moment a worker speaks to the manager.**

### `worker_budget_exhausted`
- **Triggered by**: the worker loop finished `max_worker_steps` iterations without returning `done`.
- **Side effects**: `_record_step("worker_budget_exhausted", agent=..., instruction=..., max_worker_steps=..., assignment_history=...)`.
- **Visibility**: Manager.

### `routing_error`
- **Triggered by**: manager `delegate.agent` is not in `agents_dict`.
- **Side effects**: `_record_step("routing_error", agent=name)`.
- **Visibility**: Manager (as a `SYSTEM` record).

### `final_answer`
- **Triggered by**: either `answer_user` (manager wrote the answer directly) or `_run_synthesis` (manager called `finish` and then synthesized).
- **Side effects**: `_record_step("final_answer", answer=...)`, then `_finalize_completed_request(final_answer)`. The active request migrates into `completed_requests` with its `summary`, and `_maybe_compact_completed_history` runs.
- **Visibility**: Manager (as `FINAL_ANSWER` role record), user (console emit).

### `runtime_stop`
- **Triggered by**: inner loop exhausted `max_iterations` without finishing.
- **Side effects**: `_record_step("runtime_stop", reason=...)`. The current `last_answer` (which may be `None`) is returned from `run()`.
- **Visibility**: Manager.

### `model_call` (trace-only)
- **Triggered by**: every successful `_ask_agent` call.
- **Side effects**: trace-sink emit with `prompt={"system","user"}`, `response`, `raw_response`, `token_usage`, plus `model_provider` and `model` in the payload.

### `console_output` (trace-only)
- **Triggered by**: every `AgentOrchestrator._emit` call.
- **Side effects**: trace-sink emit; the UI's Console tab renders these.

### `session_start` / `session_end` (trace-only)
- **Triggered by**: `run()` startup and `run()` exit (either `runtime_stop` or `conversation_end`).

### Files updated on every step

After **every** `_record_step` the orchestrator calls `self._save_conversation_history()` which writes:

- `memory/conversation_history.json` (normalized snapshot).
- `memory/conversation_raw_events.json` (raw event list).

After every worker step *and* after request completion, `_save_execution_history()` writes `memory.txt` — the human-readable planner context. The token ledger is appended *inside* `_record_model_response`. Trace events are appended inside `SessionTraceSink.emit` to `memory/ui_traces/<session_id>.jsonl`.

---

## 7. Runtime safety rails

These are the layers that keep the runtime predictable.

### 7.1 Filesystem sandbox

Implemented in [tools/path_policy.py](../src/agentic_system/tools/path_policy.py); enforced inside every tool function. Three rings:

- Read: `data/` and `coding_output/` only.
- Write: `coding_output/` only.
- Python script execute: `coding_output/pythondeveloper_code/` only.

If a tool gets a path outside its ring, it returns `ToolResult.failure(READ_ACCESS_DENIED | WRITE_ACCESS_DENIED | EXECUTE_ACCESS_DENIED)`. The worker sees the failure in the next iteration and can re-plan.

### 7.2 `.venv` enforcement

`validate_runtime_interpreter()` is the gate: if `.venv` is missing or the current `sys.executable` is not inside it, it returns `(False, message)`. `run_python_script` rejects execution unless `validate_project_venv()` passes. Together this guarantees the runtime always runs on the project-pinned Python, regardless of how the user launched it.

### 7.3 JSON validators

`validate_planner_action` and `validate_worker_action` raise `ValueError` if the LLM produces anything off-contract. `_ask_agent` catches that, records `invalid_json_response` in both the token ledger and the trace, then re-raises so the caller sees the failure. The orchestrator does not catch this — it lets the LLM-level failure bubble up to the UI/CLI rather than continuing in a degraded state.

### 7.4 Iteration budgets

- `max_iterations=12` planner steps per request.
- `max_worker_steps=6` tool/think steps per delegation.

Both can be overridden when constructing `AgentOrchestrator`. The defaults are deliberately small — they exist to bound unbounded LLM-driven loops, not to enable long tool chains. If a worker keeps hitting the budget you should re-shape the delegation instruction instead of bumping the cap.

### 7.5 Two-step destructive UI actions

In the Gradio UI, the Delete All History button requires two consecutive clicks within 5 seconds and is the *only* destructive UI action. The `delete_disarm_timer` re-disarms it automatically.

---

## 8. Configuration surface (`.env`)

The runtime reads everything from environment variables (loaded via `python-dotenv`). Required values depend on `MODEL_PROVIDER`:

### Always required

- `MODEL_PROVIDER` ∈ `{azure, openai, ollama}`.

### Azure OpenAI

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT` (e.g. `https://<resource>.openai.azure.com` or `…/openai/v1`)
- `AZURE_OPENAI_DEPLOYMENT` (chat completion deployment name — used as the `model` in `chat.completions.create`)
- `AZURE_OPENAI_API_VERSION` (not required when the endpoint ends in `/openai/v1`)
- `AZURE_OPENAI_EMBEDDING` (embedding deployment name)

### OpenAI

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (chat model id)
- `OPENAI_EMBEDDING` (embedding model id)
- `OPENAI_BASE_URL` (optional — defaults to `https://api.openai.com/v1`)

### Ollama

- `OLLAMA_BASE_URL` (e.g. `http://localhost:11434/v1`)
- `OLLAMA_API_KEY`
- `OLLAMA_MODEL`
- `OLLAMA_EMBEDDINGS` (defaults to `nomic-embed-text:latest`)

### Tool-specific keys

- `POSITIONSTACK_API_KEY` — for `address_to_geolocation` (positionstack.com).
- `TAVILY_API_KEY` — for `search_internet`.
- `NEWSDATA_API_KEY` — for `check_news`.

Missing keys produce `ToolResult.failure(...)` with a precise message, not a crash. The agent reads the message and decides what to do.

---

## 9. Cheat sheet — short talking points

Use these one-liners when explaining the project to someone who has not read this document:

1. **One brain, four hands.** A single LLM agent ("the manager") plans every step; four worker agents (`pythondeveloper`, `secretary`, `data_manager`, `api`) carry out the work.
2. **The manager never touches a tool.** It only emits one of four JSON actions: answer, delegate, ask user, or finish.
3. **The workers never talk to the user.** Workers serve the manager via two JSON actions: `tool` or `done`.
4. **`ToolResult` is the only contract that crosses a tool boundary.** `{success, data, summary, error}` — that's it.
5. **Workers are amnesic.** Each delegation starts with an empty assignment history. If the manager wants the worker to know a previous fact, it has to be in the `instruction` string.
6. **The manager sees worker results, not worker steps.** Tool calls and tool results are recorded in the global history but filtered out of the manager's planner context.
7. **History is built event by event.** Every interesting moment fires an event; events land in `ConversationHistory`, the assignment history (worker-scoped), and a JSONL trace file (UI-scoped).
8. **Compaction is deterministic.** When seven completed requests stack up, the oldest five get summarized by string concatenation (no extra LLM call).
9. **The sandbox is a single Python module.** `path_policy.py` decides what can be read, written, and executed; every tool consults it.
10. **The UI is optional and decoupled.** Gradio plugs into the runtime via a `TraceSink`; the CLI works identically with a `NullTraceSink`.

If you can recite this list, you can explain the whole codebase.
