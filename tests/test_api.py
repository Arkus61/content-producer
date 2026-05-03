import os
import pytest
import jwt
import uuid
from datetime import datetime, timezone, timedelta

os.environ["SUPABASE_JWT_SECRET"] = "test-secret-key-32bytes-long-key-superlong!!!!"
os.environ["DEBUG"] = "true"

from fastapi.testclient import TestClient
from src.api import app


@pytest.fixture
def client():
    return TestClient(app, base_url="http://testserver")


def _mock_supabase_token(email="admin@test.ru", role="operator"):
    payload = {
        "sub": str(uuid.uuid4()),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_operator_info(client):
    resp = client.get("/api/info/operator")
    assert resp.status_code == 200
    data = resp.json()
    assert "operator_name" in data
    assert "dpo_email" in data


def test_auth_me(client):
    token = _mock_supabase_token()
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "email" in data


def test_create_expert_requires_consent(client):
    token = _mock_supabase_token()
    headers = {"Authorization": f"Bearer {token}"}
    # Without consent — fail
    r = client.post("/api/experts", headers=headers, json={"name": "Иван", "expertise": ["маркетинг"]})
    assert r.status_code == 400
    assert "Согласие" in r.json()["detail"]

    # With consent — success
    r = client.post("/api/experts", headers=headers, json={
        "name": "Иван Иванов",
        "email": "ivan@test.ru",
        "consent_granted": True,
        "expertise": ["маркетинг"],
        "city": "Москва",
    })
    assert r.status_code == 200, r.text
    assert "expert_id" in r.json()


def test_expert_full_crud(client):
    token = _mock_supabase_token(role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    r = client.post("/api/experts", headers=headers, json={
        "name": "Петр Петров",
        "email": "petr@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
        "city": "СПб",
    })
    assert r.status_code == 200, r.text
    expert_id = r.json()["expert_id"]

    # Get
    r = client.get(f"/api/experts/{expert_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Петр Петров"

    # Update
    r = client.patch(f"/api/experts/{expert_id}", headers=headers, json={"city": "Казань"})
    assert r.status_code == 200

    # Consent log
    r = client.post(f"/api/experts/{expert_id}/consent", headers=headers, json={
        "consent_type": "processing", "is_granted": True,
    })
    assert r.status_code == 200, r.text
    assert r.json()["consent_type"] == "processing"

    # Export request
    r = client.post(f"/api/experts/{expert_id}/export", headers=headers, json={
        "export_format": "json", "include_transcriptions": True,
    })
    assert r.status_code == 200, r.text
    assert "request_id" in r.json()

    # Deletion request
    r = client.post(f"/api/experts/{expert_id}/delete", headers=headers, json={
        "reason": "subject_request", "deletion_scope": "all",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"

    # Audit
    r = client.get("/api/audit?limit=10", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "logs" in data
    assert data["total"] >= 1
