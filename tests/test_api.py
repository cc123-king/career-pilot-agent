from fastapi.testclient import TestClient

from career_pilot.api import app
from test_parsers import JD, RESUME


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "demo"


def test_analyze_endpoint():
    response = client.post(
        "/api/v1/analyze",
        json={
            "resume_text": RESUME,
            "jd_text": JD,
            "company": "示例公司",
            "role": "AI Agent 开发工程师",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_profile"]["company"] == "示例公司"
    assert payload["match_report"]["overall_score"] >= 0
    assert payload["workflow_trace"]

