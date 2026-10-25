"""Do the probe, the repair path and the monitor agree about "up"?

A service is a set of endpoints. /health on the front door answers even when the engine behind
it is dead, so a probe that stops at the first endpoint reports "up" for a service whose every
request returns 502. This audit asks the live services, then simulates a half-dead pair and
requires the answer to name the endpoint that went silent.

    python tools/audit_services.py
    python tools/audit_services.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework import services  # noqa: E402


def half_dead(name: str) -> dict:
    """The last endpoint of a pair goes silent; everything else answers."""
    urls = services.endpoints(name)
    real = services.answers

    def fake(url: str, timeout: float = 3.0) -> bool:
        return url != urls[-1]

    services.answers = fake
    try:
        return services.check(name)
    finally:
        services.answers = real


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    problems: list[str] = []
    rows = []
    for name, urls in services.ENDPOINTS.items():
        live = services.check(name)
        sim = half_dead(name) if len(urls) > 1 else None
        rows.append({"service": name, "endpoints": list(urls),
                     "healthy": live["healthy"], "silent": live["silent"],
                     "simulated_silent": (sim or {}).get("silent", [])})

        if sim is not None:
            if sim["healthy"]:
                problems.append(f"{name}: a dead half was reported healthy")
            if sim["silent"] != [urls[-1]]:
                problems.append(f"{name}: the dead half is not named "
                                f"({sim['silent']} instead of {[urls[-1]]})")

    if args.json:
        print(json.dumps({"services": rows, "ok": not problems}, indent=2))
    else:
        for row in rows:
            state = "up" if row["healthy"] else "down"
            print(f"{row['service']:<18} {state:<5} endpoints={len(row['endpoints'])}")
            for url in row["endpoints"]:
                mark = "silent" if url in row["silent"] else "answers"
                print(f"    {url:<44} {mark}")
            if row["simulated_silent"]:
                print(f"    half-dead simulation names: {', '.join(row['simulated_silent'])}")

    for line in problems:
        print(f"[FAIL] {line}")
    if not problems:
        print("[OK] every service is probed on every endpoint, and a dead half is named")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
