from langgraph.graph import StateGraph, START, END
from app.agents.state import AgentState
from app.agents.nodes.security import security_check
from app.agents.nodes.toon_converter import toon_conversion_node
from app.agents.nodes.parallel_llm import parallel_llm_node  # NEW: Parallel LLM


def create_agent_graph():
    """
    Create the security agent workflow graph.

    Flow:
        START → security_agent → (if blocked) → END
                               → (if passed) → toon_converter (if enabled) → parallel_llm → END
                               → (if passed, no TOON) → parallel_llm → END

    Every query ALWAYS gets 2 parallel LLM calls:
    1. Response generation
    2. Security threat analysis

    This ensures minimum security coverage.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("security_agent", security_check)
    workflow.add_node("toon_converter", toon_conversion_node)
    workflow.add_node("parallel_llm", parallel_llm_node)  # NEW: Always runs

    # Set entry point
    workflow.add_edge(START, "security_agent")

    # Define conditional edges from security_agent
    def route_after_security(state: AgentState):
        """Route based on security check result."""
        if state.get("is_blocked"):
            return END

        # Get sentinel config for TOON feature flag
        sentinel_config = state.get("sentinel_config")

        # If TOON conversion enabled, go there first
        if sentinel_config and sentinel_config.enable_toon_conversion:
            return "toon_converter"

        # Otherwise, go directly to parallel LLM
        return "parallel_llm"

    workflow.add_conditional_edges("security_agent", route_after_security)

    # TOON converter flows to parallel LLM
    workflow.add_edge("toon_converter", "parallel_llm")

    # Parallel LLM always goes to END
    workflow.add_edge("parallel_llm", END)

    return workflow.compile()


agent_graph = create_agent_graph()
