from __future__ import annotations

import json
import logging
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError

from app.experts import load_profile, load_runtime, resolve_expert_id
from app.knowledge.retrieval import retrieve
from app.knowledge.rerank import rerank_evidence
from app.knowledge.grounding import validate_citation
from app.matching import evidence_score
from app.config import MAX_RESEARCH_RETRIES
from app.llm import gateway
from app.scoring.engine import calculate_score
from app.schemas.domain import (CandidateSelection, EventAnalysis, NeedInference, Opportunity,
                                ResearchPlan, ReviewResult)


logger = logging.getLogger(__name__)


def initialize(state: dict) -> dict:
    """Create stable run identifiers and initialize retry state."""
    run_id = state.get("run_id") or str(uuid4())
    return {"run_id": run_id, "thread_id": run_id, "status": "RUNNING", "retry_count": 0}


def route_expert(state: dict) -> dict:
    """Resolve the requested expert through the profile registry."""
    expert_id = resolve_expert_id(state.get("expert_id", "AUTO"))
    return {"expert_id": expert_id, "expert_profile": load_profile(expert_id)}


def analyze_event(state: dict) -> dict:
    """Derive a conservative event structure before any downstream reasoning."""
    event = state["raw_event"]
    runtime = load_runtime(state["expert_profile"])
    try:
        llm_result = gateway.structured_generate(
            "event_analyzer",
            runtime.event_analyzer_prompt,
            json.dumps(event, ensure_ascii=False),
            EventAnalysis,
        )
    except ValidationError:
        # Event classification can safely use the deterministic fallback. This is
        # logged rather than hidden so an incompatible gateway can be corrected.
        logger.warning("event_analyzer returned JSON that failed local schema validation; using rule fallback")
        llm_result = None
    if llm_result:
        # Event analysis is an interpretation of supplied text, not a fact claim.
        # All later organization and project assertions still require retrieval.
        return {"event_analysis": llm_result.model_dump()}

    # Deterministic fallback keeps local development and regression tests runnable
    # when no approved model gateway is configured.
    text = f'{event["title"]} {event["content"]}'
    topics = [topic for topic, keywords in runtime.topic_keywords.items() if any(word.lower() in text.lower() for word in keywords)]
    topics = topics or [runtime.default_topic]
    procurement = any(word in text for word in ("采购", "招标", "中标"))
    project = any(word in text for word in ("项目", "建设", "实施", "启动"))
    policy = any(word in text for word in ("政策", "通知", "方案", "意见", "要求"))
    tasks = ["建设监测预警与协同处置能力"] if "城市生命线" in topics else ["开展数字化建设需求研判"]
    return {"event_analysis": {"event_type": "PROCUREMENT" if procurement else "POLICY" if policy else "PROJECT", "topics": topics, "tasks": tasks, "signals": {"policy_strength": 0.9 if policy else 0.45, "project_signal": 0.85 if project else 0.3, "budget_signal": 0.7 if "预算" in text else 0.2, "procurement_signal": 0.95 if procurement else 0.1}}}


def plan_research(state: dict) -> dict:
    """Plan questions before retrieval, keeping research separate from answers."""
    try:
        runtime = load_runtime(state["expert_profile"])
        llm_result = gateway.structured_generate(
            "research_planner",
            runtime.research_planner_prompt,
            json.dumps(state["event_analysis"], ensure_ascii=False),
            ResearchPlan,
        )
    except ValidationError:
        # Research questions have the same safe, deterministic fallback; answers
        # are still produced only by the controlled knowledge retrieval layer.
        logger.warning("research_planner returned JSON that failed local schema validation; using rule fallback")
        llm_result = None
    if llm_result:
        return {"research_plan": llm_result.model_dump()}

    topic = state["event_analysis"]["topics"][0]
    return {"research_plan": {"questions": [f"{topic} 的政策建设任务", f"{topic} 的主管单位和处室职责", f"{topic} 的相似项目与公司能力"]}}


