# Code Guide

This guide explains the current codebase from the ground up.

It is written for learning, not just for reference. The goal is that after reading it, you should understand:

- what the app is trying to do
- which files matter most
- how control flows through the system
- how agents, prompts, tools, and memory interact
- how history is stored
- what actually happens during a real request

---

# 1. What This Project Is

At a high level, this repository is a **manager-led multi-agent assistant**.

The system accepts a user request in the terminal, then tries to solve it by:

1. letting a **manager model** decide the next task
2. delegating that task to a **specialized worker agent**
3. letting that worker use one or more tools
4. recording the results into structured history
5. returning control to the manager
6. repeating until the manager has enough information to answer

The design tries to separate responsibilities:

- the **manager** decides *what should happen next*
- the **worker** decides *which tool to use to make progress*
- the **tool** performs the real action
- the **memory/history layer** keeps track of what happened

This means the system is not a single giant prompt. It is a loop with roles.

---

# 2. The Main Execution Idea

The best mental model for the current version is:

```text
User request
-> Manager plans next delegated task
-> Worker gets a bounded internal session
-> Worker may take up to N tool steps (default 4)
-> Worker returns done / needs_user_input
-> Manager replans
-> Manager eventually finishes and synthesizes final answer
-> Conversation stays open for next user request
```

That last part is important:

The app no longer exits after the first finished answer. It stays open until the user types one of the exit words such as:

- `q`
- `quit`
- `exit`
- `bye`
- `no`
- `thanks`
- `thank you`

So this is now a **multi-turn terminal conversation** rather than a one-question process.

---

# 3. The Most Important Files

If you want to understand the project quickly, read these in this order:

1. `main.py`
2. `runtime/orchestrator.py`
3. `agents_training_facility/agents.py`
4. `prompts/prompts.py`
5. `runtime/contracts.py`
6. `memory/memory_manager.py`
7. `toolbox/toolbox.py`
8. `tools/file_handler.py`
9. `tools/apis.py`
10. `tools/programer.py`

Why this order?

- `main.py` tells you where execution starts.
- `runtime/orchestrator.py` is the real control loop.
- `agents.py` explains how agents and models behave.
- `prompts.py` explains what the models are instructed to do.
- `contracts.py` explains the JSON structures and tool result shapes.
- `memory_manager.py` explains how state is stored and rendered.
- `toolbox.py` explains how tools are exposed to the model.
- the `tools/` files explain the real actions your system can take.

---

# 4. Step Zero: Starting the Program

Execution begins in `main.py`.

## What `main.py` does

`main.py` is intentionally minimal.

It does four things:

1. imports `build_default_runtime`
2. optionally loads environment variables from `.env`
3. tries to configure stdout/stderr to UTF-8
4. builds the runtime and calls `runtime.run()`

That means `main.py` is not where the business logic lives.

It is just the entrypoint that boots the application.

## Why keeping `main.py` thin is useful

This is good structure because:

- terminal bootstrapping stays separate from orchestration logic
- tests can target the runtime directly
- future entrypoints could reuse the same runtime

For example, if later you wanted:

- a web UI
- a notebook wrapper
- an API endpoint

you could reuse the same runtime/orchestrator idea without putting that logic in `main.py`.

---

# 5. Building the Runtime

The runtime is created in `runtime/orchestrator.py` inside `build_default_runtime()`.

This function creates:

- one **manager**
- four **worker agents**

Specifically:

- `manager`
- `pythondeveloper`
- `secretary`
- `intern`
- `api`

These are put into a dictionary like:

```python
agents_dict = {
    manager.name: manager,
    python_developer.name: python_developer,
    secretary.name: secretary,
    intern.name: intern,
    api_agent.name: api_agent,
}
```

That dictionary is then handed to the orchestrator.

## Why this matters

The orchestrator itself does not know how to solve tasks.

It only knows:

