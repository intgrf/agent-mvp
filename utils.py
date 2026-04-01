from langchain_core.messages import AIMessage, BaseMessage

from constants import MESSAGE_TO_USER_TOOL_NAME


def extract_response(messages: list[BaseMessage]) -> str | None:
    """Walk messages in reverse and return the ``message_to_user`` argument
    from the most recent AI tool-call, or *None* if not found."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call["name"] == MESSAGE_TO_USER_TOOL_NAME:
                    return tool_call["args"]["message"]
            break
    return None
