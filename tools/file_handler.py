from datetime import datetime
import json
import os
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency fallback
    pd = None

from runtime.contracts import ToolResult


def check_if_file_exists(filename):
    """
    Search current location and child directories for a specific file.
    Proper to find a location of a given file.
    USE ONLY IF FILENAME PROVIDED

    Parameters:
        filename (str): The name of the file to search for.

    Returns:
        ToolResult:
            - data (str): Full path to the file if found.
            - summary (str): Short explanation of the search result.
            - error (str | None): Failure reason if the file does not exist.
    """
    current_directory = os.getcwd()
    for dirpath, _, filenames in os.walk(current_directory):
        if filename in filenames:
            full_path = os.path.join(dirpath, filename)
            return ToolResult.ok(
                data=full_path,
                summary=f"Found file '{filename}' at '{full_path}'.",
            )

    return ToolResult.failure(
        f"File '{filename}' not found in the current directory or child directories.",
        summary=f"Could not find file '{filename}'.",
    )


def search_files(pattern: str, root: str | Path | None = None) -> ToolResult:
    """
    Return every file matching *pattern* starting at *root* and recurse through
    all child directories.

    Parameters:
        pattern (str): A Unix-style glob such as '*.txt' or 'A*.py'.
        root (str | pathlib.Path | None): Directory to start from. If omitted,
            current working directory is used.

    Returns:
        ToolResult:
            - data (list[str]): Absolute paths of all matching files.
            - summary (str): Short explanation of how many matches were found.
            - error (str | None): Present only if the search fails unexpectedly.
    """
    root_path = Path(root).resolve() if root else Path.cwd()
    matches = [str(path) for path in root_path.rglob(pattern)]
    return ToolResult.ok(
        data=matches,
        summary=f"Found {len(matches)} file(s) matching pattern '{pattern}'.",
    )


def text_writer(message=None, filename="results.txt"):
    """
    Write or append a message to a text file. If no message is provided,
    file will not be written.

    Parameters:
        filename (str): Name of the text file. If omitted then `results.txt` is used.
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

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message_to_write = f"{current_time} - {message}\n"
    file_exists = os.path.exists(filename)
    mode = "a" if file_exists else "w"

    with open(filename, mode, encoding="utf-8") as file:
        file.write(message_to_write)

    action = "Appended" if file_exists else "Created"
    return ToolResult.ok(
        data=filename,
        summary=f"{action} text file '{filename}'.",
    )


def read_text(filename="results.txt"):
    """
    Read and return content of a text file.

    Parameters:
        filename (str): Name of the text file to read. Defaults to `results.txt`.

    Returns:
        ToolResult:
            - data (str): Contents of the file as a string.
            - summary (str): Short explanation of the read result.
            - error (str | None): Failure reason if the file does not exist.
    """
    if not os.path.exists(filename):
        return ToolResult.failure(
            f"The file '{filename}' does not exist.",
            summary=f"Could not read text file '{filename}'.",
        )

    with open(filename, "r", encoding="utf-8") as file:
        contents = file.read()

    return ToolResult.ok(
        data=contents,
        summary=f"Read text file '{filename}'.",
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
        dataframe = pd.read_csv(filepath, **kwargs)
        return ToolResult.ok(
            data=dataframe,
            summary=f"Read CSV file '{filepath}'.",
        )
    except FileNotFoundError:
        return ToolResult.failure(
            f"The file '{filepath}' does not exist.",
            summary=f"Could not read CSV file '{filepath}'.",
        )
    except Exception as exc:
        return ToolResult.failure(
            f"An error occurred while reading '{filepath}': {exc}",
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
    if not os.path.exists(filename):
        return ToolResult.failure(
            f"The file '{filename}' does not exist.",
            summary=f"Could not read JSON file '{filename}'.",
        )

    with open(filename, "r", encoding="utf-8") as file:
        contents = json.load(file)

    return ToolResult.ok(
        data=contents,
        summary=f"Read JSON file '{filename}'.",
    )


TOOLS = {
    "check_if_file_exists": check_if_file_exists,
    "search_files": search_files,
    "text_writer": text_writer,
    "read_text": read_text,
    "csv_reader": csv_reader,
    "read_json": read_json,
}
