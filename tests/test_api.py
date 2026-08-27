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
