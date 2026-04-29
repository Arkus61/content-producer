import os
import pytest
import asyncio

# Force fresh in-memory DB before any imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from fastapi.testclient import TestClient
from src.api import app
from src.db.engine import async_engine as engine
from src.db.models import Base


@pytest.fixture(scope="module")
def setup_test_db():
    """Create tables once for all tests."""
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.get_event_loop().run_until_complete(_setup())


@pytest.fixture
def client(setup_test_db):
    return TestClient(app)


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Content Producer" in resp.json()["name"]


def test_interview_not_found(client):
    resp = client.post("/api/interview/fake-id/answer", json={"answer": "x"})
    assert resp.status_code == 404


def test_create_expert(client):
    resp = client.post("/api/experts", json={
        "name": "API Test",
        "profession": "Tester",
        "expertise": ["testing"],
    })
    assert resp.status_code == 200
    assert "expert_id" in resp.json()


def test_list_experts(client):
    resp = client.get("/api/experts")
    assert resp.status_code == 200
    assert "experts" in resp.json()
