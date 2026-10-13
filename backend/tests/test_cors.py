"""
CORS policy: the API authenticates with the Authorization header only, so it
must not ask browsers to attach cookies to cross-origin requests.
"""
import pytest

from app import create_app
from app.config import Config

ORIGIN = "http://localhost:3000"


class TestCorsPolicy:
    def test_allowed_origin_is_echoed_without_allowing_credentials(self, client, db):
        resp = client.get("/health", headers={"Origin": ORIGIN})
        assert resp.headers.get("Access-Control-Allow-Origin") == ORIGIN
        assert "Access-Control-Allow-Credentials" not in resp.headers

    def test_preflight_allows_the_authorization_header_without_credentials(self, client, db):
        resp = client.options(
            "/me/profile",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.headers.get("Access-Control-Allow-Origin") == ORIGIN
        assert "Authorization" in resp.headers.get("Access-Control-Allow-Headers", "")
        assert "Access-Control-Allow-Credentials" not in resp.headers

    def test_other_origin_gets_no_cors_headers(self, client, db):
        resp = client.get("/health", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in resp.headers

    def test_app_refuses_to_start_without_cors_origins_in_production(self, monkeypatch):
        monkeypatch.setattr(Config, "FLASK_ENV", "production")
        monkeypatch.setattr(Config, "parse_cors_origins", staticmethod(lambda: []))
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            create_app()
