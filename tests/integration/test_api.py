from fastapi.testclient import TestClient

from interfaces.api import app, get_engine


class FakeEngine:
    def run(self, goal):
        return {"status": "success", "output": f"fake:{goal}", "error": None}


def test_health_endpoint_does_not_require_engine():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_details_uses_engine_dependency_override():
    app.dependency_overrides[get_engine] = lambda: FakeEngine()
    client = TestClient(app)

    try:
        response = client.get("/health/details")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tools"]["count"] == 0
    assert data["memory"]["available"] is False


def test_query_endpoint_uses_dependency_override():
    app.dependency_overrides[get_engine] = lambda: FakeEngine()
    client = TestClient(app)

    try:
        response = client.post("/query", json={"goal": "oi"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "output": "fake:oi",
        "error": None,
    }


def test_query_get_returns_usage_instead_of_method_not_allowed():
    client = TestClient(app)

    response = client.get("/query")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
