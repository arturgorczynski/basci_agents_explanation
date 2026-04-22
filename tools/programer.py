import os
import subprocess
import sys

from runtime.contracts import ToolResult


def write_python_code(code, filename="generated_script.py"):
    """
    Writes the provided code into a Python file.

    Parameters:
        code (str): The code to write into the file.
        filename (str): Name of the file to create. Default is `generated_script.py`.

    Returns:
        ToolResult:
            - data (str): Filename that was written.
            - summary (str): Short explanation of the write result.
            - error (str | None): Failure reason if the file could not be written.
    """
    decoded_code = code.encode().decode("unicode_escape")
    with open(filename, "w", encoding="utf-8") as file:
        file.write(decoded_code)

    return ToolResult.ok(
        data=filename,
        summary=f"Wrote Python code to '{filename}'.",
    )


def run_python_script(filename):
    """
    Executes a Python script specified by the filename using the Python executable
    from a local `.venv` if it exists.

    Parameters:
        filename (str): Path to the Python script file to execute.

    Returns:
        ToolResult:
            - data (dict): Includes return code and captured stdout/stderr when available.
            - summary (str): Short explanation of the execution result.
            - error (str | None): Failure reason if the file does not exist or execution fails.
    """
    if not os.path.isfile(filename):
        return ToolResult.failure(
            f"The file '{filename}' does not exist.",
            summary=f"Could not execute '{filename}'.",
        )

    script_path = os.path.abspath(filename)
    venv_python = os.path.join(".venv", "bin", "python")
    if not os.path.exists(venv_python):
        venv_python = os.path.join(".venv", "Scripts", "python.exe")

    python_executable = venv_python if os.path.exists(venv_python) else sys.executable
    command = [os.path.abspath(python_executable), script_path]

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        output = result.stdout.strip()
        return ToolResult.ok(
            data={"returncode": result.returncode, "stdout": output},
            summary=f"Executed Python script '{filename}'.",
        )
    except subprocess.CalledProcessError as exc:
        return ToolResult.failure(
            f"Script '{filename}' failed with return code {exc.returncode}: {exc.stderr}",
            data={"returncode": exc.returncode, "stdout": exc.stdout, "stderr": exc.stderr},
            summary=f"Execution failed for '{filename}'.",
        )


TOOLS = {
    "write_python_code": write_python_code,
    "run_python_script": run_python_script,
}
