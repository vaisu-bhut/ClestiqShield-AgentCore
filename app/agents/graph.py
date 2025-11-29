from langgraph.graph import StateGraph, START, END
from app.agents.state import AgentState
from app.agents.nodes.security import security_check

def create_agent_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("security_agent", security_check)

    # Set entry point
    workflow.add_edge(START, "security_agent")

    # Define conditional edges
    def check_security_result(state: AgentState):
        if state.get("is_blocked"):
            return END
        return END # For now, we end here. Later this will go to "compliance_agent"

    workflow.add_conditional_edges(
        "security_agent",
        check_security_result
    )

    return workflow.compile()

agent_graph = create_agent_graph()