- who the manager is
- which worker agents exist
- how many loop iterations are allowed
- how many internal worker steps are allowed

So the runtime is the bridge between:

- agent definitions
- terminal I/O
- orchestration loop

---

# 6. The Orchestrator Is the Heart of the App

The most important class in the system is:

- `AgentOrchestrator` in `runtime/orchestrator.py`

This class is responsible for:

- talking to the user
- keeping the main conversation loop alive
- asking the manager what to do next
- running worker sessions
- asking the manager for the final synthesis
- saving history snapshots to `memory.txt`

You can think of it as the **runtime engine**.

---

# 7. Orchestrator State

Inside `AgentOrchestrator.__init__`, the orchestrator stores:

- `manager`
- `agents_dict`
- `steps_to_track`
- `max_iterations`
- `max_worker_steps`
- `input_func`
- `output_func`
- `sleep_func`

And it creates three memory objects:

- `step_history = Memory(is_structured=True)`
- `requests_history = Memory(is_structured=False)`
- `long_history = Memory(is_structured=False)`

## What each one means

### `step_history`

This is the **main structured execution log**.

It stores dict-like events such as:

- `user_request`
- `planner_action`
- `worker_action`
- `tool_result`
- `worker_done`
- `final_answer`

This is the most important history object in the system.

### `requests_history`

This stores the user’s requests and clarification replies as plain text entries.

This is what gives the system conversational continuity across multiple user questions in one terminal session.

### `long_history`

This currently exists but is not doing much meaningful orchestration work in the present version.

It is more of a placeholder / legacy concept than an important active piece.

---

# 8. How Output Is Printed

The orchestrator uses `_emit()` as a small wrapper around printing.

It optionally colors text with `termcolor`, but gracefully falls back to plain text if `termcolor` is not installed.

This is why the app can still work even if some optional dependencies are missing.

---

# 9. How Requests Enter the System

The main method is `AgentOrchestrator.run()`.

This method starts by:

1. deleting `memory.txt` if it exists
2. asking the initial user question if `initial_request` was not passed in
3. storing the user request in `requests_history`
4. recording a `user_request` event in `step_history`

Then it enters the main loop.

## Important detail

The conversation loop is now outermost.

That means:

- one user request runs
- it gets solved or times out
- then the user may ask another one
- the app stays alive until the user chooses to exit

So there are really two nested loops:

### Outer loop
Conversation loop over multiple user requests

### Inner loop
Execution loop for one specific request

---

# 10. The Main Execution Loop

For each request, the orchestrator runs a bounded step loop:

```text
for count in range(1, max_iterations + 1):
```

Default:

- `max_iterations = 9`

This is the manager-level safety limit.

It exists so the manager cannot loop forever.

Within each iteration:

1. the manager is asked to plan the next step
2. the result is recorded
3. the orchestrator branches based on manager action type

---

# 11. Manager Action Types

The manager must return exactly one of three JSON shapes:

```json
{"type":"delegate","agent":"<name>","instruction":"<task>"}
{"type":"ask_user","question":"<question>","reason":"<why blocked>"}
{"type":"finish","reason":"<why enough info exists>"}
```

These contracts are validated in `runtime/contracts.py`.

## Meaning of each

### `delegate`
The manager wants a worker agent to perform a bounded task.

### `ask_user`
The manager believes the system is blocked and needs information from the user.

### `finish`
The manager believes the system has enough evidence to answer now.

---

# 12. Why the Manager Does Not Use Tools

This is an intentional structural choice.

The manager:

- plans
- asks user clarifications
- synthesizes final answers

The manager does **not** execute normal tools.

This is different from your older design, where you had fake tools like:

- `talk_to_user`
- `FINAL STEP`

Those are gone from the execution flow.

Now the roles are much cleaner:

- manager = planner/narrator
- workers = executors

This is simpler to reason about.

---

# 13. If the Manager Says `ask_user`

The orchestrator calls `_ask_user(question, reason)`.

