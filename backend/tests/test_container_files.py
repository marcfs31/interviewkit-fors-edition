"""The image is built by Fly's remote builder and cannot be built in CI, so
these checks pin the invariants of the container files that would otherwise
only fail on deploy."""
import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

TEST_ONLY_PACKAGES = {"pytest", "pytest-cov", "pytest-flask", "coverage", "factory-boy", "faker"}


def _package_names(path):
    names = set()
    for line in (BACKEND / path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-r")):
            names.add(re.split(r"[=\[]", line)[0].lower().replace("_", "-"))
    return names


def _lines(path):
    return [line.strip() for line in (BACKEND / path).read_text().splitlines() if line.strip()]


def test_prod_requirements_hold_only_pinned_runtime_packages():
    prod = _lines("requirements-prod.txt")
    assert all("==" in line for line in prod)
    assert not _package_names("requirements-prod.txt") & TEST_ONLY_PACKAGES
    assert {"flask", "gunicorn", "psycopg2-binary"} <= _package_names("requirements-prod.txt")


def test_dev_requirements_extend_prod_with_the_test_packages():
    assert _lines("requirements.txt")[0] == "-r requirements-prod.txt"
    dev = _package_names("requirements.txt")
    assert TEST_ONLY_PACKAGES <= dev
    assert not dev & _package_names("requirements-prod.txt")


def test_dockerfile_pins_base_image_installs_prod_deps_and_drops_root():
    lines = _lines("Dockerfile")
    assert re.fullmatch(r"FROM python:3\.12-slim@sha256:[0-9a-f]{64}", lines[0])
    installs = [line for line in lines if line.startswith("RUN pip install")]
    assert installs == ["RUN pip install --no-cache-dir -r requirements-prod.txt"]
    users = [line for line in lines if line.startswith("USER ")]
    assert len(users) == 1 and users[0] not in ("USER root", "USER 0")
    assert lines.index(users[0]) < next(i for i, line in enumerate(lines) if line.startswith("CMD "))


def test_dockerignore_keeps_tests_and_tool_caches_out_of_the_image():
    entries = set(_lines(".dockerignore"))
    assert {"tests/", ".coverage", "coverage.xml", "htmlcov/", ".pytest_cache/",
            ".ruff_cache/", "venv*/", "__pycache__/"} <= entries


def test_fly_checks_health_endpoint():
    with open(BACKEND / "fly.toml", "rb") as f:
        service = tomllib.load(f)["http_service"]
    [check] = service["checks"]
    assert (check["method"], check["path"]) == ("GET", "/health")
    assert (check["interval"], check["timeout"], check["grace_period"]) == ("30s", "5s", "30s")
