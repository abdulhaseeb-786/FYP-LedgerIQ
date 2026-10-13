"""API endpoint tests for Audit Analytics module."""

import sys
from pathlib import Path
import pytest

BACKEND_DIR = str(Path(__file__).resolve().parents[4])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import Base, get_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


@pytest.fixture
async def test_client():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.anyio
async def test_health_endpoint(test_client):
    """Verify that backend health check includes registered services."""
    res = await test_client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"


@pytest.mark.anyio
async def test_gl_audit_endpoint_csv_upload(test_client):
    """Verify POST /api/v1/analytics/gl-audit with multipart file upload."""
    csv_bytes = b"""Voucher No,Date,Account Code,Account Title,Narration,Debit,Credit,User
JV-001,2025-01-10,1010,Cash in Hand,Petty cash,10000.00,0.00,user_1
JV-002,2025-01-11,2010,Trade Creditors,Vendor payment,0.00,10000.00,user_1
"""
    files = {"file": ("test_ledger.csv", csv_bytes, "text/csv")}
    data = {
        "entity_name": "Atlas Power Ltd",
        "reporting_period": "FY2024-25",
        "contamination_rate": "0.03",
    }

    res = await test_client.post("/api/v1/analytics/gl-audit", files=files, data=data)
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    res_data = payload["data"]
    assert res_data["entity_name"] == "Atlas Power Ltd"
    assert res_data["status"] == "SUCCESS"
    assert "report" in res_data
    run_id = res_data["run_id"]

    # Verify retrieval via GET /api/v1/analytics/runs/{id}
    get_res = await test_client.get(f"/api/v1/analytics/runs/{run_id}")
    assert get_res.status_code == 200
    run_payload = get_res.json()
    assert run_payload["data"]["id"] == run_id
    assert run_payload["data"]["entity_name"] == "Atlas Power Ltd"