This method:

1. formats a user-facing prompt
2. reads the user reply
3. appends it to `requests_history`
4. records a `user_clarification` event in `step_history`

Then the main loop continues.

That means the manager is effectively doing:

```text
I cannot continue yet.
Please ask the user this.
Once the answer comes back, I will plan again.
```

---

# 14. If the Manager Says `finish`

The orchestrator calls `_run_synthesis()`.

This method:

1. calls `manager.synthesize_answer(...)`
2. passes full request context and full execution history
3. prints the final answer
4. records `final_answer` into `step_history`

After that, the request is considered complete.

But the whole conversation is not over yet.

The orchestrator then asks:

`Your request has been finished. Shall I help with anything else?:`

If the user enters a normal message:

- that becomes the next request

If the user enters an exit command:

- the orchestrator records `conversation_end`
- returns from `run()`

---

# 15. If the Manager Says `delegate`

This is the most sophisticated part of the current architecture.

Instead of letting the worker take only one tool step, the orchestrator now runs:

- `_run_worker_session(agent_name, active_agent, instruction)`

This creates a **bounded local session** for the worker.

Default:

- `max_worker_steps = 4`

That means one manager assignment can span multiple worker decisions.

Example:

Manager instruction:

`Locate and read my_wardrobe.json`

Worker session might do:

1. `check_if_file_exists`
2. `read_json`
3. `done`

All inside one delegation.

This is exactly the improvement you wanted when you said:

> manager says open file xyz and then secretary first locate it and then open

---

# 16. Assignment-Local History

Inside `_run_worker_session()`, the orchestrator creates:

```python
assignment_history = Memory(is_structured=True)
```

This memory exists only during that delegated session.

Its job is to help the worker remember what *it* already did in the current task.

This is crucial because global history alone is often too noisy.

Without assignment-local history, a worker can forget:

- the file path it just found
- the coordinates it just fetched
- the exact result of the previous tool call

With assignment history, the worker sees a compact local trace like:

- step 1: found file path
- step 2: now read the file

That makes multi-step delegation much more reliable.

---

# 17. Worker Session Loop

Inside `_run_worker_session()`, the orchestrator does:

```text
for worker_step in range(1, max_worker_steps + 1):
```

So each delegated task is itself a small internal loop.

For each worker step:

1. the worker is asked what to do next
2. the action is recorded in local and global history
3. the action is executed or handled
4. the loop continues until:
   - worker asks for user input
   - worker says done
   - step budget is exhausted

This is the key distinction in the current design:

- manager loop controls **task-level planning**
- worker loop controls **tool-level progress**

---

# 18. Worker Action Types

Workers return one of:

```json
{"type":"tool","tool":"<tool_name>","args":{...}}
{"type":"needs_user_input","question":"...","reason":"..."}
{"type":"done","summary":"..."}
```

These are validated by `validate_worker_action()` in `runtime/contracts.py`.

## Meaning

### `tool`
The worker wants to execute a tool now.

### `needs_user_input`
The worker cannot continue because required information is missing.

### `done`
The worker believes the delegated task is complete.

Important:

`done` does **not** mean “the whole user request is complete.”

It means:

- “my delegated subtask is complete”
- “return control to the manager”

Then the manager decides whether to:

- delegate again
- ask user
- finish

---

# 19. How the Worker Thinks

Workers reason through `Agent.think_in_session()` in `agents_training_facility/agents.py`.

This method builds the worker prompt using:

- manager instruction
- recent global execution history
- assignment-local history
- user request
- current worker step and max worker steps
- tool descriptions from the toolbox

Then it calls the LLM through `_ask_agent(..., return_json=True)`.

The model must produce valid JSON in the expected shape.

If the model wraps JSON in code fences or includes extra text, `_parse_json_response()` tries to recover it.

This is a practical robustness feature.

---

# 20. How Prompt Inputs Are Composed

The prompt system is split into:

