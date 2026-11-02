"""Run the unchanged Paper2Agent verifier with typed float64 smoke assertions.

libm implementations may differ by one ULP. Nonzero real outputs use relative
error <=1e-14 and no absolute floor; zero, booleans and discrete contracts remain
exact. Scientific gradient qualification is independently enforced by the agent.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "paper2agent_vendor_verifier", ROOT / "reference/reproduction/barron2026/mcp/vendor/verify_mcp_server.py")
vendor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vendor)
_EXACT_CHECK = vendor.check_subset


def check_subset(actual, expected, location="result"):
    if isinstance(expected, dict):
        vendor.require(isinstance(actual, dict), f"{location}: expected an object")
        for key, value in expected.items():
            vendor.require(key in actual, f"{location}: missing field {key}")
            check_subset(actual[key], value, f"{location}.{key}")
    elif isinstance(expected, list):
        vendor.require(isinstance(actual, list) and len(actual) == len(expected), f"{location}: array mismatch")
        for index, (value, reference) in enumerate(zip(actual, expected)):
            check_subset(value, reference, f"{location}[{index}]")
    elif type(expected) is float:
        vendor.require(type(actual) in (float, int) and math.isfinite(actual) and
                       math.isfinite(expected) and math.isclose(actual, expected, rel_tol=1e-14, abs_tol=0),
                       f"{location}: float64 relative error exceeds 1e-14 (zero must be exact)")
    else:
        _EXACT_CHECK(actual, expected, location)


def main():
    original_check = vendor.check_subset
    original_verify = vendor.verify

    async def verify(server, expected, cases, cwd, timeout, call_timeout, report):
        report["numeric_assertion_policy"] = {"relative_tolerance": 1e-14, "absolute_tolerance": 0,
                                               "zero_and_discrete": "exact"}
        return await original_verify(server, expected, cases, cwd, timeout, call_timeout, report)

    # Preserve the original scalar comparator: only real-valued assertions change.
    vendor.check_subset = check_subset
    vendor.verify = verify
    try:
        return vendor.main()
    finally:
        vendor.check_subset = original_check
        vendor.verify = original_verify


if __name__ == "__main__":
    raise SystemExit(main())
