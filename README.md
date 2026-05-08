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

The runtime now enforces these policies in code:

- Python execution uses project `.venv` only
- Read access: `data/` and `coding_output/` only
- Write access: `coding_output/` only
- Script execution: `coding_output/` only

Important: this is repo-level policy enforcement, not an OS/container sandbox.

## Key Files

- `main.py`: entrypoint and `.venv` enforcement
- `runtime/orchestrator.py`: main control loop
- `agents_training_facility/agents.py`: model/tool orchestration
- `tools/file_handler.py`: scoped file operations
- `tools/programer.py`: code execution + package listing
- `tools/data_manager.py`: local document vector indexing and semantic query
- `tools/path_policy.py`: centralized path and `.venv` policy
- `runtime/tracing.py`: session trace events (`memory/ui_traces/*.jsonl`)
- `ui/app.py`: optional Gradio trace UI

## Setup

1. Create virtual env:

```bash
python -m venv .venv
```

2. Install dependencies:

```bash
.\.venv\Scripts\python.exe -m pip install openai python-dotenv requests pandas termcolor gradio faiss-cpu pypdf numpy
```

3. Create `.env` from `.env.example` and configure provider settings.

## Run (Terminal)

```bash
.\.venv\Scripts\python.exe main.py
```

If you run with a non-`.venv` interpreter, startup fails fast by design.

## Run (UI)

```bash
.\.venv\Scripts\python.exe -m ui.app
```

## Notes on Repo State

- Runtime outputs (conversation history, traces, token usage) are generated files and can be cleaned safely.
- `data/` contains sample input files only.
- `coding_output/` is the only intended output directory for generated scripts/artifacts.
