"""One line, and the evidence for it.

`overall` alone is not a health check. On 2026-10-27 the sampler had been dead for ten hours while
`/api/status` still answered `overall: OK`; the `stale` flag was in the payload and nobody read it.
This prints the verdict *and* the numbers behind it, so a reader cannot take the label without seeing
the age.

    python tools/health.py            → OK    seq=41 age=4.2s faults=-
    python tools/health.py --json     → {"verdict": "OK", ...}

Exit: 0 OK, 1 STALE, 2 ALARM, 3 unreachable.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def classify(payload: dict) -> tuple[str, list[str]]:
    """Verdict plus the evidence that decided it. Pure, so it can be tested without a server."""
    age = payload.get("sample_age_s")
    faults = list((payload.get("derived") or {}).get("faults") or [])
    overall = payload.get("overall")
    if payload.get("stale") or overall == "STALE":
        return "STALE", [f"sample is {age}s old"] + faults
    if overall == "ALARM" or faults:
        return "ALARM", faults or [f"overall {overall}"]
    if overall == "OK":
        return "OK", []
    return "UNKNOWN", [f"overall {overall!r}"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8765/api/status")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        with urllib.request.urlopen(args.url, timeout=8) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        if args.json:
            print(json.dumps({"verdict": "UNREACHABLE", "reason": str(exc)}))
        else:
            print(f"UNREACHABLE  {args.url}: {exc}")
        return 3

    verdict, evidence = classify(payload)
    if args.json:
        print(json.dumps({"verdict": verdict, "seq": payload.get("seq"),
                          "age_s": payload.get("sample_age_s"), "evidence": evidence,
                          "ts": payload.get("ts")}))
    else:
        age = payload.get("sample_age_s")
        seq = payload.get("seq")
        faults = "; ".join(evidence) if evidence else "-"
        print(f"{verdict:<11} seq={seq} age={age}s faults={faults}")
    return {"OK": 0, "STALE": 1, "ALARM": 2}.get(verdict, 2)


if __name__ == "__main__":
    sys.exit(main())
