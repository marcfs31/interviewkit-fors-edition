"""
Tests for fail-closed environment configuration (app/config.py) and the
places that consume it (debug blueprint registration, Sentry environment).
"""

import pytest

from app import create_app
from app.config import Config, load_env_settings

SECRET_A = "a" * 32
SECRET_B = "b" * 32


def _env(**overrides):
    env = {
        "FLASK_ENV": "production",
        "SECRET_KEY": SECRET_A,
        "JWT_SECRET_KEY": SECRET_B,
        "FRONTEND_URL": "https://app.example.com",
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


class TestFlaskEnv:
    def test_missing_flask_env_raises(self):
        with pytest.raises(RuntimeError, match="FLASK_ENV"):
            load_env_settings(_env(FLASK_ENV=None))

    @pytest.mark.parametrize("bad", ["prod", "Production", "staging", ""])
    def test_unknown_flask_env_raises_naming_the_value(self, bad):
        with pytest.raises(RuntimeError, match=repr(bad)):
            load_env_settings(_env(FLASK_ENV=bad))

    @pytest.mark.parametrize("name", ["development", "test", "production"])
    def test_allowed_values_pass(self, name):
        assert load_env_settings(_env(FLASK_ENV=name))["FLASK_ENV"] == name

    def test_cookie_settings_derive_from_the_single_value(self):
        prod = load_env_settings(_env(FLASK_ENV="production"))
        assert prod["COOKIE_SECURE"] is True
        assert prod["COOKIE_SAMESITE"] == "None"
        dev = load_env_settings(_env(FLASK_ENV="development"))
        assert dev["COOKIE_SECURE"] is False
        assert dev["COOKIE_SAMESITE"] == "Lax"


class TestSecrets:
    @pytest.mark.parametrize("env", ["development", "test", "production"])
    def test_missing_secret_key_raises_in_every_env(self, env):
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            load_env_settings(_env(FLASK_ENV=env, SECRET_KEY=None))

    def test_empty_secret_key_raises(self):
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            load_env_settings(_env(FLASK_ENV="development", SECRET_KEY=""))

    def test_missing_jwt_secret_key_raises(self):
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            load_env_settings(_env(FLASK_ENV="development", JWT_SECRET_KEY=None))

    def test_production_rejects_short_secret_key(self):
        with pytest.raises(RuntimeError, match="SECRET_KEY.*32"):
            load_env_settings(_env(SECRET_KEY="short"))

    def test_production_rejects_short_jwt_secret_key(self):
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY.*32"):
            load_env_settings(_env(JWT_SECRET_KEY="short"))

    def test_production_rejects_equal_secrets(self):
        with pytest.raises(RuntimeError, match="distinct"):
            load_env_settings(_env(SECRET_KEY=SECRET_A, JWT_SECRET_KEY=SECRET_A))

    def test_non_production_allows_short_and_equal_secrets(self):
        settings = load_env_settings(
            _env(FLASK_ENV="development", SECRET_KEY="dev", JWT_SECRET_KEY="dev")
        )
        assert settings["SECRET_KEY"] == "dev"

    def test_secret_key_does_not_fall_back_to_jwt_secret(self):
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            load_env_settings(_env(FLASK_ENV="development", SECRET_KEY=None))


class TestFrontendUrl:
    def test_production_requires_frontend_url(self):
        with pytest.raises(RuntimeError, match="FRONTEND_URL"):
            load_env_settings(_env(FRONTEND_URL=None))

    def test_production_rejects_empty_frontend_url(self):
        with pytest.raises(RuntimeError, match="FRONTEND_URL"):
            load_env_settings(_env(FRONTEND_URL=""))

    def test_production_keeps_the_configured_value(self):
        assert load_env_settings(_env())["FRONTEND_URL"] == "https://app.example.com"

    @pytest.mark.parametrize("env", ["development", "test"])
    def test_non_production_defaults_to_localhost(self, env):
        settings = load_env_settings(_env(FLASK_ENV=env, FRONTEND_URL=None))
        assert settings["FRONTEND_URL"] == "http://localhost:3000"


class TestDerivedAppConfig:
    def test_config_exposes_validated_values(self):
        assert Config.FLASK_ENV == "test"
        assert Config.FRONTEND_URL == "http://localhost:3000"
        assert Config.SECRET_KEY == "test-secret-key"
        assert Config.PREFERRED_URL_SCHEME == "http"


class TestDebugBlueprintAllowlist:
    @pytest.mark.parametrize("env", ["development", "test"])
    def test_debug_blueprint_registered_in_dev_and_test(self, monkeypatch, env):
        monkeypatch.setattr(Config, "FLASK_ENV", env)
        assert "debug" in create_app().blueprints

    def test_debug_blueprint_absent_in_production(self, monkeypatch):
        monkeypatch.setattr(Config, "FLASK_ENV", "production")
        assert "debug" not in create_app().blueprints

    def test_debug_blueprint_absent_for_unknown_value(self, monkeypatch):
        monkeypatch.setattr(Config, "FLASK_ENV", "prod")
        assert "debug" not in create_app().blueprints


class TestSentryEnvironment:
    def test_sentry_uses_the_validated_flask_env(self, monkeypatch):
        captured = {}
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.invalid/1")
        monkeypatch.setattr("app.sentry_sdk.init", lambda **kw: captured.update(kw))
        monkeypatch.setattr(Config, "FLASK_ENV", "development")
        create_app()
        assert captured["environment"] == "development"
