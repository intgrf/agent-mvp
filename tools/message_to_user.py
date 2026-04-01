from langchain_core.tools import tool


@tool
def message_to_user(message: str) -> str:
    """Send a response message to the user.

    Always use this tool when you want to deliver your final answer
    or any intermediate communication to the user.
    """
    return message
