from fastapi.testclient import TestClient
from interfaces.api import app, get_engine

class FakeEngine:
    def run(self, goal):
        return {"status": "success", "output": f"fake:{goal}", "error": None}

app.dependency_overrides[get_engine] = lambda: FakeEngine()
client = TestClient(app)

resp = client.post("/query", json={"goal": "oi"})
print("status:", resp.status_code)
print("text:", resp.text)
try:
    print("json:", resp.json())
except Exception as e:
    print("json parse error:", e)
