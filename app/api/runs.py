import logging
import time

from fastapi import APIRouter, HTTPException

from app.graph.main import expert_graph
from app.observability import get_graph_events
from app.evaluation.capability import capability_report
from app.graph.candidate_review import (begin_candidate_review,
                                        resume_candidate_review)
from app.knowledge.candidates import extract_candidate
from app.runs import get_run_repository
from app.schemas.domain import (AnalysisRequest, ExpertResult, FeedbackInput,
                                FeedbackResult, CandidateReviewInput, CandidateReviewResult,
                                KnowledgeCandidateResult, KnowledgePublicationResult,
                                KnowledgeRetirementInput, KnowledgeRetirementResult,
                                KnowledgeRestoreInput, KnowledgeRestoreResult,
                                ManualReviewInput,
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


@router.get("/runs")
def list_runs(limit: int = 50) -> dict:
    """List recent run IDs so operators can discover traces automatically."""
    return {"runs": get_run_repository().list_runs(limit)}


@router.get("/profiles/{expert_id}/capability-report")
def get_capability_report(expert_id: str) -> dict:
    """Return standard Expert ability, knowledge readiness and missing-domain metrics."""
    return capability_report(expert_id)


@router.get("/runs/{run_id}", response_model=ExpertResult)
def get_run(run_id: str) -> dict:
    """Return a previously persisted analysis result or a 404 response."""
    result = get_run_repository().get(run_id)
    if result is None:
        logger.info("run_not_found run_id=%s", run_id)
        raise HTTPException(status_code=404, detail="Run not found")
    logger.debug("run_returned run_id=%s", run_id)
    return result


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str) -> dict:
    """Return live-safe node events for any graph invocation in this process."""
    return {"run_id": run_id, "events": get_graph_events(run_id)}


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


@router.post("/runs/{run_id}/knowledge-candidates", response_model=KnowledgeCandidateResult, status_code=201)
def create_knowledge_candidate(run_id: str) -> dict:
    """Extract an unpublished experience candidate from recorded run feedback."""
    repository = get_run_repository()
    context = repository.candidate_context(run_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not context["feedback"]:
        raise HTTPException(status_code=409, detail="At least one feedback record is required")
    draft = extract_candidate(context)
    feedback_ids = [item["feedback_id"] for item in context["feedback"]]
    candidate_id = repository.save_candidate(run_id, context["expert_id"], draft.model_dump(), feedback_ids)
    if candidate_id is None:
        raise HTTPException(status_code=404, detail="Run not found")
    logger.info("knowledge_candidate_created candidate_id=%s run_id=%s", candidate_id, run_id)
    candidate = {"candidate_id": candidate_id, "run_id": run_id, "status": "PENDING_APPROVAL", "source_feedback_ids": feedback_ids, **draft.model_dump()}
    begin_candidate_review(candidate)
    return candidate


@router.get("/knowledge-candidates/{candidate_id}", response_model=KnowledgeCandidateResult)
def get_knowledge_candidate(candidate_id: str) -> dict:
    """Return an unpublished knowledge candidate without adding it to retrieval."""
    candidate = get_run_repository().get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Knowledge candidate not found")
    return {**candidate["content"], "candidate_id": candidate["candidate_id"], "run_id": candidate["run_id"], "status": candidate["status"], "source_feedback_ids": candidate["source_feedback_ids"]}


@router.post("/knowledge-candidates/{candidate_id}/reviews", response_model=CandidateReviewResult, status_code=201)
def submit_candidate_review(candidate_id: str, review: CandidateReviewInput) -> dict:
    """Resume the paused HITL workflow with an expert's candidate decision."""
    candidate = get_run_repository().get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Knowledge candidate not found")
    if candidate["status"] != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail="Knowledge candidate has already been reviewed")
    try:
        status = resume_candidate_review(candidate_id, review)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    logger.info("knowledge_candidate_reviewed candidate_id=%s decision=%s reviewer_id=%s", candidate_id, review.decision, review.reviewer_id)
    return {"candidate_id": candidate_id, "decision": review.decision, "status": status}


@router.post("/knowledge-candidates/{candidate_id}/publish", response_model=KnowledgePublicationResult, status_code=201)
def publish_knowledge_candidate(candidate_id: str) -> dict:
    """Publish one expert-approved candidate as a versioned internal knowledge document."""
    publication = get_run_repository().publish_candidate(candidate_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Knowledge candidate not found")
    if publication["status"] != "PUBLISHED":
        raise HTTPException(status_code=409, detail="Only approved knowledge candidates can be published")
    logger.info("knowledge_candidate_published candidate_id=%s document_id=%s version=%s", candidate_id, publication["document_id"], publication["version"])
    return publication


@router.post("/knowledge-publications/{publication_id}/retire", response_model=KnowledgeRetirementResult, status_code=201)
def retire_knowledge_publication(publication_id: str, retirement: KnowledgeRetirementInput) -> dict:
    """Safely retire a published version without deleting its source or audit trail."""
    status = get_run_repository().retire_publication(publication_id, retirement.reviewer_id, retirement.notes)
    if status is None:
        raise HTTPException(status_code=404, detail="Knowledge publication not found")
    if status == "ALREADY_RETIRED":
        raise HTTPException(status_code=409, detail="Knowledge publication is not active")
    logger.info("knowledge_publication_retired publication_id=%s reviewer_id=%s", publication_id, retirement.reviewer_id)
    return {"publication_id": publication_id, "status": status}


@router.post("/knowledge-publications/{publication_id}/restore", response_model=KnowledgeRestoreResult, status_code=201)
def restore_knowledge_publication(publication_id: str, restore: KnowledgeRestoreInput) -> dict:
    """Restore a retired version for internal retrieval after renewed expert review."""
    status = get_run_repository().restore_publication(publication_id, restore.reviewer_id, restore.notes)
    if status is None:
        raise HTTPException(status_code=404, detail="Knowledge publication not found")
    if status == "NOT_RETIRED":
        raise HTTPException(status_code=409, detail="Knowledge publication is not retired")
    logger.info("knowledge_publication_restored publication_id=%s reviewer_id=%s", publication_id, restore.reviewer_id)
    return {"publication_id": publication_id, "status": status}
