"""HTTP probes that cannot inherit a stale opinion.

The sampler runs for days. Twice it reached a state where `urllib` returned "silent" for services that
answered `curl` in milliseconds, and only a restart cleared it — a per-process proxy table or connection
pool holding a decision that was true at 09:00 and false at 10:00.

A raw socket has none of that state: one connection, one request, one answer. 401 is an answer.
"""

from __future__ import annotations

import json
import socket
from urllib.parse import urlsplit


def raw_request(url: str, headers: dict | None = None, timeout: float = 2.0) -> tuple[int, bytes]:
    """Return (status, body); status 0 means nothing answered."""
    parts = urlsplit(url)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query

    lines = [f"GET {path} HTTP/1.0", f"Host: {host}", "Connection: close"]
    for key, value in (headers or {}).items():
        lines.append(f"{key}: {value}")
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(request)
            chunks: list[bytes] = []
            total = 0
            while total < 4_000_000:
                block = sock.recv(65536)
                if not block:
                    break
                chunks.append(block)
                total += len(block)
    except OSError:
        return 0, b""

    blob = b"".join(chunks)
    head, _, body = blob.partition(b"\r\n\r\n")
    try:
        status = int(head.split(b"\r\n", 1)[0].split()[1])
    except (IndexError, ValueError):
        return 0, b""
    return status, body


def http_json(url: str, timeout: float = 2.0) -> tuple[int, dict]:
    status, body = raw_request(url, timeout=timeout)
    if not status:
        return 0, {"error": "no response"}
    try:
        return status, json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return status, {}


def http_status(url: str, headers: dict | None = None, timeout: float = 2.0) -> int:
    status, _ = raw_request(url, headers=headers, timeout=timeout)
    return status
