"""Unit contracts for cross-entrypoint graph event visibility."""
from app.observability import get_graph_events, record_graph_event


def test_graph_events_are_queryable_by_run_id():
    """Every graph trigger can expose the same node event envelope to viewers."""
    record_graph_event("trace-test", "NODE_COMPLETED", "research", duration_ms=12)
    events = get_graph_events("trace-test")
    assert events[-1]["node"] == "research"
    assert events[-1]["duration_ms"] == 12