- system prompts
- user prompts

## Worker side

System prompt:

- defines rules and JSON schema

User prompt:

- injects current instruction and history

This split is useful because:

- system prompt defines stable behavior
- user prompt carries current dynamic context

The same idea is used for the manager and synthesis steps.

---

# 21. How the Manager Thinks

The manager uses `CommandCentre.plan_next_step()`.

This method:

1. formats the manager planning prompt
2. includes:
   - request context
   - recent execution history
   - available agent descriptions
3. calls `_ask_agent(..., return_json=True)`
4. validates the returned planner action

The manager is therefore driven by:

- prompt rules
- the event log of what already happened
- the list of agents and their tool capabilities

---

# 22. Agent Personalities

Agent personalities come from `agents_training_facility/personalities.py`.

These descriptions are injected into prompts.

Examples:

- `secretary` is framed as a file-management specialist
- `api` is framed as an API specialist
- `pythondeveloper` is framed as a code-writing executor
- `manager` is framed as coordinator and final-answer owner

These personalities do not change the Python logic directly.

They influence the language model’s decision-making.

So they are “soft behavior configuration,” not hard runtime logic.

---

# 23. Tool Exposure Through `ToolBox`

The `ToolBox` class in `toolbox/toolbox.py` converts raw functions into `ToolSpec` objects.

Each tool spec stores:

- name
- callable
- Python signature
- description

That means when the worker sees tools, it does not just see names. It sees:

- function signature
- docstring-derived description

Example rendered shape:

```text
read_json(filename='data.json'): Read and return content of a JSON file as a dictionary...
```

This is why your docstrings matter a lot:

- they are both developer documentation
- and prompt-facing tool descriptions

---

# 24. Why Explicit `TOOLS` Registries Matter

Each tool module exposes a `TOOLS` dict.

Example from `tools/file_handler.py`:

```python
TOOLS = {
    "check_if_file_exists": check_if_file_exists,
    "search_files": search_files,
    ...
}
```

This is much safer than scanning every callable in the module, because otherwise the agent might accidentally expose:

- imported classes
- helper symbols
- third-party functions
- things that are not intended as tools

So `TOOLS` is your explicit contract saying:

“these are the functions the model is allowed to call.”

---

# 25. How Tool Execution Works

When a worker returns `{"type":"tool", ...}`, the orchestrator calls:

- `active_agent.execute_tool(worker_action)`

Inside `execute_tool()`:

1. get tool name from action
2. get args from action
3. look up tool in `ToolBox`
4. print the tool choice for terminal visibility
5. call the actual function
6. normalize result into a `ToolResult`

This means the runtime only needs to understand one result shape, regardless of the tool.

---

# 26. `ToolResult` Is the Standard Output Contract

Defined in `runtime/contracts.py`, `ToolResult` has:

- `success`
- `data`
- `summary`
- `error`

This standardization is important because before that, tools could return unrelated types:

- string
- int
- dict
- DataFrame
- sentinel token

Now the runtime gets a consistent shape.

This makes:

- logging cleaner
- testing easier
- worker history more structured
- tool failure handling more uniform

---

# 27. Success and Failure in Tools

Tools should usually return:

- `ToolResult.ok(...)`
- or `ToolResult.failure(...)`

Examples:

## Success

`read_json(...)` returns:

- `success=True`
- `data=<parsed json>`
- `summary="Read JSON file ..."`

## Failure

If the file does not exist:

- `success=False`
- `error="The file ... does not exist."`
- `summary="Could not read JSON file ..."`

This lets the manager and worker see not only that something failed, but *why*.

---

# 28. Why `summary` and `data` Are Both Needed

You might ask:

Why not just keep `data`?

Because the model often needs:

- a compact textual description for reasoning
- but also some structured raw result

For example:

- `summary`: “Found file 'my_wardrobe.json' at ...”
- `data`: actual absolute path

