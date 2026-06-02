from fastapi.testclient import TestClient

from interfaces import api


class FakeEngine:
    def run(self, goal):
        return {"status": "success", "output": f"Echo: {goal}"}


def test_health_endpoint():
    client = TestClient(api.app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_query_with_fake_engine():
    # Inject fake engine to avoid external LLM dependency
    api.set_engine_for_tests(FakeEngine())
    client = TestClient(api.app)

    res = client.post("/query", json={"goal": "Diga oi"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "Echo: Diga oi" in data.get("output", "")
