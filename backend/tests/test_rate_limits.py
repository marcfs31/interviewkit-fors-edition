"""
Rate limits of the unauthenticated auth endpoints, the per-user daily cap on
the AI endpoints, and the limiter storage configuration.
"""

import logging
import time
import types

import pytest
from flask import Flask

from app import _warn_if_limits_are_per_process, limiter
from app.config import Config, _get_ratelimit_storage_uri

OTHER_IP = {"REMOTE_ADDR": "10.0.0.2"}

# Rejected by validation / authentication, so these never touch bcrypt or the
# DB, yet they still count against the limit.
BAD_LOGIN = {"email": "nobody@example.com", "password": "wrong-password"}
BAD_REGISTER = {"name": "x", "email": "not-an-email", "password": "short"}
NO_CODE = {}

AI_PAYLOAD = {"stack": "JavaScript", "level": "Básico", "topic": "General / Mixto"}
FAKE_QUESTIONS = {"theory": ["t1", "t2"], "code": ["q1", "q2", "q3"]}
FAKE_FEEDBACK = {
    "result": "CORRECT",
    "feedback": "Well done.",
    "card": {
        "concept": "Closures",
        "definition": "...",
        "explanation": "...",
        "use_case": "...",
        "avoid_when": "",
        "mnemonic": "",
        "code": "",
        "code_language": "javascript",
        "tags": [],
    },
}


def _post_until_limited(client, url, payload, allowed, **kwargs):
    for _ in range(allowed):
        assert client.post(url, json=payload, **kwargs).status_code != 429
    return client.post(url, json=payload, **kwargs)


@pytest.mark.parametrize(
    "url, payload, allowed",
    [
        ("/auth/login", BAD_LOGIN, 10),
        ("/auth/register", BAD_REGISTER, 5),
        ("/auth/oauth/exchange", NO_CODE, 20),
    ],
)
class TestAuthEndpointLimits:
    def test_request_over_the_limit_returns_429(self, client, url, payload, allowed):
        blocked = _post_until_limited(client, url, payload, allowed)

        assert blocked.status_code == 429
        assert "limite" in blocked.get_json()["error"]

    def test_other_ips_are_counted_independently(self, client, url, payload, allowed):
        assert _post_until_limited(client, url, payload, allowed).status_code == 429

        other = client.post(url, json=payload, environ_base=OTHER_IP)

        assert other.status_code != 429

    def test_clients_behind_the_proxy_are_keyed_by_forwarded_ip(
        self, client, url, payload, allowed
    ):
        headers = {"X-Forwarded-For": "203.0.113.5"}
        assert (
            _post_until_limited(
                client, url, payload, allowed, headers=headers
            ).status_code
            == 429
        )

        same_proxy_other_client = client.post(
            url, json=payload, headers={"X-Forwarded-For": "203.0.113.6"}
        )

        assert same_proxy_other_client.status_code != 429


def test_login_key_ignores_the_jwt_identity(client, auth_headers):
    """A request carrying a valid JWT is still counted by IP: the key must not
    depend on who the caller claims to be."""
    for _ in range(10):
        assert (
            client.post("/auth/login", json=BAD_LOGIN, headers=auth_headers).status_code
            != 429
        )

    anonymous = client.post("/auth/login", json=BAD_LOGIN)

    assert anonymous.status_code == 429


@pytest.fixture
def _mock_ai(monkeypatch):
    monkeypatch.setattr(
        "app.routes.sessions.generate_questions",
        lambda stack, level, topic: dict(FAKE_QUESTIONS),
    )
    monkeypatch.setattr(
        "app.routes.sessions.generate_feedback",
        lambda stack, question, answer, question_type="code": dict(FAKE_FEEDBACK),
    )


@pytest.fixture
def _clock(monkeypatch):
    """Moves the limiter's clock only (not the JWT's), so the hourly windows
    can expire while the daily one is still open."""
    offset = {"seconds": 0}
    fake_time = types.SimpleNamespace(time=lambda: time.time() + offset["seconds"])
    monkeypatch.setattr("limits.storage.memory.time", fake_time)
    return offset


