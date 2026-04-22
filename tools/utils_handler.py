from runtime.contracts import ToolResult


def reverse_string(input_string):
    """
    Reverse the given string.

    Parameters:
        input_string (str): The string to be reversed.

    Returns:
        ToolResult:
            - data (str): The reversed string formatted as a response.
            - summary (str): Short explanation of the action taken.
            - error (str | None): Always `None` for this utility when successful.
    """
    reversed_string = input_string[::-1]
    response = (
        f"The reversed string is: {reversed_string}\n\n"
        ".Executed using the reverse_string function."
    )
    return ToolResult.ok(
        data=response,
        summary="Reversed the provided string.",
    )


TOOLS = {"reverse_string": reverse_string}
