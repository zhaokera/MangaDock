from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


def test_platforms_endpoint_exposes_dl_expo_as_video():
    response = client.get("/api/platforms")

    assert response.status_code == 200
    dl_expo = next(item for item in response.json()["platforms"] if item["name"] == "dl_expo")
    assert dl_expo["display_name"] == "糯米影视"
    assert dl_expo["type"] == "video"
