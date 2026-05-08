from __future__ import annotations

from pathlib import Path
import sys


# src/agentic_system/tools/ → src/agentic_system/
AGENTIC_ROOT = Path(__file__).resolve().parents[1]
# src/agentic_system/ → src/ → project root (where .venv lives)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_ROOT = (AGENTIC_ROOT / "data").resolve()
CODING_OUTPUT_ROOT = (AGENTIC_ROOT / "coding_output").resolve()
PYTHONDEVELOPER_CODE_ROOT = (CODING_OUTPUT_ROOT / "pythondeveloper_code").resolve()
READ_ROOTS = (DATA_ROOT, CODING_OUTPUT_ROOT)
WRITE_ROOT = CODING_OUTPUT_ROOT

VENV_ROOT = (PROJECT_ROOT / ".venv").resolve()
VENV_PYTHON_CANDIDATES = (
    VENV_ROOT / "Scripts" / "python.exe",
    VENV_ROOT / "bin" / "python",
)

PACKAGE_CACHE_PATH = (AGENTIC_ROOT / "memory" / "venv_packages_cache.json").resolve()

READ_ACCESS_DENIED = (
    "Access denied. Read operations are allowed only from 'data/' and 'coding_output/'."
)
WRITE_ACCESS_DENIED = (
    "Access denied. Write operations are allowed only to 'coding_output/'."
)
EXECUTE_ACCESS_DENIED = (
    "Access denied. Script execution is allowed only from 'coding_output/'."
)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_runtime_directories() -> None:
    CODING_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PYTHONDEVELOPER_CODE_ROOT.mkdir(parents=True, exist_ok=True)
    PACKAGE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _coerce_path(path_value: str | Path) -> Path:
    text = str(path_value).strip()
    if not text:
        raise ValueError("Path value cannot be empty.")
    return Path(text)


def resolve_read_path(path_value: str | Path, *, default_to_data: bool = True) -> Path:
    raw_path = _coerce_path(path_value)
    known_roots = {DATA_ROOT.name, CODING_OUTPUT_ROOT.name}

    if raw_path.is_absolute():
        return raw_path.resolve()

    if raw_path.parts and raw_path.parts[0] in known_roots:
        return (AGENTIC_ROOT / raw_path).resolve()

    if len(raw_path.parts) == 1:
        data_candidate = (DATA_ROOT / raw_path).resolve()
        output_candidate = (CODING_OUTPUT_ROOT / raw_path).resolve()
        if data_candidate.exists():
            return data_candidate
        if output_candidate.exists():
            return output_candidate
        return data_candidate if default_to_data else output_candidate

    return (AGENTIC_ROOT / raw_path).resolve()


def resolve_write_path(path_value: str | Path) -> Path:
    raw_path = _coerce_path(path_value)
    known_roots = {DATA_ROOT.name, CODING_OUTPUT_ROOT.name}
    if raw_path.is_absolute():
        return raw_path.resolve()
    if raw_path.parts and raw_path.parts[0] in known_roots:
        return (AGENTIC_ROOT / raw_path).resolve()
    return (WRITE_ROOT / raw_path).resolve()


def is_allowed_read_path(path_value: Path) -> bool:
    resolved = path_value.resolve()
    return any(_is_within(resolved, allowed_root) for allowed_root in READ_ROOTS)


def is_allowed_write_path(path_value: Path) -> bool:
    resolved = path_value.resolve()
    return _is_within(resolved, WRITE_ROOT)


def resolve_pythondeveloper_code_path(path_value: str | Path) -> Path:
    raw_path = _coerce_path(path_value)
    known_roots = {CODING_OUTPUT_ROOT.name, PYTHONDEVELOPER_CODE_ROOT.name}
    if raw_path.is_absolute():
        return raw_path.resolve()
    if raw_path.parts and raw_path.parts[0] in known_roots:
        return (AGENTIC_ROOT / raw_path).resolve()
    return (PYTHONDEVELOPER_CODE_ROOT / raw_path).resolve()


def is_allowed_pythondeveloper_code_path(path_value: Path) -> bool:
    resolved = path_value.resolve()
    return _is_within(resolved, PYTHONDEVELOPER_CODE_ROOT)


def resolve_venv_python() -> Path | None:
    for candidate in VENV_PYTHON_CANDIDATES:
        if candidate.exists():
            return candidate.resolve()
    return None


def validate_project_venv() -> tuple[bool, str]:
    if not VENV_ROOT.exists():
        return (
            False,
            "Project virtual environment '.venv' was not found. Create it with `python -m venv .venv`.",
        )

    pyvenv_cfg = VENV_ROOT / "pyvenv.cfg"
    if not pyvenv_cfg.exists():
        return (
            False,
            "Project virtual environment '.venv' is invalid (missing pyvenv.cfg).",
        )

    venv_python = resolve_venv_python()
    if venv_python is None:
        return (
            False,
            "Project virtual environment '.venv' is invalid (Python executable not found).",
        )

    return True, ""


def is_running_from_project_venv() -> bool:
    try:
        current_executable = Path(sys.executable).resolve()
    except OSError:
        return False
    return _is_within(current_executable, VENV_ROOT)


def validate_runtime_interpreter() -> tuple[bool, str]:
    is_valid, validation_message = validate_project_venv()
    if not is_valid:
        return is_valid, validation_message

    if not is_running_from_project_venv():
        expected = resolve_venv_python()
        expected_display = str(expected) if expected else "<missing>"
        current_display = str(Path(sys.executable).resolve())
        return (
            False,
            "Runtime must be started with the project .venv interpreter.\n"
            f"Current interpreter: {current_display}\n"
            f"Expected interpreter: {expected_display}\n"
            "Run with '.\\.venv\\Scripts\\python.exe main.py' (Windows) or "
            "'./.venv/bin/python main.py' (POSIX).",
        )

    return True, ""
