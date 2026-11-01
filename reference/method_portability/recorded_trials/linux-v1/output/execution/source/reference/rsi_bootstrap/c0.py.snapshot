"""Single-attempt development proposal core with an externally bounded transport.

run_once does not own a model or establish a network/process deadline. The
transport must be supplied by a separately qualified, owned runtime controller.
Tests use declared doubles. No scientific promotion is possible here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Callable

import numpy as np

from . import expressions, grader


PROMPT = """Propose one numerical repair for f(x)=log(1-exp(-x)) and its first
derivative for positive finite float32/float64 scalar x with normal-range results.
The textbook loss and exp(-x)/(1-exp(-x)) derivative can lose significant digits.
The Softmax lesson is to preserve small quantities in the actual arithmetic;
finite output or a correct-looking forward value does not verify the derivative.
Return only a JSON object with exactly program and explanation. explanation is a
nonempty string. program has exactly loss and gradient expression nodes.
Leaves: {"input":"x"} or {"const":finite_number} (no booleans).
Operators: {"op":name,"args":[nodes]}; unary neg/exp/expm1/log/log1p;
binary add/sub/mul/div/le; ternary where(boolean,number,number), evaluated lazily.
Only le produces booleans. Both outputs must be numeric. All arithmetic retains
the input dtype. No Python, code fences, imports, paths or external tools.
Whole response <=32768 UTF-8 bytes, program <=256 nodes and depth <=16.
This is a public development task, not a scientific novelty or held-out claim.
"""


def source_snapshot() -> dict[str, str]:
    folder = Path(__file__).resolve().parent
    paths = sorted(folder.glob("*.py")) + [folder / "C0-SPEC.md", grader.PROTOCOL]
    return {p.relative_to(grader.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate response key")
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError("nonfinite response constant")


def run_once(provider: Callable[[str], str]) -> dict:
    """Request once, preserve adverse outcomes, and check the actual expressions.

    This is the proposal/evaluation core. Callers must not confuse a successful
    supplied test transport with actual model execution or a bounded trial.
    """
    started = time.monotonic()
    before = source_snapshot()
    result = {"schema": "eidos.rsi.c0.development-core.v1",
              "observed_at": datetime.now(timezone.utc).isoformat(),
              "status": "UNOBSERVED", "source_before": before,
              "prompt": PROMPT, "raw_response": "", "points": [],
              "retained_for_development": False, "scientific_promotion": False,
              "model_execution_attested": False, "sealed_evaluation": "NOT_RUN",
              "scientific_rsi": "NOT_DEMONSTRATED", "provider_calls": 1}
    try:
        try:
            raw = provider(PROMPT)
        except TimeoutError:
            result["status"] = "TRANSPORT_TIMEOUT"
            return result
        except Exception as error:
            result.update(status="TRANSPORT_ERROR", error_type=type(error).__name__)
            return result
        if not isinstance(raw, str):
            result["status"] = "INVALID_RESPONSE"
            return result
        result["raw_response"] = raw[:expressions.MAX_BYTES]
        result["response_characters"] = len(raw)
        try:
            if len(raw) > expressions.MAX_BYTES or len(raw.encode("utf-8")) > expressions.MAX_BYTES:
                raise ValueError("response budget exceeded")
            envelope = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
            if (not isinstance(envelope, dict) or set(envelope) != {"program", "explanation"}
                    or not isinstance(envelope["explanation"], str)
                    or not envelope["explanation"].strip()):
                raise ValueError("invalid response envelope")
            program = expressions.parse_program(json.dumps(envelope["program"], allow_nan=False))
        except (ValueError, RecursionError):
            result["status"] = "INVALID_RESPONSE"
            return result
        result["explanation"] = envelope["explanation"]
        cases = grader.development_cases()
        with np.errstate(all="ignore"):
            result["baseline_conforming_points"] = sum(
                grader.grade(case, *grader.textbook(case.value))["passed"] for case in cases)
            for case in cases:
                outputs = expressions.execute(program, case.value)
                point = grader.grade(case, *outputs)
                # Decimal acceptance is already decided by the oracle. Preserve
                # a normal rejection even when its float diagnostic overflows.
                for key in ("loss_relative_error", "gradient_relative_error"):
                    if point[key] is not None and not math.isfinite(point[key]):
                        point[key] = None
                        point.setdefault("diagnostic_range_error", []).append(key)
                point["actual_outputs"] = [float(v) if np.isfinite(v) else str(v) for v in outputs]
                result["points"].append(point)
        result["candidate_conforming_points"] = sum(p["passed"] for p in result["points"])
        accepted = len(result["points"]) == 23 and all(p["passed"] for p in result["points"])
        result["retained_for_development"] = accepted
        result["status"] = "DEVELOPMENT_CONFORMING" if accepted else "DEVELOPMENT_NONCONFORMING"
        return result
    except Exception as error:
        result.update(status="EVALUATOR_ERROR", error_type=type(error).__name__,
                      retained_for_development=False)
        return result
    finally:
        result["wall_seconds"] = time.monotonic() - started
        try:
            result["source_after"] = source_snapshot()
        except OSError:
            result.update(source_after=None, status="INPUT_UNOBSERVABLE",
                          retained_for_development=False)
        else:
            if before != result["source_after"]:
                result.update(status="INPUT_CHANGED", retained_for_development=False)
