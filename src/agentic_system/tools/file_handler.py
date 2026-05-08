from datetime import datetime
import json
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency fallback
    pd = None

from runtime.contracts import ToolResult
from tools.path_policy import (
    READ_ACCESS_DENIED,
    READ_ROOTS,
    WRITE_ACCESS_DENIED,
    ensure_runtime_directories,
    is_allowed_read_path,
    is_allowed_write_path,
    resolve_read_path,
    resolve_write_path,
)


def _deny_read() -> ToolResult:
    return ToolResult.failure(READ_ACCESS_DENIED, summary=READ_ACCESS_DENIED)


def _deny_write() -> ToolResult:
    return ToolResult.failure(WRITE_ACCESS_DENIED, summary=WRITE_ACCESS_DENIED)


def check_if_file_exists(filename):
    """
    Search allowed read directories (`data/`, `coding_output/`) for a specific file.
    Proper to find a location of a given file.
    USE ONLY IF FILENAME PROVIDED.

    Parameters:
        filename (str): The name of the file to search for.

    Returns:
        ToolResult:
            - data (str): Full path to the file if found.
            - summary (str): Short explanation of the search result.
            - error (str | None): Failure reason if the file does not exist.
    """
    try:
        candidate = resolve_read_path(filename)
    except ValueError as exc:
        return ToolResult.failure(str(exc), summary="Could not resolve file path.")

    if candidate.exists():
        if not is_allowed_read_path(candidate):
            return _deny_read()
        if candidate.is_file():
            return ToolResult.ok(
                data=str(candidate),
                summary=f"Found file '{filename}' at '{candidate}'.",
            )
        return ToolResult.failure(
            f"'{candidate}' exists but is not a file.",
            summary=f"Could not find file '{filename}'.",
        )

    raw_path = Path(str(filename).strip())
    is_plain_filename = not raw_path.is_absolute() and len(raw_path.parts) == 1
    if is_plain_filename:
        for search_root in READ_ROOTS:
            for path in search_root.rglob(raw_path.name):
                if path.is_file():
                    resolved = path.resolve()
                    if is_allowed_read_path(resolved):
                        return ToolResult.ok(
                            data=str(resolved),
                            summary=f"Found file '{filename}' at '{resolved}'.",
                        )

    return ToolResult.failure(
        f"File '{filename}' not found in allowed read directories.",
        summary=f"Could not find file '{filename}'.",
    )


def search_files(pattern: str, root: str | Path | None = None) -> ToolResult:
    """
    Return every file matching *pattern* starting at *root* and recurse through
    all child directories.

    Parameters:
        pattern (str): A Unix-style glob such as '*.txt' or 'A*.py'.
        root (str | pathlib.Path | None): Directory to start from. If omitted,
            both allowed read roots are used.

    Returns:
        ToolResult:
            - data (list[str]): Absolute paths of all matching files.
            - summary (str): Short explanation of how many matches were found.
            - error (str | None): Present only if the search fails unexpectedly.
    """
    if not pattern or not str(pattern).strip():
        return ToolResult.failure(
            "Search pattern cannot be empty.",
            summary="Could not perform file search.",
        )

    search_roots: list[Path]
    if root is None:
        search_roots = list(READ_ROOTS)
    else:
        try:
            root_path = resolve_read_path(root, default_to_data=False)
        except ValueError as exc:
            return ToolResult.failure(str(exc), summary="Could not resolve search root.")
        if not is_allowed_read_path(root_path):
            return _deny_read()
        if not root_path.exists():
            return ToolResult.failure(
                f"The root directory '{root_path}' does not exist.",
                summary=f"Could not search files with pattern '{pattern}'.",
            )
        if not root_path.is_dir():
            return ToolResult.failure(
                f"The root path '{root_path}' is not a directory.",
                summary=f"Could not search files with pattern '{pattern}'.",
            )
        search_roots = [root_path]

    matches: list[str] = []
    for search_root in search_roots:
        for path in search_root.rglob(pattern):
            if path.is_file():
                resolved = path.resolve()
                if is_allowed_read_path(resolved):
                    matches.append(str(resolved))

    unique_matches = sorted(set(matches))
    return ToolResult.ok(
        data=unique_matches,
        summary=f"Found {len(unique_matches)} file(s) matching pattern '{pattern}'.",
    )


