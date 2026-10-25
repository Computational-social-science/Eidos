"""What a service *is*, declared once.

The monitor and the recovery path must agree on when a service counts as up. They drifted:
the probe asked only the front door (8090/health) while the engine behind it (8081) was dead,
so the page said "up" and every request returned 502. This module is the one place that says
which endpoints have to answer.

A service is a set of endpoints, not a port.
"""

from __future__ import annotations

import urllib.error
import urllib.request

#: Every endpoint that must answer for the service to be considered up. A single-entry tuple is
#: a service with one face; two entries is a pair, and both are required.
ENDPOINTS = {
    "decision_service": ("http://127.0.0.1:8090/health", "http://127.0.0.1:8081/health"),
    "runtime_18434": ("http://127.0.0.1:18434/v1/models",),
}

#: Statuses that prove a server is alive. 401 means it answered and is enforcing auth; that is
#: presence, not absence, and treating it as "down" once made a live runtime look dead.
ALIVE = range(200, 500)


def answers(url: str, timeout: float = 3.0) -> bool:
    """Did this endpoint answer at all? 401 is an answer — it is a server enforcing auth.

    urllib raises HTTPError for 4xx, and HTTPError is a URLError subclass, so the naive
    `except URLError: return False` reports an authenticated runtime as dead. That is the
    exact mistake this module exists to stop repeating.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status in ALIVE
    except urllib.error.HTTPError as exc:
        return exc.code in ALIVE
    except (urllib.error.URLError, OSError):
        return False


def endpoints(service: str) -> tuple[str, ...]:
    return ENDPOINTS.get(service, ())


def check(service: str) -> dict:
    """Every endpoint, the ones that answered, and the first that did not."""
    urls = endpoints(service)
    if not urls:
        return {"service": service, "known": False, "healthy": False, "silent": []}
    answered = {url: answers(url) for url in urls}
    silent = [url for url, ok in answered.items() if not ok]
    return {"service": service, "known": True, "healthy": not silent,
            "answered": answered, "silent": silent}
