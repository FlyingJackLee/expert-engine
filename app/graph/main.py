from langgraph.graph import END, START, StateGraph

from app.graph.state import ExpertState
from app.observability import graph_node
from app.nodes.core import (analyze_event, extract_historical_knowledge, finalize, infer_needs, initialize,
                            ground_evidence,
                            match_capabilities, match_departments,
                            match_organizations, plan_research, research,
                            refine_research, review, route_after_review, route_expert, score_result,
                            synthesize_opportunity)


def build_graph():
    """Assemble the generic expert workflow and its bounded retry route."""
    builder = StateGraph(ExpertState)
    for name, node in [("initialize", initialize), ("route_expert", route_expert), ("analyze_event", analyze_event), ("plan_research", plan_research), ("research", research), ("extract_historical_knowledge", extract_historical_knowledge), ("refine_research", refine_research), ("infer_needs", infer_needs), ("match_organizations", match_organizations), ("match_departments", match_departments), ("match_capabilities", match_capabilities), ("ground_evidence", ground_evidence), ("synthesize", synthesize_opportunity), ("score", score_result), ("review", review), ("finalize", finalize)]:
        builder.add_node(name, graph_node(name, node))
    builder.add_edge(START, "initialize")
    for source, target in [("initialize", "route_expert"), ("route_expert", "analyze_event"), ("analyze_event", "plan_research"), ("plan_research", "research"), ("research", "extract_historical_knowledge"), ("extract_historical_knowledge", "infer_needs"), ("refine_research", "research"), ("infer_needs", "match_organizations"), ("match_organizations", "match_departments"), ("match_departments", "match_capabilities"), ("match_capabilities", "ground_evidence"), ("ground_evidence", "synthesize"), ("synthesize", "score"), ("score", "review"), ("finalize", END)]:
        builder.add_edge(source, target)
    builder.add_conditional_edges("review", route_after_review, {"refine_research": "refine_research", "finalize": "finalize"})
    return builder.compile()


expert_graph = build_graph()
