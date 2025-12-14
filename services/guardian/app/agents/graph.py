from langgraph.graph import StateGraph, START, END
from app.agents.state import GuardianState
from app.agents.nodes.content_filter import content_filter_node
from app.agents.nodes.pii_scanner import pii_scanner_node
from app.agents.nodes.toon_decoder import toon_decoder_node

# NEW: Advanced validation nodes
from app.agents.nodes.hallucination_detector import hallucination_detector_node
from app.agents.nodes.citation_verifier import citation_verifier_node
from app.agents.nodes.tone_checker import tone_checker_node
from app.agents.nodes.disclaimer_injector import disclaimer_injector_node
from app.agents.nodes.refusal_detector import refusal_detector_node


def create_guardian_graph():
    """
    Create the Guardian validation workflow with advanced features.

    Flow:
        START → content_filter → (if blocked) → END
                               → (if passed) → pii_scanner → toon_decoder
                               → hallucination_detector → citation_verifier
                               → tone_checker → refusal_detector
                               → disclaimer_injector → END

    Note: Some nodes are conditional based on guardrails config.
    """
    workflow = StateGraph(GuardianState)

    # Add existing nodes
    workflow.add_node("content_filter", content_filter_node)
    workflow.add_node("pii_scanner", pii_scanner_node)
    workflow.add_node("toon_decoder", toon_decoder_node)

    # Add new advanced validation nodes
    workflow.add_node("hallucination_detector", hallucination_detector_node)
    workflow.add_node("citation_verifier", citation_verifier_node)
    workflow.add_node("tone_checker", tone_checker_node)
    workflow.add_node("refusal_detector", refusal_detector_node)
    workflow.add_node("disclaimer_injector", disclaimer_injector_node)

    # Entry point
    workflow.add_edge(START, "content_filter")

    # Conditional routing after content filter
    def route_after_filter(state: GuardianState):
        if state.get("content_blocked"):
            return END
        return "pii_scanner"

    workflow.add_conditional_edges("content_filter", route_after_filter)

    # Sequential flow for all validation nodes
    workflow.add_edge("pii_scanner", "toon_decoder")
    workflow.add_edge("toon_decoder", "hallucination_detector")
    workflow.add_edge("hallucination_detector", "citation_verifier")
    workflow.add_edge("citation_verifier", "tone_checker")
    workflow.add_edge("tone_checker", "refusal_detector")
    workflow.add_edge("refusal_detector", "disclaimer_injector")
    workflow.add_edge("disclaimer_injector", END)

    return workflow.compile()


guardian_graph = create_guardian_graph()