def research(state: dict) -> dict:
    """Retrieve policy, responsibility, capability and case evidence by role."""
    topics = state["event_analysis"]["topics"]
    # Include compact, machine-matchable event context in addition to natural
    # language research questions. This keeps retrieval deterministic even when
    # Chinese source text has no whitespace segmentation.
    query = " ".join([*state["research_plan"]["questions"], *topics, state["raw_event"]["title"]])
    city = state["raw_event"].get("city") or state.get("user_context", {}).get("city")
    evidence = []
    profile_id = state.get("expert_profile", {}).get("id")
    retrieval_scope = {"expert_profile_id": profile_id} if profile_id else {}
    # Policy/industry, organization, capability and case evidence serve different
    # inference steps. Keep them separate here so a strong vendor case cannot
    # accidentally substitute for a local authority responsibility record.
    evidence.extend(retrieve(query, {"POLICY", "INDUSTRY"}, city=city, topics=topics, **retrieval_scope))
    evidence.extend(retrieve(query, {"RESPONSIBILITY"}, city=city, **retrieval_scope))
    evidence.extend(retrieve(query, {"CAPABILITY"}, topics=topics, **retrieval_scope))
    evidence.extend(retrieve(query, {"CASE"}, topics=topics, **retrieval_scope))
    # Published expert lessons are supplementary internal context, never a
    # substitute for policy or responsibility evidence in deterministic matching.
    evidence.extend(retrieve(query, {"INTERNAL"}, **retrieval_scope))
    deduplicated = {item["evidence_id"]: item for item in evidence}
    ranked_evidence = rerank_evidence(query, list(deduplicated.values()))
    history = list(state.get("research_history", []))
    history.append({"attempt": state.get("retry_count", 0), "question_count": len(state["research_plan"]["questions"]), "city": city, "evidence_count": len(ranked_evidence)})
    return {"evidence": ranked_evidence, "research_city": city, "research_history": history}


def extract_historical_knowledge(state: dict) -> dict:
    """Separate published internal lessons from primary evidence for transparent use."""
    history = [item for item in state["evidence"] if str(item["type"]) == "INTERNAL"]
    return {"historical_knowledge": history}


def refine_research(state: dict) -> dict:
    """Turn reviewer gaps into additional retrieval questions without asserting facts."""
    existing_questions = list(state["research_plan"]["questions"])
    issue_questions = [f"补充可核验的{issue['type']}证据：{issue['message']}" for issue in state["review_result"]["issues"]]
    questions = list(dict.fromkeys([*existing_questions, *issue_questions]))
    return {"research_plan": {"questions": questions}, "retry_count": state.get("retry_count", 0) + 1}


def route_after_review(state: dict) -> str:
    """Bounded retry routing; never retry an approved decision indefinitely."""
    if state["review_result"]["decision"] == "RESEARCH_MORE" and state.get("retry_count", 0) < MAX_RESEARCH_RETRIES:
        return "refine_research"
    return "finalize"


def infer_needs(state: dict) -> dict:
    """Map tasks to needs; this intentionally does not match products directly."""
    evidence = [item for item in state["evidence"] if str(item["type"]) in {"POLICY", "INDUSTRY"}]
    evidence_ids = [item["evidence_id"] for item in evidence]
    topic = state["event_analysis"]["topics"][0]
    task = state["event_analysis"]["tasks"][0]
    maturity = "PROCUREMENT" if state["event_analysis"]["signals"]["procurement_signal"] > 0.8 else "PROJECT" if state["event_analysis"]["signals"]["project_signal"] > 0.8 else "EXPLICIT"
    runtime = load_runtime(state["expert_profile"])
    context = {"event_analysis": state["event_analysis"], "evidence": [{"evidence_id": item["evidence_id"], "title": item["title"], "content": item["content"]} for item in evidence]}
    try:
        inferred = gateway.structured_generate("need_reasoning", runtime.need_reasoning_prompt, json.dumps(context, ensure_ascii=False), NeedInference)
    except ValidationError:
        logger.warning("need_reasoning returned JSON that failed local schema validation; using rule fallback")
        inferred = None
    if inferred:
        valid_ids = set(evidence_ids)
        needs = []
        for need in inferred.needs:
            cleaned_ids = [evidence_id for evidence_id in need.evidence_ids if evidence_id in valid_ids]
            data = need.model_dump()
            data["evidence_ids"] = cleaned_ids
            if not cleaned_ids:
                data["confidence"] = min(data["confidence"], 0.45)
            needs.append(data)
        return {"needs": needs}
    stable_id = f"need_{sha256(f'{topic}|{task}'.encode()).hexdigest()[:12]}"
    return {"needs": [{"id": stable_id, "name": f"{topic}数字化建设需求", "category": "PLATFORM", "description": task, "maturity": maturity, "confidence": 0.86 if evidence_ids else 0.45, "derived_from_tasks": state["event_analysis"]["tasks"], "evidence_ids": evidence_ids}]}


