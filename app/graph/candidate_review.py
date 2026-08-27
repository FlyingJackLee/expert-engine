"""LangGraph HITL workflow for pausing a knowledge candidate for expert approval."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.graph.checkpoints import build_hitl_checkpointer
from app.runs import get_run_repository
from app.schemas.domain import CandidateReviewInput


class CandidateReviewState(TypedDict, total=False):
    """Serializable state held while a candidate waits for an expert decision."""

    candidate_id: str
    candidate: dict[str, Any]
    review_input: dict[str, Any]
    review_status: str


def wait_for_expert(state: CandidateReviewState) -> dict:
    """Pause the workflow and expose only the candidate context required for review."""
    review_input = interrupt(
        {
            "type": "KNOWLEDGE_CANDIDATE_REVIEW",
            "candidate_id": state["candidate_id"],
            "candidate": state["candidate"],
        }
    )
    return {"review_input": review_input}


def persist_expert_decision(state: CandidateReviewState) -> dict:
    """Validate the resumed human input before recording the candidate decision."""
    review = CandidateReviewInput.model_validate(state["review_input"])
    status = get_run_repository().record_candidate_review(
        state["candidate_id"], review.decision, review.reviewer_id, review.notes
    )
    if status is None:
        raise ValueError("Knowledge candidate no longer exists")
    if status == "ALREADY_REVIEWED":
        raise ValueError("Knowledge candidate has already been reviewed")
    return {"review_status": status}


def _config(candidate_id: str) -> dict:
    """Use the candidate ID as a stable HITL thread identity within this process."""
    return {"configurable": {"thread_id": f"knowledge-candidate:{candidate_id}"}}


def begin_candidate_review(candidate: dict) -> None:
    """Start and intentionally pause a review workflow after candidate persistence."""
    candidate_review_graph.invoke(
        {"candidate_id": candidate["candidate_id"], "candidate": candidate},
        _config(candidate["candidate_id"]),
    )


def resume_candidate_review(candidate_id: str, review: CandidateReviewInput) -> str:
    """Resume a paused HITL thread and return its persisted candidate status."""
    state = candidate_review_graph.invoke(Command(resume=review.model_dump()), _config(candidate_id))
    return state["review_status"]


def build_candidate_review_graph():
    """Compile the interrupt-based candidate approval workflow with a checkpointer."""
    builder = StateGraph(CandidateReviewState)
    builder.add_node("wait_for_expert", wait_for_expert)
    builder.add_node("persist_expert_decision", persist_expert_decision)
    builder.add_edge(START, "wait_for_expert")
    builder.add_edge("wait_for_expert", "persist_expert_decision")
    builder.add_edge("persist_expert_decision", END)
    return builder.compile(checkpointer=build_hitl_checkpointer())


candidate_review_graph = build_candidate_review_graph()
