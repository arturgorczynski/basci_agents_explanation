def write_python_code(code, filename='generated_script.py'):
    """
    Writes the provided code into a Python file.

    Parameters:
    code (str): The code to write into the file.
    filename (str): The name of the file to create. Default is 'generated_script.py'.

    Returns:
    str: A message indicating that the file has been created.
    """
    # Ensure that escape sequences (like \n) are properly interpreted
    code = code.encode().decode('unicode_escape')
    
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(code)
    
    print(f"Code has been written to {filename}")



def run_python_script(filename):
    """
    Executes a Python script specified by the filename using the Python executable from a local .venv if it exists.

    Parameters:
    filename (str): The path to the Python script file to execute.

    Returns:
    int: The exit code of the executed script. Zero indicates success.
    """
    import subprocess
    import os

    print(f'>>>>>> EXECUTING {filename} <<<<<<<')
    
    # Check if the file exists
    if not os.path.isfile(filename):
        print(f"Error: The file '{filename}' does not exist.")
        return -1

    try:
        # Get the absolute path of the script
        script_path = os.path.abspath(filename)

        # Check if there is a local .venv directory
        venv_python = os.path.join('.venv', 'bin', 'python')  # For Linux/macOS
        if not os.path.exists(venv_python):  # Check for Windows paths
            venv_python = os.path.join('.venv', 'Scripts', 'python.exe')

        # Use the .venv Python executable if it exists, otherwise default to system Python
        python_executable = venv_python if os.path.exists(venv_python) else os.path.abspath(sys.executable)

        command = [python_executable, script_path]

        result = subprocess.run(command, check=True)

        print(f"Script '{filename}' executed successfully.")
        return result.returncode

    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing '{filename}': {e}")
        return e.returncode

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return -1
