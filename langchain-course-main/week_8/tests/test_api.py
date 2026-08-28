from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_planner_agent_validation():
    # Verifies that missing required fields properly trigger a 422 error response
    response = client.post("/run-planner-agent", json={})
    assert response.status_code == 422

def test_chat_route_structure():
    # Verifies the chat router responds appropriately to a basic user payload
    response = client.post("/chat", json={"message": "Testing the agent loop"})
    assert response.status_code in [200, 422]