from langchain_core.messages import BaseMessage, SystemMessage


class PromptBuilder:
    """Builds the full message list (system prompt + history) for an LLM call.

    Subclass and override ``_build_system_content`` to inject dynamic context
    (RAG chunks, user profile, etc.) into the system prompt.
    """

    def __init__(self, system_prompt: str):
        self._system_prompt = system_prompt

    def build_messages(self, history: list[BaseMessage]) -> list[BaseMessage]:
        return [SystemMessage(content=self._build_system_content())] + list(history)

    def _build_system_content(self) -> str:
        return self._system_prompt
