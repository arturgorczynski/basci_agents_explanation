# Multi-Agent Runtime (Manager + Workers)

This project is a manager-led multi-agent assistant.

The manager plans one next step at a time, delegates work to specialized workers, and synthesizes the final answer.

## Current Architecture

- `manager` plans and decides when enough information exists
- `pythondeveloper` writes and executes Python scripts
- `secretary` handles file reads/searches/writes
- `data_manager` handles local document vector search and topic news checks
- `api` calls external APIs (geolocation/weather + Tavily web search)

## Runtime Safety Rules

The runtime enforces these policies in code:

- Python execution uses the project `.venv` only
- Read access: `data/` and `coding_output/` only
- Write access: `coding_output/` only
- Script execution: `coding_output/` only

Important: this is repo-level policy enforcement, not an OS/container sandbox.

## Key Files

- `main.py`: entrypoint and `.venv` enforcement
- `run_ui.py`: entrypoint for the Gradio web UI
- `src/agentic_system/runtime/orchestrator.py`: main control loop
- `src/agentic_system/agents_training_facility/agents.py`: model/tool orchestration
- `src/agentic_system/tools/file_handler.py`: scoped file operations
- `src/agentic_system/tools/programer.py`: code execution + package listing
- `src/agentic_system/tools/data_manager.py`: local document vector indexing and semantic query
- `src/agentic_system/tools/path_policy.py`: centralized path and `.venv` policy
- `src/agentic_system/runtime/tracing.py`: session trace events (`memory/ui_traces/*.jsonl`)
- `src/agentic_system/ui/app.py`: optional Gradio trace UI

## Setup

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

2. Install dependencies:

   ```bash
   # Windows
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt

   # macOS / Linux
   .venv/bin/python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and configure your provider settings.

## Run (Terminal)

```bash
# Windows
.\.venv\Scripts\python.exe main.py

# macOS / Linux
.venv/bin/python main.py
```

If you run with a non-`.venv` interpreter, startup fails fast by design.

## Run (UI)

```bash
# Windows
.\.venv\Scripts\python.exe run_ui.py

# macOS / Linux
.venv/bin/python run_ui.py
```

Then open http://127.0.0.1:7860 in your browser.

## Notes on Repo State

- Runtime outputs (conversation history, traces, token usage) are generated files and can be cleaned safely.
- `data/` contains sample input files only.
- `coding_output/` is the only intended output directory for generated scripts/artifacts.
