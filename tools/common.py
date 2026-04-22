def talk_to_user(input_text):
    """
    Answer to user by displaying text. 
    Good to give information back to user and to print information that should be use later.
    You can also use this function to ask user additional questions

    Parameters:
    input_text (str): The text to be echoed back.

    Returns:
    str: The conversational response.
    """

    response = f"Agent said: {input_text}"
    # print(f"DEBUG: response: {response}")
    return response