The summary helps prompt readability.
The data helps downstream reuse.

---

# 29. How Tool Results Enter History

When a tool finishes, `_run_worker_session()` records the result twice:

## A. In assignment-local history

This helps the current worker session reason about its own recent steps.

## B. In global `step_history`

This helps the manager and final synthesizer see what happened across the whole request.

The global record stores fields like:

- agent
- instruction
- worker step
- tool
- args
- success
- summary
- error
- data

That is much more robust than loose strings like:

- “used tool X with args Y”

---

# 30. Why `make_json_safe()` Exists

Not everything can be stored directly in structured history cleanly.

Examples:

- pandas DataFrames
- tuples
- odd nested objects

`make_json_safe()` converts them into serialization-friendly objects.

For DataFrames it creates:

- type = dataframe
- shape
- preview rows

This is especially useful because a worker may read a CSV and return a DataFrame, but history should stay readable and serializable.

---

# 31. How `Memory` Works

The `Memory` class in `memory/memory_manager.py` is intentionally simple.

It stores entries in a Python list.

It can operate in two modes:

- structured
- unstructured

## Structured mode

Requires entries to be dicts.

Used for:

- `step_history`
- assignment-local worker history

## Unstructured mode

Accepts plain values and lists.

Used for:

- `requests_history`
- `token_usage`

---

# 32. How Memory Is Rendered

The memory class has two important output methods:

## `recall_last_actions(steps)`

Returns a string representation of the last `steps` entries.

For structured memory, each entry is JSON-encoded.

For unstructured memory, entries are converted with `str(...)`.

This matters because both manager and worker prompts consume history as text.

## `recall_raw()`

Returns the raw list entries.

This is useful when the runtime wants to store structured sub-history inside a larger event.

---

# 33. The Current History Types in the System

There are really four history/state concepts in play:

## 1. `requests_history`

What the user has asked, plus user clarification replies.

This is conversational context.

## 2. `step_history`

Structured global event log of everything important that happened in execution.

This is the system’s main reasoning trace.

## 3. Assignment-local history

Temporary structured history for one delegated task.

This is the worker’s short-term tactical memory.

## 4. `token_usage`

Persistent logging of model responses and token usage.

This is cost/trace metadata, not reasoning memory.

---

# 34. What Gets Saved to Disk

This is a very important topic.

Not all history is persisted equally.

## A. `memory.txt`

The orchestrator writes to `memory.txt` using `_save_execution_history()`.

But note carefully:

It writes only:

- `step_history.recall_last_actions(self.steps_to_track)`

And `steps_to_track` defaults to `10`.

So `memory.txt` is **not** the full lifetime log.

It is a rolling text snapshot of the **most recent structured execution events**.

This file is mainly a human-readable recent trace.

Also, at the start of `run()`, if `memory.txt` exists, it is deleted.

So it is not treated as permanent history across launches.

## B. `memory/execution_cost/token_usage.txt`

Every model call appends usage info to this file through `Agent.token_usage.save_history(...)`.

This file is more persistent and cumulative.

It stores entries like:

- timestamp
- model output
- completion tokens
- prompt tokens

It is effectively your LLM usage log.

## C. `requests_history`

This is currently only in memory during runtime.

It is **not** automatically saved to a dedicated file.

## D. Assignment-local history

This is also in memory only.

It exists only for the lifetime of one delegated worker session.

## E. Full chat history across app restarts

You do **not** currently have a true durable whole-conversation store for all requests and all steps across sessions.

What you have is:

- recent execution snapshot in `memory.txt`
- durable token/cost log in `memory/execution_cost/token_usage.txt`
- runtime in-memory request history during one active session

That distinction is important.

---

# 35. What Happens to History Across Multiple Questions in One Session

Since the conversation loop now stays alive, `requests_history` keeps growing during one terminal session.

That means if you ask:

1. question one
2. then question two
3. then question three

all of them are still part of the live request context unless the prompts or manager naturally ignore older ones.