@pytest.mark.usefixtures("_mock_ai")
class TestPerUserDailyAICap:
    def _answer(self, client, headers, session_id, question_id):
        return client.patch(
            f"/sessions/{session_id}/questions/{question_id}",
            json={"answer": "x"},
            headers=headers,
        )

    def _spend_the_daily_cap(self, client, headers):
        """5 creations + 15 answers: the most the hourly limits allow, which
        is exactly the 20-per-day cap."""
        created = None
        for _ in range(5):
            created = client.post("/sessions/", json=AI_PAYLOAD, headers=headers)
            assert created.status_code == 201
        session_id = created.get_json()["session_id"]
        question_id = created.get_json()["questions"][0]["question_id"]
        for _ in range(15):
            assert (
                self._answer(client, headers, session_id, question_id).status_code
                == 200
            )
        return session_id, question_id

    def test_cap_is_shared_by_create_and_answer(self, client, auth_headers, _clock):
        session_id, question_id = self._spend_the_daily_cap(client, auth_headers)
        _clock["seconds"] = 3601  # hourly windows expire, the daily one doesn't

        assert (
            client.post("/sessions/", json=AI_PAYLOAD, headers=auth_headers).status_code
            == 429
        )
        assert (
            self._answer(client, auth_headers, session_id, question_id).status_code
            == 429
        )

    def test_cap_does_not_affect_another_user(
        self, client, auth_headers, second_user_headers, _clock
    ):
        self._spend_the_daily_cap(client, auth_headers)
        _clock["seconds"] = 3601

        assert (
            client.post("/sessions/", json=AI_PAYLOAD, headers=auth_headers).status_code
            == 429
        )
        assert (
            client.post(
                "/sessions/", json=AI_PAYLOAD, headers=second_user_headers
            ).status_code
            == 201
        )

    def test_cap_resets_after_a_day(self, client, auth_headers, _clock):
        self._spend_the_daily_cap(client, auth_headers)
        _clock["seconds"] = 24 * 3600 + 1

        assert (
            client.post("/sessions/", json=AI_PAYLOAD, headers=auth_headers).status_code
            == 201
        )


class TestStorageConfiguration:
    def test_storage_uri_is_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://cache.internal:6379/0")

        assert _get_ratelimit_storage_uri() == "redis://cache.internal:6379/0"

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_unset_or_blank_keeps_memory(self, monkeypatch, raw):
        if raw is None:
            monkeypatch.delenv("RATELIMIT_STORAGE_URI", raising=False)
        else:
            monkeypatch.setenv("RATELIMIT_STORAGE_URI", raw)

        assert _get_ratelimit_storage_uri() == "memory://"

    def test_config_value_reaches_the_app_and_the_limiter(self, app):
        assert app.config["RATELIMIT_STORAGE_URI"] == Config.RATELIMIT_STORAGE_URI
        assert type(limiter.storage).__name__ == "MemoryStorage"


class TestProductionWarning:
    def _app(self, env, uri):
        flask_app = Flask("warning-test")
        flask_app.config.update(FLASK_ENV=env, RATELIMIT_STORAGE_URI=uri)
        return flask_app

    def test_warns_once_in_production_with_memory_storage(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app"):
            _warn_if_limits_are_per_process(self._app("production", "memory://"))

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "RATELIMIT_STORAGE_URI" in warnings[0].getMessage()

    def test_silent_when_a_shared_storage_is_configured(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app"):
            _warn_if_limits_are_per_process(
                self._app("production", "redis://cache.internal:6379/0")
            )

        assert caplog.records == []

    @pytest.mark.parametrize("env", ["development", "test"])
    def test_silent_outside_production(self, caplog, env):
        with caplog.at_level(logging.WARNING, logger="app"):
            _warn_if_limits_are_per_process(self._app(env, "memory://"))

        assert caplog.records == []
