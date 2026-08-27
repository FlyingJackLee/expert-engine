from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(StrEnum):
    """Categories used to constrain retrieval and evidence review."""
    POLICY = "POLICY"
    INDUSTRY = "INDUSTRY"
    RESPONSIBILITY = "RESPONSIBILITY"
    CASE = "CASE"
    INTERNAL = "INTERNAL"
    CAPABILITY = "CAPABILITY"


class NeedMaturity(StrEnum):
    """Lifecycle stage inferred for a potential customer need."""
    CONCEPT = "CONCEPT"
    POTENTIAL = "POTENTIAL"
    EXPLICIT = "EXPLICIT"
    PROJECT = "PROJECT"
    PROCUREMENT = "PROCUREMENT"


class DepartmentRole(StrEnum):
    """Relationship of a department to a candidate opportunity."""
    LEAD = "LEAD"
    COORDINATE = "COORDINATE"
    TECH_SUPPORT = "TECH_SUPPORT"
    DATA_PROVIDER = "DATA_PROVIDER"
    IMPLEMENTATION = "IMPLEMENTATION"
    SUPERVISION = "SUPERVISION"


class EventInput(BaseModel):
    """Normalized event supplied to the analysis API."""
    title: str = Field(min_length=3, max_length=300)
    content: str = Field(min_length=10, max_length=20_000)
    source_url: str | None = None
    event_id: str | None = None
    city: str | None = Field(default=None, min_length=2, max_length=50)


class AnalysisRequest(BaseModel):
    """Top-level request selecting an expert and analysis context."""
    event: EventInput
    expert_id: str = "AUTO"
    include_internal: bool = False
    user_context: dict[str, Any] = Field(default_factory=dict)


class EventSignals(BaseModel):
    """Structured strength signals extracted from the submitted event."""
    policy_strength: float = Field(ge=0, le=1)
    project_signal: float = Field(ge=0, le=1)
    budget_signal: float = Field(ge=0, le=1)
    procurement_signal: float = Field(ge=0, le=1)


class EventAnalysis(BaseModel):
    """Structured event understanding; it is not evidence of external facts."""

    event_type: str
    topics: list[str] = Field(min_length=1, max_length=8)
    tasks: list[str] = Field(default_factory=list, max_length=10)
    signals: EventSignals


class ResearchPlan(BaseModel):
    """Questions drive retrieval; the planner must not answer them itself."""

    questions: list[str] = Field(min_length=1, max_length=8)


class KnowledgeDocumentInput(BaseModel):
    """Validated document payload accepted by the knowledge ingestion API."""
    document_id: str = Field(min_length=3, max_length=200)
    source_type: EvidenceType
    title: str = Field(min_length=3, max_length=500)
    chunks: list[str] = Field(min_length=1)
    source_url: str | None = None
    organization: str | None = None
    reliability: float = Field(ge=0, le=1)
    effective_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """A retrievable source excerpt used to ground a conclusion."""
    evidence_id: str
    type: EvidenceType
    source_id: str
    title: str
    content: str
    organization: str | None = None
    source_url: str | None = None
    relevance: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    effective_date: str | None = None
    chunk_index: int | None = None


class Need(BaseModel):
    """Potential customer need derived from event tasks and evidence."""
    id: str
    name: str
    category: str
    description: str
    maturity: NeedMaturity
    confidence: float = Field(ge=0, le=1)
    derived_from_tasks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class NeedInference(BaseModel):
    """Schema-constrained set of needs inferred from grounded event context."""

    needs: list[Need] = Field(min_length=1, max_length=5)


class OrganizationMatch(BaseModel):
    """Evidence-ranked organization candidate for the opportunity."""
    organization_id: str
    name: str
    score: float = Field(ge=0, le=1)
    reason: str
    evidence_ids: list[str]


class DepartmentMatch(BaseModel):
    """Evidence-ranked department candidate within an organization."""
    department_id: str | None = None
    name: str | None = None
    organization_id: str
    role: DepartmentRole | None = None
    score: float = Field(default=0, ge=0, le=1)
    status: str = "CONFIRMED"
    evidence_ids: list[str] = Field(default_factory=list)