def _metadata(item: dict) -> dict:
    """Return normalized optional metadata from one evidence item."""
    return item.get("metadata") or {}


def match_organizations(state: dict) -> dict:
    """Rank organizations strictly from responsibility-card evidence."""
    candidates: dict[str, dict] = {}
    for item in state["evidence"]:
        metadata = _metadata(item)
        organization_id = metadata.get("organization_id")
        if str(item["type"]) != "RESPONSIBILITY" or not organization_id:
            continue
        candidate = candidates.setdefault(organization_id, {"organization_id": organization_id, "name": metadata.get("organization_name") or item.get("organization") or item["title"], "evidence_ids": [], "scores": []})
        candidate["evidence_ids"].append(item["evidence_id"])
        candidate["scores"].append(evidence_score(item, city=state.get("research_city"), topics=state["event_analysis"]["topics"]))
    matches = [{"organization_id": item["organization_id"], "name": item["name"], "score": round(sum(item["scores"]) / len(item["scores"]), 2), "reason": "按职责证据的相关度、来源可靠度及城市/主题上下文排序。", "evidence_ids": item["evidence_ids"]} for item in candidates.values()]
    if not matches:
        matches = [{"organization_id": "UNKNOWN", "name": "UNKNOWN", "score": 0.0, "reason": "未检索到可核验的组织职责证据。", "evidence_ids": []}]
    return {"organizations": sorted(matches, key=lambda item: (-item["score"], item["organization_id"]))}


def match_departments(state: dict) -> dict:
    """Rank department candidates only when their responsibility evidence exists."""
    candidates = []
    for item in state["evidence"]:
        metadata = _metadata(item)
        if str(item["type"]) != "RESPONSIBILITY" or not metadata.get("department_id"):
            continue
        candidates.append({"department_id": metadata["department_id"], "name": metadata.get("department_name") or item["title"], "organization_id": metadata.get("organization_id", "UNKNOWN"), "role": "LEAD", "score": evidence_score(item, city=state.get("research_city"), topics=state["event_analysis"]["topics"]), "status": "CONFIRMED", "evidence_ids": [item["evidence_id"]]})
    if not candidates:
        candidates = [{"department_id": None, "name": None, "organization_id": state["organizations"][0]["organization_id"], "role": None, "score": 0.0, "status": "UNKNOWN", "evidence_ids": []}]
    return {"departments": sorted(candidates, key=lambda item: (-item["score"], item["department_id"] or ""))}


def match_capabilities(state: dict) -> dict:
    """Rank company capabilities and attach the strongest related cases."""
    ranked_cases = sorted(
        ((evidence_score(item, topics=state["event_analysis"]["topics"]), _metadata(item).get("case_id") or item["source_id"]) for item in state["evidence"] if str(item["type"]) == "CASE"),
        key=lambda item: (-item[0], item[1]),
    )
    case_ids = [case_id for _, case_id in ranked_cases]
    matches = []
    for item in state["evidence"]:
        metadata = _metadata(item)
        if str(item["type"]) != "CAPABILITY" or not metadata.get("capability_id"):
            continue
        matches.append({"need_id": state["needs"][0]["id"], "capability_id": metadata["capability_id"], "name": item["title"], "score": evidence_score(item, topics=state["event_analysis"]["topics"]), "reason": "按能力证据的相关度、来源可靠度及主题上下文排序。", "case_ids": metadata.get("case_ids") or case_ids, "evidence_ids": [item["evidence_id"]]})
    return {"capabilities": sorted(matches, key=lambda item: (-item["score"], item["capability_id"]))}


