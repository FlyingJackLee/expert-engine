"""Unit contracts for reusable golden-sample evaluation metrics."""
from evaluation.metrics import summarize_outcomes


def test_summarize_outcomes_reports_pass_rate_and_history_coverage():
    """The evaluator exposes stable aggregate metrics for acceptance reports."""
    report = summarize_outcomes([
        {"id": "a", "passed": True, "checks": {"historical_knowledge": True}},
        {"id": "b", "passed": False, "checks": {"historical_knowledge": False}},
    ])
    assert report["total"] == 2
    assert report["passed"] == 1
    assert report["historical_knowledge_coverage"] == 0.5
