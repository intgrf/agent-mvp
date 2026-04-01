from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from constants import NodeName, MESSAGE_TO_USER_TOOL_NAME, SUBAGENT_EXCLUDED_TOOLS
from state import AgentState
from context import PromptBuilder
from prompts import MAIN_AGENT_SYSTEM_PROMPT, SUBAGENT_SYSTEM_PROMPT
from tools.registry import ToolsRegistry


class AgentFactory:
    """Creates compiled LangGraph agents with a shared architecture.

    Both main agent and subagents follow the same graph topology::

        START ─► llm_call_node ─┬─► tool_node ─┬─► END  (message_to_user called)
                   ▲             │      │        │
                   │  (text only)│      │        │
                   └─────────────┘      └────────┘  (other tools → loop back)
    """

    def __init__(self, llm: BaseChatModel, registry: ToolsRegistry) -> None:
        self._llm = llm
        self.registry = registry

    def create_main_agent(self) -> CompiledStateGraph:
        return self._build_graph(
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            tools=self.registry.get_all(),
        )

    def create_subagent(
        self,
        tools: list[BaseTool] | None = None,
    ) -> CompiledStateGraph:
        if tools is None:
            tools = self.registry.get_all_except(SUBAGENT_EXCLUDED_TOOLS)
        return self._build_graph(
            system_prompt=SUBAGENT_SYSTEM_PROMPT,
            tools=tools,
        )

    # ── private ───────────────────────────────────────────────────

    def _build_graph(
        self,
        system_prompt: str,
        tools: list[BaseTool],
    ) -> CompiledStateGraph:
        prompt_builder = PromptBuilder(system_prompt)
        llm_with_tools = self._llm.bind_tools(tools)

        def llm_call_node(state: AgentState) -> dict:
            messages = prompt_builder.build_messages(state["messages"])
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}

        def route_after_llm(state: AgentState) -> str:
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                return NodeName.TOOLS
            return NodeName.LLM_CALL

        def route_after_tools(state: AgentState) -> str:
            for msg in reversed(state["messages"]):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc["name"] == MESSAGE_TO_USER_TOOL_NAME:
                            return END
                    break
            return NodeName.LLM_CALL

        tool_node = ToolNode(tools)

        workflow = StateGraph(AgentState)
        workflow.add_node(NodeName.LLM_CALL, llm_call_node)
        workflow.add_node(NodeName.TOOLS, tool_node)

        workflow.add_edge(START, NodeName.LLM_CALL)
        workflow.add_conditional_edges(NodeName.LLM_CALL, route_after_llm)
        workflow.add_conditional_edges(NodeName.TOOLS, route_after_tools)

        return workflow.compile()
