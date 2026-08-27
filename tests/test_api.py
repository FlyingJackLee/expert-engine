from fastapi.testclient import TestClient

from app.main import app


def test_analysis_returns_evidence_grounded_result():
    response = TestClient(app).post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    assert response.status_code == 200
    result = response.json()
    assert result["expert"]["id"] == "housing_digitalization"
    assert result["needs"][0]["evidence_ids"]
    assert result["departments"][0]["status"] == "CONFIRMED"
    assert all(item["status"] == "GROUNDED" for item in result["grounding"])
    assert result["grounding"][0]["citations"][0]["source_id"]


def test_analysis_accepts_a_city_for_local_evidence_filtering():
    response = TestClient(app).post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。", "city": "重庆"}})
    assert response.status_code == 200
    assert response.json()["event"]["city"] == "重庆"


def test_analysis_result_can_be_loaded_by_run_id():
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    assert created.status_code == 200
    fetched = client.get(f"/api/v1/expert/runs/{created.json()['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == created.json()["run_id"]


def test_manual_review_is_audited_against_an_existing_run():
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    response = client.post(
        f"/api/v1/expert/runs/{created.json()['run_id']}/reviews",
        json={"decision": "APPROVE", "reviewer_id": "business_reviewer_01", "notes": "证据与当前研判一致。"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "COMPLETED"


def test_feedback_can_be_recorded_for_an_existing_run():
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    response = client.post(f"/api/v1/expert/runs/{created.json()['run_id']}/feedback", json={"outcome": "已完成首次需求沟通", "notes": "客户确认仍需补充实施范围。", "submitted_by": "sales_owner_01"})
    assert response.status_code == 201
    assert response.json()["feedback_id"]


def test_feedback_can_be_extracted_to_an_unpublished_knowledge_candidate():
    """Candidates preserve feedback provenance and are not published automatically."""
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    run_id = created.json()["run_id"]
    feedback = client.post(f"/api/v1/expert/runs/{run_id}/feedback", json={"outcome": "完成需求沟通", "notes": "客户要求先明确协同范围后再安排下一次沟通。", "submitted_by": "sales_owner_01"})
    assert feedback.status_code == 201
    response = client.post(f"/api/v1/expert/runs/{run_id}/knowledge-candidates")
    assert response.status_code == 201
    candidate = response.json()
    assert candidate["status"] == "PENDING_APPROVAL"
    assert candidate["source_feedback_ids"] == [feedback.json()["feedback_id"]]
    assert client.get(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}").json()["candidate_id"] == candidate["candidate_id"]


def test_knowledge_candidate_requires_recorded_feedback():
    """Candidate extraction refuses to infer experience from analysis output alone."""
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    response = client.post(f"/api/v1/expert/runs/{created.json()['run_id']}/knowledge-candidates")
    assert response.status_code == 409


def test_expert_can_approve_a_pending_knowledge_candidate_once():
    """Expert review changes only the candidate lifecycle state and leaves it queryable."""
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    run_id = created.json()["run_id"]
    client.post(f"/api/v1/expert/runs/{run_id}/feedback", json={"outcome": "完成需求沟通", "notes": "客户要求先明确协同范围后再安排下一次沟通。", "submitted_by": "sales_owner_01"})
    candidate = client.post(f"/api/v1/expert/runs/{run_id}/knowledge-candidates").json()
    review = client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/reviews", json={"decision": "APPROVE", "reviewer_id": "domain_expert_01", "notes": "经验表述审慎，可进入正式知识发布流程。"})
    assert review.status_code == 201
    assert review.json()["status"] == "APPROVED"
    assert client.get(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}").json()["status"] == "APPROVED"
    repeat = client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/reviews", json={"decision": "REJECT", "reviewer_id": "domain_expert_02", "notes": "不应覆盖第一位专家的审核结果。"})
    assert repeat.status_code == 409


def test_only_an_approved_candidate_can_be_published_as_expert_knowledge():
    """Publishing promotes reviewed experience once and rejects pending candidates."""
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    run_id = created.json()["run_id"]
    client.post(f"/api/v1/expert/runs/{run_id}/feedback", json={"outcome": "完成需求沟通", "notes": "客户要求先明确协同范围后再安排下一次沟通。", "submitted_by": "sales_owner_01"})
    candidate = client.post(f"/api/v1/expert/runs/{run_id}/knowledge-candidates").json()
    assert client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/publish").status_code == 409
    approved = client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/reviews", json={"decision": "APPROVE", "reviewer_id": "domain_expert_01", "notes": "可发布为经过审核的内部经验。"})
    assert approved.status_code == 201
    published = client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/publish")
    assert published.status_code == 201
    assert published.json()["status"] == "PUBLISHED"
    assert published.json()["version"] >= 1
    assert client.get(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}").json()["status"] == "PUBLISHED"


def test_published_knowledge_can_be_retired_without_deleting_its_history():
    """Retirement prevents a second governance action while retaining the publication ID."""
    client = TestClient(app)
    created = client.post("/api/v1/expert/analyze", json={"event": {"title": "城市生命线建设实施方案", "content": "某市发布城市生命线安全工程建设实施方案，启动燃气、供水和桥梁监测预警平台建设。"}})
    run_id = created.json()["run_id"]
    client.post(f"/api/v1/expert/runs/{run_id}/feedback", json={"outcome": "完成需求沟通", "notes": "客户要求先明确协同范围后再安排下一次沟通。", "submitted_by": "sales_owner_01"})
    candidate = client.post(f"/api/v1/expert/runs/{run_id}/knowledge-candidates").json()
    client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/reviews", json={"decision": "APPROVE", "reviewer_id": "domain_expert_01", "notes": "可发布为经过审核的内部经验。"})
    publication = client.post(f"/api/v1/expert/knowledge-candidates/{candidate['candidate_id']}/publish").json()
    retired = client.post(f"/api/v1/expert/knowledge-publications/{publication['publication_id']}/retire", json={"reviewer_id": "domain_expert_01", "notes": "后续实践表明该经验需停用并重新验证。"})
    assert retired.status_code == 201
    assert retired.json()["status"] == "RETIRED"
    assert client.post(f"/api/v1/expert/knowledge-publications/{publication['publication_id']}/retire", json={"reviewer_id": "domain_expert_02", "notes": "不能重复退役同一知识版本。"}).status_code == 409
