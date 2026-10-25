"""One endpoint table, reachable two ways, and the status codes that mean "alive".

The refactor that introduced framework/services.py shipped a broken import: recovery used a
flat `import services`, which only resolves when framework/ itself is on sys.path. The tests
caught it after the commit. These tests catch it before.
"""

from __future__ import annotations

import importlib
import sys
import urllib.error
from email.message import Message

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_package_and_flat_import_see_the_same_table():
    package = importlib.import_module("framework.services")
    sys.path.insert(0, str(ROOT / "framework"))
    try:
        flat = importlib.import_module("services")
        assert flat.ENDPOINTS == package.ENDPOINTS
        assert flat.ENDPOINTS["decision_service"] == package.ENDPOINTS["decision_service"]
    finally:
        sys.path.remove(str(ROOT / "framework"))
        sys.modules.pop("services", None)


def test_recovery_reads_the_shared_table():
    from framework import recovery, services

    assert recovery.ENDPOINTS is services.ENDPOINTS


def test_401_is_presence_not_absence(monkeypatch):
    """urllib raises HTTPError for 401, and HTTPError is a URLError subclass.

    The naive `except URLError: return False` therefore reports an authenticated runtime as
    dead — the exact confusion that made a live service look down.
    """
    from framework import services

    def boom(url, timeout=3.0):
        raise urllib.error.HTTPError(url, 401, "unauthorized", Message(), None)

    monkeypatch.setattr(services.urllib.request, "urlopen", boom)
    assert services.answers("http://127.0.0.1:18434/v1/models") is True


def test_a_refused_connection_is_absence(monkeypatch):
    from framework import services

    def refused(url, timeout=3.0):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(services.urllib.request, "urlopen", refused)
    assert services.answers("http://127.0.0.1:9/health") is False


def test_the_pair_reports_the_half_that_is_silent(monkeypatch):
    """A service with two faces is healthy only if both answer, and it must name the silent one."""
    from framework import services

    seen = []

    def only_front_door(url, timeout=3.0):
        seen.append(url)
        if url.endswith(":8081/health"):
            raise urllib.error.URLError("refused")
        raise urllib.error.HTTPError(url, 200, "ok", Message(), None)

    monkeypatch.setattr(services.urllib.request, "urlopen", only_front_door)
    look = services.check("decision_service")
    assert look["healthy"] is False
    assert look["silent"] == ["http://127.0.0.1:8081/health"]
    assert len(seen) == 2
