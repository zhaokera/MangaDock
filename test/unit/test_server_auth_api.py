from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


class TestAuthApi:
    def test_login_rejects_unsupported_platform(self):
        response = client.post(
            "/api/auth/login",
            json={
                "platform": "unknown",
                "username": "tester",
                "password": "secret",
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "不支持的平台: unknown"}
