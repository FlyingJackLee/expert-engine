from typing import Any, TypedDict


class ExpertState(TypedDict, total=False):
    """Shared, serializable state passed between LangGraph analysis nodes."""
    run_id: str
    thread_id: str
    status: str
    user_context: dict[str, Any]
    expert_id: str
    expert_profile: dict[str, Any]
    raw_event: dict[str, Any]
    include_internal: bool
    event_analysis: dict[str, Any]
    research_plan: dict[str, Any]
    research_city: str | None
    research_history: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    historical_knowledge: list[dict[str, Any]]
    needs: list[dict[str, Any]]
    organizations: list[dict[str, Any]]
    departments: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]
    candidate_reasoning: dict[str, Any]
    grounding: list[dict[str, Any]]
    opportunity: dict[str, Any]
    score: dict[str, Any]
    review_result: dict[str, Any]
    retry_count: int
    final_result: dict[str, Any]
