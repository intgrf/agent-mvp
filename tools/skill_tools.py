from __future__ import annotations

import json

from langchain_core.tools import BaseTool, StructuredTool

from constants import CREATE_SKILL_TOOL_NAME, GET_SKILL_TOOL_NAME
from skill_registry import SkillsRegistry


def _format_skill_md(name: str, description: str, content: str) -> str:
    """Build SKILL.md: frontmatter ``name`` / ``description``, then Markdown body."""
    key = name.strip()
    desc = description.rstrip()
    body = content.lstrip("\n")
    text = f"""---
name: {key}
description: {json.dumps(desc, ensure_ascii=False)}
---
{body}"""
    return text if text.endswith("\n") else text + "\n"


def create_get_skill_tool(registry: SkillsRegistry) -> BaseTool:
    def _run(skill_name: str) -> str:
        full = registry.get_full(skill_name.strip())
        if full is None:
            return (
                f"No skill named {skill_name!r}. "
                f"Known skills: {registry.names or '[]'}."
            )
        return full

    return StructuredTool.from_function(
        func=_run,
        name=GET_SKILL_TOOL_NAME,
        description=(
            "Load the full markdown for a skill (skills/<skill_name>/SKILL.md). "
            "Use when you need complete step-by-step instructions for a composite workflow; "
            "the system prompt only lists short summaries."
        ),
    )


def create_create_skill_tool(registry: SkillsRegistry) -> BaseTool:
    def _run(name: str, description: str, content: str) -> str:
        key = name.strip()
        try:
            registry.create_skill(key, _format_skill_md(key, description, content))
        except ValueError as e:
            return f"Error: {e}"
        return (
            f"Skill {key!r} saved to "
            f"{registry.skills_dir / key / 'SKILL.md'}. "
            "Use `get_skill` to read it back."
        )

    return StructuredTool.from_function(
        func=_run,
        name=CREATE_SKILL_TOOL_NAME,
        description=(
            "Create or overwrite skills/<name>/SKILL.md. "
            "Provide `name` (directory slug), `description` (short summary for the prompt), "
            "and `content` (Markdown body after the frontmatter). "
            "Name must be alphanumeric with _ or - only."
        ),
    )


def create_skill_tools(registry: SkillsRegistry) -> list[BaseTool]:
    return [
        create_get_skill_tool(registry),
        create_create_skill_tool(registry),
    ]
