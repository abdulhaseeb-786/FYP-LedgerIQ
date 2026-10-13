"""API endpoint tests for Document Digitizer & Edge OCR (Module 7)."""

import sys
import io
from pathlib import Path
from PIL import Image
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
async def test_get_hardware_profile(test_client):
    response = await test_client.get("/api/v1/digitizer/hardware-profile")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "vram_ceiling_mb" in data
    assert data["vram_ceiling_mb"] == 2200.0
    assert data["zero_cloud_exfiltration_guarantee"] is True


@pytest.mark.anyio
async def test_process_image_upload(test_client):
    # Create simple image in memory
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"file": ("test_receipt.png", buf, "image/png")}
    data = {
        "document_id": "test-doc-01",
        "auto_disambiguate": "true",
    }

    response = await test_client.post("/api/v1/digitizer/process-image", files=files, data=data)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    res_data = json_data["data"]
    assert "document" in res_data
    assert "verification" in res_data
    assert "execution_profile" in res_data
