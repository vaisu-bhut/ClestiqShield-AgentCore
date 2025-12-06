from langgraph.graph import StateGraph, START, END
from app.agents.state import AgentState
from app.agents.nodes.security import security_check
from app.agents.nodes.toon_converter import toon_conversion_node
from app.agents.nodes.llm_responder import llm_responder_node
from app.core.config import get_settings

def create_agent_graph():
    """
    Create the security agent workflow graph.
    
    Flow:
        START → security_agent → (if blocked) → END
                              → (if passed) → toon_converter → llm_responder → END
    """
    workflow = StateGraph(AgentState)
    settings = get_settings()

    # Add nodes
    workflow.add_node("security_agent", security_check)
    
    if settings.TOON_CONVERSION_ENABLED:
        workflow.add_node("toon_converter", toon_conversion_node)
    
    if settings.LLM_FORWARD_ENABLED:
        workflow.add_node("llm_responder", llm_responder_node)

    # Set entry point
    workflow.add_edge(START, "security_agent")

    # Define conditional edges from security_agent
    def route_after_security(state: AgentState):
        """Route based on security check result."""
        if state.get("is_blocked"):
            return END
        
        # If passed, go to TOON converter (if enabled) or LLM responder (if enabled)
        settings = get_settings()
        if settings.TOON_CONVERSION_ENABLED:
            return "toon_converter"
        elif settings.LLM_FORWARD_ENABLED:
            return "llm_responder"
        return END

    workflow.add_conditional_edges(
        "security_agent",
        route_after_security
    )
    
    # Add edges for TOON converter
    if settings.TOON_CONVERSION_ENABLED:
        if settings.LLM_FORWARD_ENABLED:
            workflow.add_edge("toon_converter", "llm_responder")
        else:
            workflow.add_edge("toon_converter", END)
    
    # Add edge for LLM responder to END
    if settings.LLM_FORWARD_ENABLED:
        workflow.add_edge("llm_responder", END)

    return workflow.compile()

agent_graph = create_agent_graph()

