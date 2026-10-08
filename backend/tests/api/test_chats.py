from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_routes_reject_requests_without_a_bearer_token() -> None:
    chat_id = "00000000-0000-0000-0000-000000000001"
    requests = [
        ("GET", "/chats", None),
        ("POST", "/chats", {"title": "Research"}),
        ("GET", f"/chats/{chat_id}/messages", None),
        ("POST", f"/chats/{chat_id}/messages", {"content": "Compare revenue."}),
        (
            "POST",
            f"/chats/{chat_id}/messages/stream",
            {"content": "Compare revenue."},
        ),
    ]

    with TestClient(app) as client:
        responses = [
            client.request(method, path, json=body) for method, path, body in requests
        ]

    assert [response.status_code for response in responses] == [401] * len(requests)
