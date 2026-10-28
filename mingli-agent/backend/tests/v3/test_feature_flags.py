import httpx
import pytest

from app.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_feature_snapshot_respects_v3_master_switch(monkeypatch):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        monkeypatch.setattr(settings, "V3_ENABLED", False)
        monkeypatch.setattr(settings, "PERSONA_ENABLED", True)
        disabled = (await client.get("/api/features")).json()
        assert disabled["v3_enabled"] is False
        assert disabled["persona_enabled"] is False

        monkeypatch.setattr(settings, "V3_ENABLED", True)
        enabled = (await client.get("/api/features")).json()
        assert enabled["v3_enabled"] is True
        assert enabled["persona_enabled"] is True