def reason_about_candidates(state: dict) -> dict:
    """Optionally narrow evidence-backed candidates without allowing new entities."""
    runtime = load_runtime(state["expert_profile"])
    groups = {
        "organization_ids": ("organizations", "organization_id"),
        "department_ids": ("departments", "department_id"),
        "capability_ids": ("capabilities", "capability_id"),
    }
    context = {
        "event_analysis": state["event_analysis"],
        "candidates": {
            field: [
                {identifier: item.get(identifier), "name": item.get("name"), "score": item.get("score"), "evidence_ids": item.get("evidence_ids", [])}
                for item in state.get(state_key, [])
            ]
            for field, (state_key, identifier) in groups.items()
        },
    }
    try:
        selection = gateway.structured_generate("candidate_reasoning", runtime.candidate_reasoning_prompt, json.dumps(context, ensure_ascii=False), CandidateSelection)
    except ValidationError:
        logger.warning("candidate_reasoning returned JSON that failed local schema validation; using rule fallback")
        selection = None
    if not selection:
        return {"candidate_reasoning": {"organization_ids": [], "department_ids": [], "capability_ids": [], "rationale": "未配置候选复核模型，保留确定性证据排序。", "mode": "RULE_FALLBACK"}}
    output = {"candidate_reasoning": {"mode": "LLM_CONSTRAINED", "rationale": selection.rationale}}
    for field, (state_key, identifier) in groups.items():
        candidates = state.get(state_key, [])
        available = {str(item[identifier]) for item in candidates if item.get(identifier) is not None}
        selected = [item_id for item_id in getattr(selection, field) if item_id in available]
        output["candidate_reasoning"][field] = selected
        if selected:
            positions = {item_id: index for index, item_id in enumerate(selected)}
            output[state_key] = sorted(
                [item for item in candidates if str(item.get(identifier)) in positions],
                key=lambda item: positions[str(item[identifier])],
            )
    return output


def ground_evidence(state: dict) -> dict:
    """Create an explicit claim-to-evidence map without inventing claim support."""
    evidence_by_id = {item["evidence_id"]: item for item in state["evidence"]}
    groups = (
        ("NEED", "needs", "id"),
        ("ORGANIZATION", "organizations", "organization_id"),
        ("DEPARTMENT", "departments", "department_id"),
        ("CAPABILITY", "capabilities", "capability_id"),
    )
    grounding = []
    for claim_type, state_key, id_key in groups:
        for item in state.get(state_key, []):
            claim_id = item.get(id_key) or "UNKNOWN"
            evidence_ids = list(dict.fromkeys(item.get("evidence_ids", [])))
            citations = [{"evidence_id": evidence_id, "source_id": evidence_by_id[evidence_id]["source_id"], "title": evidence_by_id[evidence_id]["title"], "source_url": evidence_by_id[evidence_id].get("source_url"), "chunk_index": evidence_by_id[evidence_id].get("chunk_index"), "validation": validate_citation(evidence_by_id[evidence_id])} for evidence_id in evidence_ids if evidence_id in evidence_by_id]
            grounded = bool(evidence_ids) and all(item["validation"]["complete"] for item in citations)
            grounding.append({"claim_type": claim_type, "claim_id": str(claim_id), "evidence_ids": evidence_ids, "citations": citations, "status": "GROUNDED" if grounded else "UNGROUNDED"})
    return {"grounding": grounding}