class CapabilityMatch(BaseModel):
    """Company capability matched to a need using supporting evidence."""
    need_id: str
    capability_id: str
    name: str
    score: float = Field(ge=0, le=1)
    reason: str
    case_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Opportunity(BaseModel):
    """Structured commercial assessment assembled from grounded matches."""
    summary: str
    stage: str
    reasoning_summary: str
    risks: list[str]
    recommended_actions: list[str]


class Score(BaseModel):
    """Deterministic opportunity score with its component factors."""
    opportunity_score: int = Field(ge=0, le=100)
    level: str
    confidence: float = Field(ge=0, le=1)
    factors: dict[str, float]


class ReviewIssue(BaseModel):
    """A single evidence or quality gap found during review."""
    type: str
    message: str


class ReviewResult(BaseModel):
    """Automated reviewer decision and any required follow-up targets."""
    decision: str
    confidence: float = Field(ge=0, le=1)
    issues: list[ReviewIssue] = Field(default_factory=list)
    retry_targets: list[str] = Field(default_factory=list)


class GroundingItem(BaseModel):
    """Explicit mapping from one conclusion claim to its evidence IDs."""
    claim_type: str
    claim_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    citations: list["Citation"] = Field(default_factory=list)
    status: str


class Citation(BaseModel):
    """Resolvable source location attached to one grounded conclusion."""

    evidence_id: str
    source_id: str
    title: str
    source_url: str | None = None
    chunk_index: int | None = None


class ManualReviewInput(BaseModel):
    """Human decision and audit context submitted for a saved analysis run."""
    decision: str = Field(pattern="^(APPROVE|REJECT|REQUEST_RESEARCH)$")
    reviewer_id: str = Field(min_length=2, max_length=100)
    notes: str = Field(min_length=2, max_length=4_000)


class ManualReviewResult(BaseModel):
    """Status returned after a human review decision is recorded."""
    run_id: str
    decision: str
    status: str


class FeedbackInput(BaseModel):
    """Structured outcome note submitted after a real-world follow-up action."""

    outcome: str = Field(min_length=2, max_length=100)
    notes: str = Field(min_length=2, max_length=4_000)
    submitted_by: str = Field(min_length=2, max_length=100)


class FeedbackResult(BaseModel):
    """Confirmation returned after one feedback record is persisted."""

    run_id: str
    feedback_id: str


class KnowledgeCandidateDraft(BaseModel):
    """Extracted experience content before it is assigned an approval identity."""

    title: str = Field(min_length=3, max_length=300)
    summary: str = Field(min_length=3, max_length=4_000)
    lessons: list[str] = Field(min_length=1, max_length=10)
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class KnowledgeCandidateResult(KnowledgeCandidateDraft):
    """Persisted candidate returned for an expert approval workflow."""

    candidate_id: str
    run_id: str
    status: str
    source_feedback_ids: list[str] = Field(min_length=1)


class CandidateReviewInput(BaseModel):
    """Expert approval decision and auditable rationale for one knowledge candidate."""

    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    reviewer_id: str = Field(min_length=2, max_length=100)
    notes: str = Field(min_length=2, max_length=4_000)


class CandidateReviewResult(BaseModel):
    """Candidate state returned after an expert records an approval decision."""

    candidate_id: str
    decision: str
    status: str


class KnowledgePublicationResult(BaseModel):
    """Published knowledge identity, version and source candidate provenance."""

    publication_id: str
    candidate_id: str
    document_id: str
    expert_id: str
    version: int = Field(ge=1)
    status: str


class KnowledgeRetirementInput(BaseModel):
    """Expert-authored reason for retiring a published knowledge version."""

    reviewer_id: str = Field(min_length=2, max_length=100)
    notes: str = Field(min_length=2, max_length=4_000)


class KnowledgeRetirementResult(BaseModel):
    """Publication state returned after a version is safely retired."""

    publication_id: str
    status: str


class ExpertResult(BaseModel):
    """Full evidence-grounded response returned by an expert analysis run."""
    run_id: str
    expert: dict[str, str]
    event: dict[str, Any]
    opportunity: Opportunity
    score: Score
    needs: list[Need]
    organizations: list[OrganizationMatch]
    departments: list[DepartmentMatch]
    capabilities: list[CapabilityMatch]
    evidence: list[Evidence]
    grounding: list[GroundingItem]
    review: ReviewResult
