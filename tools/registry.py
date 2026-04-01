from langchain_core.tools import BaseTool


class ToolsRegistry:
    """Central catalogue of tools available to agents.

    Supports registration, lookup by name, and filtered retrieval
    (e.g. excluding certain tools for subagents).
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ── registration ──────────────────────────────────────────────

    def register(self, tool: BaseTool) -> "ToolsRegistry":
        """Register a tool. Returns *self* so calls can be chained."""
        self._tools[tool.name] = tool
        return self

    # ── retrieval ─────────────────────────────────────────────────

    def get(self, name: str) -> BaseTool:
        return self._tools[name]

    def get_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_by_names(self, names: list[str]) -> list[BaseTool]:
        return [self._tools[n] for n in names if n in self._tools]

    def get_all_except(self, exclude: set[str]) -> list[BaseTool]:
        return [t for n, t in self._tools.items() if n not in exclude]

    # ── introspection ─────────────────────────────────────────────

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get_tools_description(
        self,
        exclude: set[str] | None = None,
    ) -> str:
        """Human-readable list of ``name: description`` for prompts."""
        exclude = exclude or set()
        return "\n".join(
            f"- {name}: {t.description}"
            for name, t in self._tools.items()
            if name not in exclude
        )

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolsRegistry(tools={self.names})"