def synthesize_opportunity(state: dict) -> dict:
    """Produce a constrained commercial summary from already grounded matches."""
    need = state["needs"][0]
    org = state["organizations"][0]
    runtime = load_runtime(state["expert_profile"])
    synthesis_context = {"event_analysis": state["event_analysis"], "needs": state["needs"], "organizations": state["organizations"], "departments": state["departments"], "capabilities": state["capabilities"], "grounding": state["grounding"], "historical_knowledge": [{"evidence_id": item["evidence_id"], "title": item["title"], "content": item["content"]} for item in state.get("historical_knowledge", [])]}
    try:
        llm_result = gateway.structured_generate("opportunity_synthesis", runtime.opportunity_synthesis_prompt, json.dumps(synthesis_context, ensure_ascii=False), Opportunity)
    except ValidationError:
        logger.warning("opportunity_synthesis returned JSON that failed local schema validation; using rule fallback")
        llm_result = None
    if llm_result:
        return {"opportunity": llm_result.model_dump()}
    history_note = "已检索到历史内部经验，仍需以当前原始证据核验其适用性。" if state.get("historical_knowledge") else ""
    return {"opportunity": {"summary": f"建议围绕{need['name']}开展商机跟进。", "stage": "EARLY_OPPORTUNITY", "reasoning_summary": f"事件信号指向{need['name']}，{org['name']}是优先研判对象。", "risks": ["当前为种子知识验证结果，需补充目标地区的正式文件和实际部门职责。", *([history_note] if history_note else [])], "recommended_actions": ["核验当地实施方案及采购计划。", "与候选牵头处室确认建设范围、预算和时间表。"]}}


def score_result(state: dict) -> dict:
    """Apply the versioned deterministic opportunity-scoring model."""
    return {"score": calculate_score(state)}


def review(state: dict) -> dict:
    """Combine non-overridable rule checks with an optional independent critic."""
    issues = []
    evidence_types = {str(item["type"]) for item in state.get("evidence", [])}
    if "POLICY" not in evidence_types:
        issues.append({"type": "MISSING_POLICY_EVIDENCE", "message": "缺乏政策直接证据。"})
    if not state["departments"][0]["evidence_ids"]:
        issues.append({"type": "MISSING_DEPARTMENT_EVIDENCE", "message": "缺乏可靠处室职责依据。"})
    grounding_targets = set()
    for item in state.get("grounding", []):
        if item.get("status") == "UNGROUNDED":
            grounding_targets.add(item.get("claim_type", "EVIDENCE"))
            invalid = [citation.get("validation", {}).get("missing", []) for citation in item.get("citations", []) if not citation.get("validation", {}).get("complete", True)]
            detail = "；".join("、".join(fields) for fields in invalid if fields) or "引用缺少可核验来源"
            issues.append({"type": "INVALID_CITATION", "message": f"{item.get('claim_type', 'EVIDENCE')} 引用未通过完整性校验：{detail}。"})
    runtime = load_runtime(state["expert_profile"])
    critic_context = {"grounding": state["grounding"], "evidence_types": sorted(evidence_types), "score": state["score"]}
    try:
        critic_result = gateway.structured_generate("evidence_critic", runtime.evidence_critic_prompt, json.dumps(critic_context, ensure_ascii=False), ReviewResult)
    except ValidationError:
        logger.warning("evidence_critic returned JSON that failed local schema validation; ignoring critic output")
        critic_result = None
    if critic_result:
        known = {(issue["type"], issue["message"]) for issue in issues}
        for issue in critic_result.issues:
            item = issue.model_dump()
            if (item["type"], item["message"]) not in known:
                issues.append(item)
                known.add((item["type"], item["message"]))
    decision = "APPROVE" if not issues and (not critic_result or critic_result.decision == "APPROVE") else "RESEARCH_MORE"
    retry_targets = sorted(grounding_targets) or (["ORGANIZATION"] if issues else [])
    return {"review_result": {"decision": decision, "confidence": state["score"]["confidence"], "issues": issues, "retry_targets": retry_targets}}


def finalize(state: dict) -> dict:
    """Assemble the public expert response from the completed graph state."""
    profile = state["expert_profile"]
    result = {"run_id": state["run_id"], "expert": {"id": profile["id"], "version": profile["version"]}, "event": state["raw_event"], "opportunity": state["opportunity"], "score": state["score"], "needs": state["needs"], "organizations": state["organizations"], "departments": state["departments"], "capabilities": state["capabilities"], "candidate_reasoning": state["candidate_reasoning"], "evidence": state["evidence"], "historical_knowledge": state.get("historical_knowledge", []), "grounding": state["grounding"], "review": state["review_result"]}
    return {"status": "COMPLETED", "final_result": result}
