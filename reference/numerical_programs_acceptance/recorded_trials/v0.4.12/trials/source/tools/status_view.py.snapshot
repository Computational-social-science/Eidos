"""One derivation of "what is the state of the pipeline", used by every consumer.

The page has four places that report state — node colours, the fault line, the counter
cards, and the header pill. If each computes its own verdict they will disagree the moment
one of them is stale. So the verdict is computed **once**, from the same two inputs
(signal states and chain states), and everything else reads it:

    derive(signals, chains) -> {"overall", "faults", "counts"}

`watch_pipeline` puts it in the status payload, the dashboard renders it server-side and
repaints it from the same object, and the tests assert the three agree.
"""

from __future__ import annotations

SEVERITY = {"FAIL": 5, "STALE": 4, "RUNNING": 3, "SKIP": 2, "PASS": 1, "IDLE": 0}
FAULTY_CHAIN = ("FAIL", "STALE")


def worst(states) -> str:
    return max(states, key=lambda s: SEVERITY.get(s, 0)) if states else "IDLE"


def derive(signals: dict, chains: dict, module_users: dict | None = None) -> dict:
    """The single verdict: overall state, the named faults, and the counters.

    A chain that is SKIP is not a fault (the boundary was not exercised); a service that is
    not OK is. `overall` is ALARM when anything is a fault, else OK.
    """
    faults: list[str] = []
    for name, state in sorted((chains or {}).items()):
        if state in FAULTY_CHAIN:
            faults.append(f"chain:{name} = {state}")
    for name, row in sorted((signals or {}).items()):
        state = (row or {}).get("state")
        if state and state != "OK":
            faults.append(f"{name} = {'DOWN' if state == 'ALARM' else state}")

    if module_users:
        for module, users in sorted(module_users.items()):
            state = worst([(chains or {}).get(u, "IDLE") for u in users])
            if state in FAULTY_CHAIN:
                faults.append(f"{module} = {state}")

    counts = {
        "pass": sum(1 for s in (chains or {}).values() if s == "PASS"),
        "fail": sum(1 for s in (chains or {}).values() if s in ("FAIL", "ERROR")),
        "skip": sum(1 for s in (chains or {}).values() if s == "SKIP"),
        "services_up": sum(1 for r in (signals or {}).values() if (r or {}).get("state") == "OK"),
        "services_down": sum(1 for r in (signals or {}).values()
                             if (r or {}).get("state") not in (None, "OK")),
    }
    return {"overall": "ALARM" if faults else "OK", "faults": faults, "counts": counts}
