import os
from datetime import timedelta
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))


def _get_database_url():
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _get_ratelimit_storage_uri():
    """Where Flask-Limiter keeps its counters. Unset or blank keeps the
    per-process memory:// storage (a shared one needs e.g. a redis:// URI)."""
    return (os.getenv("RATELIMIT_STORAGE_URI") or "").strip() or "memory://"


ALLOWED_ENVS = ("development", "test", "production")
_DEFAULT_FRONTEND_URL = "http://localhost:3000"
_MIN_PROD_SECRET_LENGTH = 32


def load_env_settings(environ):
    """Validates the environment-dependent settings and derives everything
    that hangs off FLASK_ENV from that single value. Fails closed: a missing
    or unknown FLASK_ENV (e.g. a "prod" typo) never degrades to a default."""
    env = environ.get("FLASK_ENV")
    if env not in ALLOWED_ENVS:
        raise RuntimeError(
            f"FLASK_ENV must be one of {', '.join(ALLOWED_ENVS)}; got {env!r}."
        )
    is_prod = env == "production"

    secret_key = environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY is required. Set it in .env or the environment variables."
        )
    jwt_secret_key = environ.get("JWT_SECRET_KEY")
    if not jwt_secret_key:
        raise RuntimeError(
            "JWT_SECRET_KEY is required. Set it in .env or the environment variables."
        )
    if is_prod:
        for name, value in (
            ("SECRET_KEY", secret_key),
            ("JWT_SECRET_KEY", jwt_secret_key),
        ):
            if len(value) < _MIN_PROD_SECRET_LENGTH:
                raise RuntimeError(
                    f"{name} must be at least {_MIN_PROD_SECRET_LENGTH} characters in production."
                )
        if secret_key == jwt_secret_key:
            raise RuntimeError(
                "SECRET_KEY and JWT_SECRET_KEY must be distinct in production."
            )

    frontend_url = environ.get("FRONTEND_URL")
    if not frontend_url:
        if is_prod:
            raise RuntimeError("FRONTEND_URL is required in production.")
        frontend_url = _DEFAULT_FRONTEND_URL

    return {
        "FLASK_ENV": env,
        "SECRET_KEY": secret_key,
        "JWT_SECRET_KEY": jwt_secret_key,
        "FRONTEND_URL": frontend_url,
        "COOKIE_SECURE": is_prod,
        "COOKIE_SAMESITE": "None" if is_prod else "Lax",
        "PREFERRED_URL_SCHEME": "https" if is_prod else "http",
    }


_SETTINGS = load_env_settings(os.environ)


class Config:
    SQLALCHEMY_DATABASE_URI = _get_database_url()
    # pool_pre_ping: check each pooled connection with a lightweight ping
    # before reusing it, so a connection the DB server already closed (idle
    # timeout, managed-Postgres suspend, etc.) gets transparently replaced
    # instead of surfacing as an OperationalError on the request that draws
    # it from the pool - which is what caused OAuth login (and any other
    # first request after a period of inactivity) to fail once and then
    # succeed on retry once the pool had a fresh connection.
    # pool_recycle: proactively recycle connections older than this many
    # seconds, so we don't rely solely on the ping catching everything.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    SECRET_KEY = _SETTINGS["SECRET_KEY"]

    JWT_SECRET_KEY = _SETTINGS["JWT_SECRET_KEY"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "1"))
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Hard cap on any request body (413 beyond it). The largest legitimate
    # payload is a card, bounded far below this by the per-field caps.
    MAX_CONTENT_LENGTH = 64 * 1024

    # Header only: a cookie is sent by the browser on cross-site requests on
    # its own, so accepting the JWT from one would make every route CSRF-able.
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # Flask's session cookie (used by Authlib to store the OAuth handshake's
    # state/nonce). This is cross-site in production (frontend on Vercel,
    # backend on Fly.io), so it needs explicit SameSite=None + Secure; Flask's
    # defaults aren't enough and cause the state to get lost on the redirect
    # back from Google/GitHub.
    SESSION_COOKIE_SAMESITE = _SETTINGS["COOKIE_SAMESITE"]
    SESSION_COOKIE_SECURE = _SETTINGS["COOKIE_SECURE"]

    RATELIMIT_STORAGE_URI = _get_ratelimit_storage_uri()

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

    # Comma-separated CORS origins.
    # Dev example: "http://localhost:3000"
    # Prod example: "https://your-app.vercel.app,https://*.vercel.app"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")

    # Public frontend URL (used to redirect after OAuth)
    FRONTEND_URL = _SETTINGS["FRONTEND_URL"]

    # App mode: "development" | "production" | "test"
    FLASK_ENV = _SETTINGS["FLASK_ENV"]

    # Behind a proxy in production, force HTTPS in generated URLs
    PREFERRED_URL_SCHEME = _SETTINGS["PREFERRED_URL_SCHEME"]

    @staticmethod
    def parse_cors_origins():
        """Turns 'a,b,c' into ['a','b','c']. Returns an empty list if blank."""
        raw = (Config.CORS_ORIGINS or "").strip()
        if not raw:
            return []
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