Similarly, `step_history` continues to grow during the same session.

So the second and third requests are not isolated by default.

They are part of one continuous conversation context.

This is good for continuity, but it also means:

- older tasks may influence later planning
- prompt context may get noisier over time

That is a design choice to be aware of.

---

# 36. What Happens When a Worker Says `done`

This is subtle and important.

When a worker says:

```json
{"type":"done","summary":"..."}
```

the orchestrator does **not** immediately synthesize the final user answer.

Instead it:

- records `worker_done`
- returns control to the manager loop

Then the manager gets another chance to plan.

This is correct behavior because:

- worker completion means delegated subtask complete
- not necessarily whole request complete

So `done` means:

“I finished my assigned sub-problem.”

Then the manager decides:

- delegate again
- ask user
- finish

---

# 37. What Happens If a Worker Budget Runs Out

If the worker uses up all allowed internal steps without returning `done` or `needs_user_input`, the orchestrator records:

- `worker_budget_exhausted`

That event includes:

- agent
- instruction
- max worker steps
- assignment history

Then control goes back to the manager loop.

So bounded worker sessions prevent infinite micro-loops.

This is one of the key safety mechanisms in the current design.

---

# 38. Why This Design Is Better Than One-Step Workers

In your older one-step-per-delegation design, the manager had to micromanage too much.

Example problem:

- manager says “read wardrobe file”
- secretary finds the file
- control goes back to manager
- manager must now say “read the discovered path”

That was inefficient and fragile.

Now the worker can complete a small tactical chain:

- find file
- read file
- done

This is much closer to how a human would work.

So the manager remains strategic while the worker becomes tactically competent.

---

# 39. How Final Answer Generation Works

The manager’s `synthesize_answer()` uses the synthesis prompt.

The synthesis prompt tells the model:

- read execution history carefully
- read user request carefully
- answer from evidence
- do not invent missing facts if history is uncertain

This means your final answer is not directly generated by the worker who used the tools.

It is generated by the manager after all the evidence has been gathered.

That is a good design if you want:

- one consistent narrator
- one final answer style
- centralized answer responsibility

---

# 40. How a Real Example Flows

Let’s trace a wardrobe + weather request.

User asks:

`Check weather near Wawozowa 32b/1 Krakow and my_wardrobe.json file ...`

## Step A
Runtime records the user request.

## Step B
Manager plans:

```json
{"type":"delegate","agent":"api","instruction":"Get location and weather"}
```

## Step C
API worker session starts.

Possible internal steps:

1. `address_to_geolocation(address)`
2. `get_weather_forecast(lat, lon)`
3. `done`

## Step D
Control returns to manager.

## Step E
Manager plans:

```json
{"type":"delegate","agent":"secretary","instruction":"Locate and read wardrobe JSON"}
```

## Step F
Secretary worker session starts.

Possible internal steps:

1. `check_if_file_exists("my_wardrobe.json")`
2. `read_json(full_path)`
3. `done`

## Step G
Manager now has weather plus wardrobe contents.

Manager plans:

```json
{"type":"finish","reason":"Enough information exists"}
```

## Step H
Manager synthesizes final answer.

## Step I
Conversation remains open for next user request.

That is the intended happy-path flow.

---

# 41. Current Strengths of the Architecture

The strongest parts of the current design are:

## Clean role separation

- manager plans
- workers execute
- tools do real work

## Structured contracts

- manager actions are validated
- worker actions are validated
- tool results are normalized

## Better worker autonomy

Workers can now finish short subtask chains inside one delegation.

## Better history structure

You now record real event objects rather than mostly informal strings.

## Stronger prompt clarity

The prompts now define explicit JSON schemas and clearer role boundaries.

---

# 42. Current Limits / Things to Be Aware Of

Even though the structure is much better now, there are still some important limitations:

## Request context is cumulative in one session

