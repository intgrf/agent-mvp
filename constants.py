from enum import StrEnum


class NodeName(StrEnum):
    LLM_CALL = "llm_call_node"
    TOOLS = "tool_node"


MESSAGE_TO_USER_TOOL_NAME = "message_to_user"
SPAWN_SUBAGENT_TOOL_NAME = "spawn_subagent"
GET_SKILL_TOOL_NAME = "get_skill"
CREATE_SKILL_TOOL_NAME = "create_skill"

SUBAGENT_EXCLUDED_TOOLS: set[str] = {SPAWN_SUBAGENT_TOOL_NAME}
