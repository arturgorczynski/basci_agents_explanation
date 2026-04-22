from datetime import datetime
import os
from pathlib import Path
from typing import Iterable
import pandas as pd
import glob
import json


def check_if_file_exists(filename):
    """
    Search current location and child directories for a specific file.
    Proper to find a location of a given file.
    USE ONLY IF FILENAME PROVIDED

    Parameters:
    filename (str): The name of the file to search for.

    Returns:
    str: The full path to the file if found, or a 'file not found' message if the file does not exist.
    """
    # Get the current working directory
    current_directory = os.getcwd()
    
    # Walk through the current directory and all subdirectories
    for dirpath, dirnames, filenames in os.walk(current_directory):
        if filename in filenames:
            return os.path.join(dirpath, filename)

    # If file is not found, return a not found message
    return f"File '{filename}' not found in the current directory or any child directories."


def search_files(pattern: str, root: str | Path | None = None) -> list[str]:
    """
    Return every file matching *pattern* starting at *root* (default: the directory
    that contains this source file) and recursing through all sub‑directories.

    Parameters
    ----------
    pattern : str
        A Unix‑style glob such as '*.txt' or 'A*.py'.
    root : str | pathlib.Path | None, optional
        The directory to start from.  If omitted, the directory that holds
        this module is used.

    Returns
    -------
    list[str]
        Absolute paths of all matching files.
    """
    root_path = Path(root).resolve() if root else Path(__file__).resolve().parent
    return [str(p) for p in root_path.rglob(pattern)]

def text_writer(message=None, filename='results.txt'):
    """
    Write or append a message to a text file. If no message is provided, a default message will be used.
    
    Parameters:
    filename (str): The name of the text file. If none then default - results.txt will be used.
    message (str): The message to be written or appended. If None, file will not be written
    
    Returns:
    None
    """
    if message is None:
        return None

    # Get the current date and time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepare the message to write/append
    message_to_write = f"{current_time} - {message}\n"

    # Check if the file already exists
    if os.path.exists(filename):
        # Append the message if the file exists
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(message_to_write)
    else:
        # Create a new file and write the message
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(message_to_write)

    print(f"Message has been {'appended to' if os.path.exists(filename) else 'written to'} the file: {filename}")


def read_text(filename='results.txt'):
    """
    Read and return content of a text file.

    Parameters:
    filename (str): The name of the text file to read. Defaults to 'results.txt'.

    Returns:
    str: The contents of the file as a string. If the file does not exist, returns None.
    """
    if not os.path.exists(filename):
        print(f"The file '{filename}' does not exist.")
        return None

    # Read the contents of the file
    with open(filename, 'r', encoding='utf-8') as file:
        contents = file.read()

    print(f"Contents of the file '{filename}' have been read successfully.")
    return contents



def csv_reader(filepath='data.csv', **kwargs):
    """
    Read a CSV file into a Pandas DataFrame. Additional parameters can be passed to handle
    specific needs like custom delimiters, missing values, or column types.
    Use only if file name and its location are known.
    
    Parameters:
    filepath (str): The path to the CSV file. Defaults to 'data.csv'.
    **kwargs: Additional keyword arguments to be passed to pandas.read_csv() function.
    
    Returns:
    pd.DataFrame: The content of the CSV file as a Pandas DataFrame. If the file does not exist,
                  prints an error message and returns None.
    """
    try:
        # Attempt to read the CSV file using the provided arguments
        df = pd.read_csv(filepath, **kwargs)
        print(f"CSV file '{filepath}' has been read successfully into a DataFrame.")
        return df
    except FileNotFoundError:
        print(f"The file '{filepath}' does not exist.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None
    
def read_json(filename='data.json'):
    """
    Read and return content of a JSON file as a dictionary.

    Parameters:
    filename (str): The name of the JSON file to read. Defaults to 'data.json'.

    Returns:
    dict: The contents of the JSON file as a dictionary. If the file does not exist, returns None.
    """
    if not os.path.exists(filename):
        print(f"The file '{filename}' does not exist.")
        return None

    # Read and parse the JSON file
    with open(filename, 'r', encoding='utf-8') as file:
        contents = json.load(file)

    print(f"Contents of the file '{filename}' have been read successfully.")
    return contents
