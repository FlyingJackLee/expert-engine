"""Direct contract tests for the candidate-review LangGraph interrupt boundary."""
from app.graph.candidate_review import build_candidate_review_graph


def test_candidate_review_graph_pauses_for_human_input():
    """Creating a candidate review thread must surface an interrupt before a decision."""
    graph = build_candidate_review_graph()
    state = graph.invoke(
        {"candidate_id": "candidate_test_01", "candidate": {"candidate_id": "candidate_test_01", "title": "待审核经验"}},
        {"configurable": {"thread_id": "candidate-test-thread"}},
    )
    assert "__interrupt__" in state
    assert state["__interrupt__"][0].value["type"] == "KNOWLEDGE_CANDIDATE_REVIEW"
