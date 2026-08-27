"""Candidate extraction that keeps practice feedback separate from published knowledge."""
from __future__ import annotations

import json

from pydantic import ValidationError

from app.experts import load_profile, load_runtime
from app.llm import gateway
from app.schemas.domain import KnowledgeCandidateDraft


def extract_candidate(context: dict) -> KnowledgeCandidateDraft:
    """Extract a reviewable lesson from one run and its recorded feedback only."""
    result = context["result"]
    feedback = context["feedback"]
    allowed_evidence_ids = {item["evidence_id"] for item in result.get("evidence", [])}
    runtime = load_runtime(load_profile(context["expert_id"]))
    model_context = {
        "event": result.get("event", {}),
        "grounding": result.get("grounding", []),
        "feedback": feedback,
    }
    try:
        extracted = gateway.structured_generate(
            "knowledge_extraction",
            runtime.knowledge_extraction_prompt,
            json.dumps(model_context, ensure_ascii=False),
            KnowledgeCandidateDraft,
        )
    except ValidationError:
        extracted = None
    if extracted:
        data = extracted.model_dump()
        data["supporting_evidence_ids"] = [
            evidence_id for evidence_id in data["supporting_evidence_ids"] if evidence_id in allowed_evidence_ids
        ]
        return KnowledgeCandidateDraft.model_validate(data)
    return _deterministic_candidate(result, feedback, allowed_evidence_ids)


def _deterministic_candidate(result: dict, feedback: list[dict], allowed_evidence_ids: set[str]) -> KnowledgeCandidateDraft:
    """Create a traceable fallback without claiming that feedback is verified fact."""
    latest_feedback = feedback[-1]
    event_title = result.get("event", {}).get("title", "未命名事件")
    evidence_ids = [
        evidence_id
        for item in result.get("grounding", [])
        for evidence_id in item.get("evidence_ids", [])
        if evidence_id in allowed_evidence_ids
    ]
    return KnowledgeCandidateDraft(
        title=f"实践反馈候选：{event_title}",
        summary=f"反馈结果：{latest_feedback['outcome']}。反馈备注：{latest_feedback['notes']}",
        lessons=[f"待审核经验：{latest_feedback['notes']}"],
        supporting_evidence_ids=list(dict.fromkeys(evidence_ids)),
    )
