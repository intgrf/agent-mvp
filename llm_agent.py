from __future__ import annotations

from pathlib import Path

from langchain_core.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from nodes import AgentFactory
from skill_registry import SkillsRegistry
from tools.registry import ToolsRegistry
from tools.message_to_user import message_to_user
from tools.skill_tools import create_skill_tools
from tools.spawn_subagent import create_spawn_subagent_tool
from utils import extract_response


class LLMAgent:
    """High-level facade that wires up the registry, factory, and graph.

    Usage::

        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o")
        agent = LLMAgent(llm)

        # (optional) register extra tools before setup:
        # agent.registry.register(my_custom_tool)

        agent.setup()
        print(agent.invoke("What is 2 + 2?"))
    """

    def __init__(
        self,
        llm: BaseChatModel,
        registry: ToolsRegistry | None = None,
        skills_registry: SkillsRegistry | None = None,
        skills_dir: Path | None = None,
    ) -> None:
        self._llm = llm
        self.registry = registry or ToolsRegistry()
        if skills_registry is not None:
            self.skills_registry = skills_registry
        elif skills_dir is not None:
            self.skills_registry = SkillsRegistry(skills_dir)
        else:
            self.skills_registry = SkillsRegistry()
        self.factory = AgentFactory(llm, self.registry, self.skills_registry)
        self._graph: CompiledStateGraph | None = None

    def setup(self) -> LLMAgent:
        """Register built-in tools and compile the main-agent graph.

        Call this **after** you have registered any custom tools in
        ``self.registry`` so they are included in the compiled graph.
        """
        self.registry.register(message_to_user)

        for tool in create_skill_tools(self.skills_registry):
            self.registry.register(tool)

        spawn_tool = create_spawn_subagent_tool(self.factory)
        self.registry.register(spawn_tool)

        self._graph = self.factory.create_main_agent()
        return self

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("Agent not initialised — call .setup() first.")
        return self._graph

    def invoke(self, user_message: str) -> str:
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            {"recursion_limit": 50},
        )
        return extract_response(result["messages"]) or "Agent did not produce a response."
