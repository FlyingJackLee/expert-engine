import logging
import time

from fastapi import APIRouter, HTTPException

from app.graph.main import expert_graph
from app.runs import get_run_repository
from app.schemas.domain import (AnalysisRequest, ExpertResult, FeedbackInput,
                                FeedbackResult, ManualReviewInput,
                                ManualReviewResult)

router = APIRouter(prefix="/api/v1/expert", tags=["expert-runs"])
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=ExpertResult)
def analyze(request: AnalysisRequest) -> dict:
    """Run expert analysis and persist its result before returning it."""
    started = time.perf_counter()
    # Log only request metadata: event text and user_context may be sensitive.
    logger.info("analysis_requested expert_id=%s event_id=%s", request.expert_id, request.event.event_id or "unspecified")
    try:
        state = expert_graph.invoke({"raw_event": request.event.model_dump(), "expert_id": request.expert_id, "include_internal": request.include_internal, "user_context": request.user_context})
    except Exception:
        logger.exception("analysis_failed expert_id=%s event_id=%s", request.expert_id, request.event.event_id or "unspecified")
        raise
    status = "COMPLETED" if state["final_result"]["review"]["decision"] == "APPROVE" else "PENDING_REVIEW"
    get_run_repository().save(state["run_id"], state["expert_id"], status, state["final_result"])
    logger.info(
        "analysis_completed run_id=%s duration_ms=%d score=%s review=%s evidence_count=%d",
        state["run_id"],
        (time.perf_counter() - started) * 1000,
        state["final_result"]["score"]["opportunity_score"],
        state["final_result"]["review"]["decision"],
        len(state["final_result"]["evidence"]),
    )
    return state["final_result"]


@router.get("/runs/{run_id}", response_model=ExpertResult)
def get_run(run_id: str) -> dict:
    """Return a previously persisted analysis result or a 404 response."""
    result = get_run_repository().get(run_id)
    if result is None:
        logger.info("run_not_found run_id=%s", run_id)
        raise HTTPException(status_code=404, detail="Run not found")
    logger.debug("run_returned run_id=%s", run_id)
    return result


@router.post("/runs/{run_id}/reviews", response_model=ManualReviewResult, status_code=201)
def submit_manual_review(run_id: str, review: ManualReviewInput) -> dict:
    """Store one auditable human decision for an existing analysis run."""
    status = get_run_repository().record_review(run_id, review.decision, review.reviewer_id, review.notes)
    if status is None:
        raise HTTPException(status_code=404, detail="Run not found")
    logger.info("manual_review_recorded run_id=%s decision=%s reviewer_id=%s", run_id, review.decision, review.reviewer_id)
    return {"run_id": run_id, "decision": review.decision, "status": status}


@router.post("/runs/{run_id}/feedback", response_model=FeedbackResult, status_code=201)
def submit_feedback(run_id: str, feedback: FeedbackInput) -> dict:
    """Persist a structured real-world outcome without changing the analysis result."""
    feedback_id = get_run_repository().record_feedback(run_id, feedback.outcome, feedback.notes, feedback.submitted_by)
    if feedback_id is None:
        raise HTTPException(status_code=404, detail="Run not found")
    logger.info("feedback_recorded run_id=%s submitted_by=%s", run_id, feedback.submitted_by)
    return {"run_id": run_id, "feedback_id": feedback_id}