def text_writer(message=None, filename="results.txt"):
    """
    Write or append a message to a text file. If no message is provided,
    file will not be written.

    Parameters:
        filename (str): Name of the text file. Relative paths are resolved under
            `coding_output/`. If omitted then `coding_output/results.txt` is used.
        message (str): Message to be written or appended.

    Returns:
        ToolResult:
            - data (str): Filename that was written to.
            - summary (str): Short explanation whether file was created or appended.
            - error (str | None): Failure reason when no message is provided.
    """
    if message is None:
        return ToolResult.failure(
            "No message was provided to write.",
            summary="Skipped writing because no message was provided.",
        )

    ensure_runtime_directories()
    try:
        target_path = resolve_write_path(filename)
    except ValueError as exc:
        return ToolResult.failure(str(exc), summary="Could not resolve output file path.")
    if not is_allowed_write_path(target_path):
        return _deny_write()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message_to_write = f"{current_time} - {message}\n"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = target_path.exists()
    mode = "a" if file_exists else "w"

    with target_path.open(mode, encoding="utf-8") as file:
        file.write(message_to_write)

    action = "Appended" if file_exists else "Created"
    return ToolResult.ok(
        data=str(target_path),
        summary=f"{action} text file '{target_path}'.",
    )


def read_text(filename="coding_output/results.txt"):
    """
    Read and return content of a text file.

    Parameters:
        filename (str): Name of the text file to read. Defaults to
            `coding_output/results.txt`.

    Returns:
        ToolResult:
            - data (str): Contents of the file as a string.
            - summary (str): Short explanation of the read result.
            - error (str | None): Failure reason if the file does not exist.
    """
    try:
        source_path = resolve_read_path(filename, default_to_data=False)
    except ValueError as exc:
        return ToolResult.failure(str(exc), summary="Could not resolve text file path.")
    if not is_allowed_read_path(source_path):
        return _deny_read()

    if not source_path.exists():
        return ToolResult.failure(
            f"The file '{source_path}' does not exist.",
            summary=f"Could not read text file '{filename}'.",
        )

    if not source_path.is_file():
        return ToolResult.failure(
            f"'{source_path}' exists but is not a file.",
            summary=f"Could not read text file '{filename}'.",
        )

    with source_path.open("r", encoding="utf-8") as file:
        contents = file.read()

    return ToolResult.ok(
        data=contents,
        summary=f"Read text file '{source_path}'.",
    )


def csv_reader(filepath="data.csv", **kwargs):
    """
    Read a CSV file into a Pandas DataFrame. Additional parameters can be passed
    to handle custom delimiters, missing values, or column types.
    Use only if file name and its location are known.

    Parameters:
        filepath (str): Path to the CSV file. Defaults to `data.csv`.
        **kwargs: Additional keyword arguments forwarded to `pandas.read_csv()`.

    Returns:
        ToolResult:
            - data (pd.DataFrame): The content of the CSV file as a DataFrame.
            - summary (str): Short explanation of the read result.
            - error (str | None): Failure reason if file is missing, pandas is unavailable,
              or parsing fails.
    """
    if pd is None:
        return ToolResult.failure(
            "pandas package is required to read CSV files.",
            summary="Could not read CSV because pandas is not installed.",
        )

    try:
        source_path = resolve_read_path(filepath, default_to_data=True)
    except ValueError as exc:
        return ToolResult.failure(str(exc), summary="Could not resolve CSV file path.")
    if not is_allowed_read_path(source_path):
        return _deny_read()

    try:
        dataframe = pd.read_csv(source_path, **kwargs)
        return ToolResult.ok(
            data=dataframe,
            summary=f"Read CSV file '{source_path}'.",
        )
    except FileNotFoundError:
        return ToolResult.failure(
            f"The file '{source_path}' does not exist.",
            summary=f"Could not read CSV file '{filepath}'.",
        )
    except Exception as exc:
        return ToolResult.failure(
            f"An error occurred while reading '{source_path}': {exc}",
            summary=f"CSV read failed for '{filepath}'.",
        )


def read_json(filename="data.json"):
    """
    Read and return content of a JSON file as a dictionary.

    Parameters:
        filename (str): Name of the JSON file to read. Defaults to `data.json`.

    Returns:
        ToolResult:
            - data (dict): Parsed JSON content.
            - summary (str): Short explanation of the read result.
            - error (str | None): Failure reason if the file does not exist.
    """
    try:
        source_path = resolve_read_path(filename, default_to_data=True)
    except ValueError as exc:
        return ToolResult.failure(str(exc), summary="Could not resolve JSON file path.")
    if not is_allowed_read_path(source_path):
        return _deny_read()

    if not source_path.exists():
        return ToolResult.failure(
            f"The file '{source_path}' does not exist.",
            summary=f"Could not read JSON file '{filename}'.",
        )

    if not source_path.is_file():
        return ToolResult.failure(
            f"'{source_path}' exists but is not a file.",
            summary=f"Could not read JSON file '{filename}'.",
        )

    with source_path.open("r", encoding="utf-8") as file:
        contents = json.load(file)

    return ToolResult.ok(
        data=contents,
        summary=f"Read JSON file '{source_path}'.",
    )


TOOLS = {
    "check_if_file_exists": check_if_file_exists,
    "search_files": search_files,
    "text_writer": text_writer,
    "read_text": read_text,
    "csv_reader": csv_reader,
    "read_json": read_json,
}
