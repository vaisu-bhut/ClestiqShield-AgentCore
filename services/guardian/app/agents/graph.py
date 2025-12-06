from langgraph.graph import StateGraph, START, END
from app.agents.state import GuardianState
from app.agents.nodes.content_filter import content_filter_node
from app.agents.nodes.pii_scanner import pii_scanner_node
from app.agents.nodes.toon_decoder import toon_decoder_node


def create_guardian_graph():
    """
    Create the Guardian validation workflow.

    Flow:
        START → content_filter → (if blocked) → END
                              → (if passed) → pii_scanner → toon_decoder → END
    """
    workflow = StateGraph(GuardianState)

    # Add nodes
    workflow.add_node("content_filter", content_filter_node)
    workflow.add_node("pii_scanner", pii_scanner_node)
    workflow.add_node("toon_decoder", toon_decoder_node)

    # Entry point
    workflow.add_edge(START, "content_filter")

    # Conditional routing after content filter
    def route_after_filter(state: GuardianState):
        if state.get("content_blocked"):
            return END
        return "pii_scanner"

    workflow.add_conditional_edges("content_filter", route_after_filter)

    # Sequential flow for remaining nodes
    workflow.add_edge("pii_scanner", "toon_decoder")
    workflow.add_edge("toon_decoder", END)

    return workflow.compile()


guardian_graph = create_guardian_graph()
