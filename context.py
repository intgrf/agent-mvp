from __future__ import annotations

from langchain_core.messages import BaseMessage, SystemMessage

from skill_registry import SkillsRegistry


class PromptBuilder:
    """Builds the full message list (system prompt + history) for an LLM call.

    Subclass and override ``_build_system_content`` to inject dynamic context
    (RAG chunks, user profile, etc.) into the system prompt.
    """

    def __init__(
        self,
        system_prompt: str,
        skills_registry: SkillsRegistry | None = None,
    ) -> None:
        self._system_prompt = system_prompt
        self._skills_registry = skills_registry

    def build_messages(self, history: list[BaseMessage]) -> list[BaseMessage]:
        return [SystemMessage(content=self._build_system_content())] + list(history)

    def _build_system_content(self) -> str:
        parts = [self._system_prompt.rstrip()]
        if self._skills_registry is not None:
            parts.append("\n## Skills (brief)\n")
            parts.append(self._skills_registry.get_prompt_section())
        return "\n".join(parts)
