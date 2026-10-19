import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import init_db


@pytest.mark.asyncio
async def test_health_endpoint():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "HEALTHY"
        assert data["database"] == "ONLINE"


@pytest.mark.asyncio
async def test_cameras_list():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/cameras")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_analytics_summary():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data
        assert "active_alerts" in data


@pytest.mark.asyncio
async def test_camera_stop_start_toggle():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cams_res = await ac.get("/api/cameras")
        assert cams_res.status_code == 200
        cams = cams_res.json()
        assert len(cams) > 0
        cam_id = cams[0]["id"]

        # 1. Stop Camera
        stop_res = await ac.post(f"/api/cameras/{cam_id}/stop")
        assert stop_res.status_code == 200
        stop_data = stop_res.json()
        assert stop_data["success"] is True
        assert stop_data["status"] == "OFFLINE"

        # Verify DB status updated to OFFLINE
        cam_detail = await ac.get(f"/api/cameras/{cam_id}")
        assert cam_detail.status_code == 200
        assert cam_detail.json()["status"] == "OFFLINE"

        # 2. Start Camera
        start_res = await ac.post(f"/api/cameras/{cam_id}/start")
        assert start_res.status_code == 200
        start_data = start_res.json()
        assert start_data["success"] is True
        assert start_data["status"] == "ONLINE"

        # Verify DB status updated to ONLINE
        cam_detail2 = await ac.get(f"/api/cameras/{cam_id}")
        assert cam_detail2.status_code == 200
        assert cam_detail2.json()["status"] == "ONLINE"

        # 3. Toggle Camera (ONLINE -> OFFLINE)
        toggle_res = await ac.post(f"/api/cameras/{cam_id}/toggle")
        assert toggle_res.status_code == 200
        assert toggle_res.json()["status"] == "OFFLINE"

        # 4. Toggle Camera (OFFLINE -> ONLINE)
        toggle_res2 = await ac.post(f"/api/cameras/{cam_id}/toggle")
        assert toggle_res2.status_code == 200
        assert toggle_res2.json()["status"] == "ONLINE"

