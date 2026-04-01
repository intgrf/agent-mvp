from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, StructuredTool

from constants import (
    MESSAGE_TO_USER_TOOL_NAME,
    SPAWN_SUBAGENT_TOOL_NAME,
    SUBAGENT_EXCLUDED_TOOLS,
)

if TYPE_CHECKING:
    from nodes import AgentFactory


def _extract_subagent_response(messages: list) -> str | None:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == MESSAGE_TO_USER_TOOL_NAME:
                    return tc["args"]["message"]
            break
    return None


def create_spawn_subagent_tool(factory: AgentFactory) -> BaseTool:
    """Produce a ``spawn_subagent`` tool whose description dynamically
    lists the tools the caller can delegate to a subagent."""

    registry = factory.registry
    default_subagent_tools = registry.get_all_except(SUBAGENT_EXCLUDED_TOOLS)
    selectable_names = [t.name for t in default_subagent_tools]

    def _run(task: str, tool_names: Optional[list[str]] = None) -> str:
        if tool_names is not None:
            tools = registry.get_by_names(tool_names)
            if MESSAGE_TO_USER_TOOL_NAME not in {t.name for t in tools}:
                tools.append(registry.get(MESSAGE_TO_USER_TOOL_NAME))
        else:
            tools = None

        agent = factory.create_subagent(tools=tools)
        result = agent.invoke(
            {"messages": [HumanMessage(content=task)]},
            {"recursion_limit": 25},
        )
        response = _extract_subagent_response(result["messages"])
        return response or "Subagent completed but did not produce a response."

    description = (
        "Spawn an independent subagent to handle a specific task. "
        "The subagent runs with its own message history and cannot spawn further subagents. "
        f"Available tool_names for the subagent: {selectable_names}. "
        f"`{MESSAGE_TO_USER_TOOL_NAME}` is always included automatically. "
        "Omit tool_names to give the subagent every available tool."
    )

    return StructuredTool.from_function(
        func=_run,
        name=SPAWN_SUBAGENT_TOOL_NAME,
        description=description,
    )
