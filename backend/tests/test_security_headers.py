"""
Tests for the security headers every API response carries (after_request in
app/__init__.py). The API only serves JSON and redirects, so the CSP is
fully closed; HSTS is production-only because plain-HTTP dev must keep working.
"""

from unittest.mock import patch

import pytest

from app import create_app
from app.config import Config

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
HSTS = "max-age=63072000; includeSubDomains"


def _assert_base_headers(resp):
    for name, value in BASE_HEADERS.items():
        assert resp.headers.get(name) == value, name


@pytest.fixture
def production_client(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "production")
    return create_app().test_client()


class TestHeadersOnEveryResponse:
    def test_json_route(self, client, db):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.is_json
        _assert_base_headers(resp)

    def test_error_response(self, client):
        resp = client.get("/no-such-route")
        assert resp.status_code == 404
        _assert_base_headers(resp)

    def test_redirect_keeps_its_location(self, client, db):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.side_effect = Exception(
                "Token error"
            )
            resp = client.get("/auth/google/callback")
        assert resp.status_code == 302
        assert resp.location == "http://localhost:3000/login?error=oauth_failed"
        _assert_base_headers(resp)

    def test_cors_headers_are_not_disturbed(self, client):
        resp = client.get("/no-such-route", headers={"Origin": "http://localhost:3000"})
        assert (
            resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
        )
        _assert_base_headers(resp)


class TestHsts:
    def test_absent_outside_production(self, client, db):
        assert "Strict-Transport-Security" not in client.get("/health").headers
        assert "Strict-Transport-Security" not in client.get("/no-such-route").headers

    def test_present_in_production_on_errors(self, production_client):
        resp = production_client.get("/no-such-route")
        assert resp.status_code == 404
        assert resp.headers.get("Strict-Transport-Security") == HSTS
        _assert_base_headers(resp)

    def test_present_in_production_on_redirects(self, production_client):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.side_effect = Exception(
                "Token error"
            )
            resp = production_client.get("/auth/google/callback")
        assert resp.status_code == 302
        assert "error=oauth_failed" in resp.location
        assert resp.headers.get("Strict-Transport-Security") == HSTS
        _assert_base_headers(resp)
