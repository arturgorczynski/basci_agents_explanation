import json
import os
import subprocess
from datetime import datetime

from runtime.contracts import ToolResult
from tools.path_policy import (
    AGENTIC_ROOT,
    PACKAGE_CACHE_PATH,
    PYTHONDEVELOPER_CODE_ROOT,
    ensure_runtime_directories,
    is_allowed_pythondeveloper_code_path,
    resolve_venv_python,
    resolve_pythondeveloper_code_path,
    validate_project_venv,
)


def write_python_code(code, filename="generated_script.py"):
    """
    Writes the provided code into a Python file.

    Parameters:
        code (str): The code to write into the file.
        filename (str): Target file path. Relative paths are resolved under
            `coding_output/pythondeveloper_code/`. Default path is
            `coding_output/pythondeveloper_code/generated_script.py`.

    Returns:
        ToolResult:
            - data (str): Filename that was written.
            - summary (str): Short explanation of the write result.
            - error (str | None): Failure reason if the file could not be written.
    """
    ensure_runtime_directories()
    decoded_code = code.encode().decode("unicode_escape")

    try:
        target_path = resolve_pythondeveloper_code_path(filename)
    except ValueError as exc:
        return ToolResult.failure(
            str(exc),
            summary="Could not resolve the output file path.",
        )

    if not is_allowed_pythondeveloper_code_path(target_path):
        return ToolResult.failure(
            (
                "Access denied for write_python_code. Python developer files must stay "
                f"inside '{PYTHONDEVELOPER_CODE_ROOT}'."
            ),
            summary="Access denied for write_python_code.",
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as file:
        file.write(decoded_code)

    return ToolResult.ok(
        data=str(target_path),
        summary=f"Wrote Python code to '{target_path}'.",
    )


def run_python_script(filename):
    """
    Executes a Python script from `coding_output/pythondeveloper_code/` using
    the Python executable from the local project `.venv`.

    Parameters:
        filename (str): Script file path. Relative paths are resolved under
            `coding_output/pythondeveloper_code/`.

    Returns:
        ToolResult:
            - data (dict): Includes return code and captured stdout/stderr when available.
            - summary (str): Short explanation of the execution result.
            - error (str | None): Failure reason if the file does not exist or execution fails.
    """
    ensure_runtime_directories()

    try:
        script_path = resolve_pythondeveloper_code_path(filename)
    except ValueError as exc:
        return ToolResult.failure(
            str(exc),
            summary="Could not resolve script path for execution.",
        )

    if not is_allowed_pythondeveloper_code_path(script_path):
        return ToolResult.failure(
            (
                "Access denied for run_python_script. Python developer scripts must stay "
                f"inside '{PYTHONDEVELOPER_CODE_ROOT}'."
            ),
            summary="Access denied for run_python_script.",
        )

    if not script_path.is_file():
        return ToolResult.failure(
            f"The file '{script_path}' does not exist.",
            summary=f"Could not execute '{script_path}'.",
        )

    venv_ok, venv_error = validate_project_venv()
    if not venv_ok:
        return ToolResult.failure(venv_error, summary="Could not execute script from project .venv.")

    python_executable = resolve_venv_python()
    if python_executable is None:
        return ToolResult.failure(
            "Project virtual environment Python executable could not be resolved.",
            summary="Could not execute script from project .venv.",
        )

    command = [str(python_executable), str(script_path)]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(AGENTIC_ROOT),
            env=env,
        )
        return ToolResult.ok(
            data={
                "script_path": str(script_path),
                "command": command,
                "cwd": str(AGENTIC_ROOT),
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            summary=f"Executed Python script '{script_path}'.",
        )
    except subprocess.CalledProcessError as exc:
        stderr_text = (exc.stderr or "").strip()
        stdout_text = (exc.stdout or "").strip()
        failure_details = stderr_text or stdout_text or "No stdout/stderr captured."
        return ToolResult.failure(
            (
                f"Script '{script_path}' failed with return code {exc.returncode}.\n"
                f"Captured output:\n{failure_details}"
            ),
            data={
                "script_path": str(script_path),
                "command": command,
                "cwd": str(AGENTIC_ROOT),
                "returncode": exc.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
            },
            summary=f"Execution failed for '{script_path}' with return code {exc.returncode}.",
        )


def list_installed_packages(refresh: bool = False):
    """
    Return installed packages from the project `.venv`.

    Parameters:
        refresh (bool): When True, force a fresh query via `pip list --format=json`.
            When False, return cached data when available.

    Returns:
        ToolResult:
            - data (dict): Package payload with keys `packages`, `count`, `timestamp`, and `cached`.
            - summary (str): Short explanation of whether cached or live data was returned.
            - error (str | None): Failure reason if `.venv` is invalid or listing fails.
    """
    ensure_runtime_directories()

    if not refresh and PACKAGE_CACHE_PATH.exists():
        try:
            with PACKAGE_CACHE_PATH.open("r", encoding="utf-8") as cache_file:
                cached_payload = json.load(cache_file)
            packages = cached_payload.get("packages", [])
            timestamp = cached_payload.get("timestamp")
            count = int(cached_payload.get("count", len(packages)))
            return ToolResult.ok(
                data={
                    "packages": packages,
                    "count": count,
                    "timestamp": timestamp,
                    "cached": True,
                },
                summary=f"Loaded {count} package(s) from cache.",
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            # Fall back to a live query when cache is corrupted or unreadable.
            pass

    venv_ok, venv_error = validate_project_venv()
    if not venv_ok:
        return ToolResult.failure(
            venv_error,
            summary="Could not list installed packages from project .venv.",
        )

    python_executable = resolve_venv_python()
    if python_executable is None:
        return ToolResult.failure(
            "Project virtual environment Python executable could not be resolved.",
            summary="Could not list installed packages from project .venv.",
        )

    command = [str(python_executable), "-m", "pip", "list", "--format=json"]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(AGENTIC_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        return ToolResult.failure(
            f"Package listing failed with return code {exc.returncode}: {exc.stderr}",
            data={
                "returncode": exc.returncode,
                "stdout": (exc.stdout or "").strip(),
                "stderr": (exc.stderr or "").strip(),
            },
            summary="Could not list installed packages from project .venv.",
        )

    try:
        raw_packages = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return ToolResult.failure(
            f"Failed to decode package list JSON: {exc}",
            summary="Could not parse package listing output.",
        )

    packages = sorted(
        [
            {
                "name": str(package.get("name", "")).strip(),
                "version": str(package.get("version", "")).strip(),
            }
            for package in raw_packages
            if str(package.get("name", "")).strip()
        ],
        key=lambda item: item["name"].lower(),
    )
    timestamp = datetime.now().isoformat(timespec="seconds")
    snapshot = {
        "packages": packages,
        "count": len(packages),
        "timestamp": timestamp,
    }

    try:
        with PACKAGE_CACHE_PATH.open("w", encoding="utf-8") as cache_file:
            json.dump(snapshot, cache_file, ensure_ascii=False, indent=2)
    except OSError:
        # Non-critical: package data is still returned even if cache write fails.
        pass

    return ToolResult.ok(
        data={**snapshot, "cached": False},
        summary=f"Retrieved {len(packages)} package(s) from project .venv.",
    )


TOOLS = {
    "write_python_code": write_python_code,
    "run_python_script": run_python_script,
    "list_installed_packages": list_installed_packages,
}
