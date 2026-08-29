from fastapi.testclient import TestClient

from backend.main import app
from backend.models import RecentRaceCard


def test_recent_races_endpoint_exists():
    try:
        client = TestClient(app, lifespan="off")
    except TypeError:
        client = TestClient(app)
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/recent-races" in paths
    assert "/api/aris/ghost-recompute" in paths
    resp = client.get("/api/recent-races?limit=3")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) <= 3
    for row in body:
        RecentRaceCard.model_validate(row)
        assert "r2_available" in row
        assert "circuitName" in row
        assert "year" in row
        assert "round" in row
