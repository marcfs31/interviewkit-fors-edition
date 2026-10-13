"""
Request-level bounds owned by the app factory: the 64 KiB body cap (413) and
the single check that a JSON body is an object (400), both answered as JSON.
"""
import json

import pytest

MAX_BODY = 64 * 1024


def _login_body_of_size(size):
    """A JSON object for /auth/login of exactly `size` bytes."""
    base = {"email": "nobody@example.com", "password": "wrong-password", "pad": ""}
    base["pad"] = "x" * (size - len(json.dumps(base)))
    body = json.dumps(base)
    assert len(body.encode()) == size
    return body


class TestBodySizeLimit:
    def test_body_over_the_limit_returns_json_413(self, client):
        resp = client.post(
            "/auth/login", data=_login_body_of_size(MAX_BODY + 1), content_type="application/json"
        )
        assert resp.status_code == 413
        assert resp.is_json
        assert "demasiado grande" in resp.get_json()["error"]

    def test_body_exactly_at_the_limit_is_accepted(self, client):
        resp = client.post(
            "/auth/login", data=_login_body_of_size(MAX_BODY), content_type="application/json"
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Credenciales incorrectas"


class TestJsonBodyShape:
    @pytest.mark.parametrize("body", ["[1, 2]", '"text"', "42", "null", "true", "[]"])
    @pytest.mark.parametrize("url", ["/auth/register", "/auth/login", "/oauth/exchange"])
    def test_non_object_json_body_returns_json_400(self, client, url, body):
        resp = client.post(url, data=body, content_type="application/json")
        assert resp.status_code == 400
        assert resp.is_json
        assert "objeto JSON" in resp.get_json()["error"]

    def test_non_object_body_is_rejected_on_patch_before_the_handler(self, client, auth_headers):
        resp = client.patch("/me/profile", data="[1]", headers=auth_headers)
        assert resp.status_code == 400
        assert "objeto JSON" in resp.get_json()["error"]

    def test_non_object_body_is_rejected_on_put_before_the_handler(self, client, app):
        # No PUT route exists: the 400 proves the check runs for the method
        # itself, ahead of routing-level 405s.
        resp = client.put("/auth/login", data="[1]", content_type="application/json")
        assert resp.status_code == 400
        assert "objeto JSON" in resp.get_json()["error"]

    def test_malformed_json_returns_json_400_not_html(self, client):
        resp = client.post("/auth/login", data="{not json", content_type="application/json")
        assert resp.status_code == 400
        assert resp.is_json
        assert "JSON" in resp.get_json()["error"]

    def test_empty_json_body_on_a_handler_that_reads_it_returns_json_400(self, client):
        resp = client.post("/auth/login", data="", content_type="application/json")
        assert resp.status_code == 400
        assert resp.is_json

    def test_object_body_reaches_the_handler(self, client):
        resp = client.post("/auth/login", json={"email": "a@example.com", "password": "x"})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Credenciales incorrectas"

    def test_bodyless_json_post_is_unaffected(self, client):
        """The frontend sends Content-Type: application/json on every call,
        including POSTs that carry no body (logout)."""
        resp = client.post("/auth/logout", data="", content_type="application/json")
        assert resp.status_code == 200

    def test_non_json_content_type_is_left_to_the_handler(self, client):
        resp = client.post("/auth/login", data="[1]", content_type="text/plain")
        assert resp.status_code == 415

    def test_get_with_json_content_type_is_unaffected(self, client):
        resp = client.get("/stacks/", data="[1]", content_type="application/json")
        assert resp.status_code == 200