The second request inherits the first request’s history unless prompts effectively separate them.

## `memory.txt` is not a durable full log

It is just a rolling recent snapshot.

## Assignment history is temporary

It helps a worker within one delegated task, but it is not persisted separately.

## Tool descriptions come from docstrings

This is powerful, but also means tool docs serve two purposes:

- developer documentation
- model-facing prompt content

That is why changes to docstrings affect agent behavior.

## Some files still contain legacy artifacts

For example, there are old memory files in the repo that are not central to current orchestration.

Those are useful as historical context, but they are not the current main control path.

---

# 43. How To Read the Code Going Forward

When you study this repo, use this strategy:

## First pass

Follow control flow:

- `main.py`
- `runtime/orchestrator.py`

## Second pass

Understand the model interface:

- `agents_training_facility/agents.py`
- `prompts/prompts.py`
- `runtime/contracts.py`

## Third pass

Understand the data/actions:

- `toolbox/toolbox.py`
- `tools/file_handler.py`
- `tools/apis.py`
- `tools/programer.py`

## Fourth pass

Study history/state:

- `memory/memory_manager.py`
- `memory/execution_cost/token_usage.txt`

That reading order matches the real runtime structure much better than reading alphabetically.

---

# 44. One-Sentence Summary of Each Main File

## `main.py`
Boot the runtime.

## `runtime/orchestrator.py`
Run the conversation and delegate work.

## `agents_training_facility/agents.py`
Define agents, model calls, tool execution, and manager behavior.

## `prompts/prompts.py`
Define model instructions and response schemas.

## `runtime/contracts.py`
Define tool result format and action validation.

## `memory/memory_manager.py`
Store and render history.

## `toolbox/toolbox.py`
Convert Python functions into model-visible tool specs.

## `tools/file_handler.py`
File discovery, file reading, text writing, CSV/JSON loading.

## `tools/apis.py`
Geolocation and weather retrieval.

## `tools/programer.py`
Write and execute Python scripts.

## `tools/utils_handler.py`
Small utility tools.

---

# 45. Core Conceptual Summary

If you want the shortest correct explanation of the current system, it is this:

> The app is a manager-driven execution engine where a planner model delegates bounded subtasks to specialized worker agents, workers choose tools using prompt-visible tool descriptions, tool outputs are normalized into structured results, and both global and assignment-local histories are used to make later planning more reliable.

That sentence is dense, but it is the architecture.

---

# 46. Final Advice for Learning From This Repo

When you feel lost, ask these five questions:

1. Who is currently making the decision?
   Manager or worker?

2. What contract is expected right now?
   Planner action, worker action, or tool result?

3. What history is available right now?
   Request history, global execution history, or assignment-local history?

4. Is this logic prompt-driven or Python-driven?
   Some behavior is hard-coded, some is model-guided.

5. Is this step strategic or tactical?
   Manager work is strategic. Worker work is tactical.

If you keep those five questions in mind, the code becomes much easier to navigate.

---

# 47. Suggested Next Learning Exercises

If you want to learn this code deeply, try these exercises:

## Exercise 1
Take one real user request and trace every event that would be recorded in `step_history`.

## Exercise 2
Pretend you are the secretary worker and manually simulate a 3-step assignment history.

## Exercise 3
Add a brand-new simple tool in your head and figure out:

- where it must be defined
- how it enters `TOOLS`
- how the worker would discover it

## Exercise 4
Read one tool module and ask:

- what is the prompt-visible description?
- what is the actual Python behavior?
- what is the exact `ToolResult` shape?

## Exercise 5
Trace how a final answer is produced without any fake “final tool”.

That will make the current architecture feel natural instead of abstract.

---

# 48. Closing Thought

The current codebase is no longer “a single smart prompt with tools.”

It is now a small runtime system with:

- role separation
- structured contracts
- bounded delegated execution
- event-based history
- persistent conversation loop

That is a much stronger base for growing the project.
