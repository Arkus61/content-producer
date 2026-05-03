"""Extended tests for auth, ownership, compliance."""
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


# ── Ownership tests ──────────────────────────────────────

def test_user_cannot_read_other_users_expert(client):
    token1 = _mock_supabase_token(email="u1@test.ru")
    token2 = _mock_supabase_token(email="u2@test.ru")

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    r = client.post("/api/experts", headers=headers1, json={
        "name": "Иван Иванов",
        "email": "ivan@test.ru",
        "consent_granted": True,
        "expertise": ["маркетинг"],
    })
    assert r.status_code == 200, r.text
    expert_id = r.json()["expert_id"]

    r2 = client.get(f"/api/experts/{expert_id}", headers=headers2)
    assert r2.status_code == 403, r2.text


def test_user_can_read_own_expert(client):
    token = _mock_supabase_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/experts", headers=headers, json={
        "name": "Петр",
        "email": "petr@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
    })
    expert_id = r.json()["expert_id"]

    r2 = client.get(f"/api/experts/{expert_id}", headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["name"] == "Петр"


def test_operator_cannot_see_others_email(client):
    token = _mock_supabase_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/experts", headers=headers, json={
        "name": "Секретный",
        "email": "secret@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
    })
    assert r.status_code == 200, r.text
    expert_id = r.json()["expert_id"]

    r2 = client.get(f"/api/experts/{expert_id}", headers=headers)
    data = r2.json()
    assert data.get("email") == "secret@test.ru"  # owner sees


def test_interview_requires_auth(client):
    r = client.post("/api/interview/start", json={"expert_name": "Тест"})
    assert r.status_code == 401


def test_interview_answer_requires_auth_and_ownership(client):
    token = _mock_supabase_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/interview/start", headers=headers, json={"expert_name": "Тест"})
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]

    token2 = _mock_supabase_token()
    headers2 = {"Authorization": f"Bearer {token2}"}
    r2 = client.post(f"/api/interview/{session_id}/answer", headers=headers2, json={"answer": "test"})
    assert r2.status_code == 403, r2.text


# ── Compliance tests ─────────────────────────────────────

def test_consent_version_minumum(client):
    token = _mock_supabase_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/experts", headers=headers, json={
        "name": "Василий",
        "email": "vas@test.ru",
        "consent_granted": True,
        "consent_version": "0.1",
        "expertise": ["IT"],
    })
    assert r.status_code == 400, r.text
    assert "version" in r.json()["detail"].lower()


# ── Admin tests ──────────────────────────────────────────

def test_admin_audit_endpoint(client):
    token = _mock_supabase_token(role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/audit?limit=10", headers=headers)
    assert r.status_code == 200, r.text
    assert "logs" in r.json()


# ── Consent ownership tests ──────────────────────────────

def test_consent_requires_ownership(client):
    token1 = _mock_supabase_token(email="u1@test.ru")
    token2 = _mock_supabase_token(email="u2@test.ru")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    r = client.post("/api/experts", headers=headers1, json={
        "name": "Эксперт",
        "email": "expert@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
    })
    assert r.status_code == 200, r.text
    expert_id = r.json()["expert_id"]

    r2 = client.post(f"/api/experts/{expert_id}/consent", headers=headers2, json={
        "consent_type": "processing", "is_granted": True,
    })
    assert r2.status_code == 403, r2.text


def test_consent_withdrawal_requires_ownership(client):
    token1 = _mock_supabase_token(email="u1@test.ru")
    token2 = _mock_supabase_token(email="u2@test.ru")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    r = client.post("/api/experts", headers=headers1, json={
        "name": "Эксперт",
        "email": "expert@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
    })
    expert_id = r.json()["expert_id"]

    r2 = client.delete(f"/api/experts/{expert_id}/consent/processing", headers=headers2)
    assert r2.status_code == 403, r2.text


# ── Export / Deletion ownership tests ────────────────────

def test_export_requires_ownership(client):
    token1 = _mock_supabase_token(email="u1@test.ru")
    token2 = _mock_supabase_token(email="u2@test.ru")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    r = client.post("/api/experts", headers=headers1, json={
        "name": "Эксперт",
        "email": "expert@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
    })
    expert_id = r.json()["expert_id"]

    r2 = client.post(f"/api/experts/{expert_id}/export", headers=headers2, json={
        "export_format": "json", "include_transcriptions": True,
    })
    assert r2.status_code == 403, r2.text


def test_deletion_requires_ownership(client):
    token1 = _mock_supabase_token(email="u1@test.ru")
    token2 = _mock_supabase_token(email="u2@test.ru")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    r = client.post("/api/experts", headers=headers1, json={
        "name": "Эксперт",
        "email": "expert@test.ru",
        "consent_granted": True,
        "expertise": ["IT"],
    })
    expert_id = r.json()["expert_id"]

    r2 = client.post(f"/api/experts/{expert_id}/delete", headers=headers2, json={
        "reason": "subject_request", "deletion_scope": "all",
    })
    assert r2.status_code == 403, r2.text


