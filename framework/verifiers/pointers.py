"""Gate S S4 and S7: a judgement is only as good as the pointer it cites.

Plan §6.1–6.2: every S4 check and every S7 objection carries an `evidence_pointer` of the form
`/artifacts/…/file.json#/json/pointer`. This module resolves those pointers against the artefacts on
disk and enforces the category rules:

* `statistics` must point into `stat_recompute.json`
* `support` must point into a support record
* `identification` must point into `proofpath.json`
* a `PASS` with an unresolved major or fatal objection is illegal

The model produces the JSON; this module decides whether it is admissible. Nothing here calls a
model, so a dangling pointer fails the same way whether the server is up or not.
"""

from __future__ import annotations

import json
from pathlib import Path

S4_VERDICTS = ("PASS", "WEAK_PASS", "FAIL")
S4_CHECK_STATUS = ("PASS", "FAIL", "NOT_APPLICABLE")
SEVERITIES = ("minor", "major", "fatal")
CATEGORIES = {
    # category -> the artefact a pointer of that category must land in
    "statistics": "stat_recompute.json",
    "support": "support",
    "identification": "proofpath.json",
    "design": "",
    "other": "",
}


class PointerError(ValueError):
    pass


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve(document, pointer: str):
    """RFC 6901. `""` is the whole document; arrays accept indices."""
    if pointer in ("", "/"):
        return document
    if not pointer.startswith("/"):
        raise PointerError(f"pointer must start with '/': {pointer!r}")
    node = document
    for token in pointer.split("/")[1:]:
        token = _unescape(token)
        if isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError):
                raise PointerError(f"{pointer!r}: {token!r} is not an index of a {len(node)}-item list")
        elif isinstance(node, dict):
            if token not in node:
                raise PointerError(f"{pointer!r}: key {token!r} is absent")
            node = node[token]
        else:
            raise PointerError(f"{pointer!r}: cannot descend into {type(node).__name__}")
    return node


def split_pointer(pointer: str) -> tuple[str, str]:
    """`/a/b.json#/c` -> ('a/b.json', '/c'). A pointer with no fragment addresses the whole file."""
    if "#" in pointer:
        path, frag = pointer.split("#", 1)
    else:
        path, frag = pointer, ""
    return path.lstrip("/"), frag


def resolve_artefact(root: Path, pointer: str):
    rel, frag = split_pointer(pointer)
    if not rel:
        raise PointerError(f"{pointer!r} names no artefact")
    path = (root / rel).resolve()
    if root.resolve() not in path.parents and path != root.resolve():
        raise PointerError(f"{pointer!r} escapes the project root")
    if not path.is_file():
        raise PointerError(f"{pointer!r}: {rel} does not exist")
    document = json.loads(path.read_text(encoding="utf-8"))
    return path, resolve(document, frag)


def check_s4(root: Path, answer: dict) -> list[str]:
    """Return the reasons an S4 answer is inadmissible (empty list = admissible)."""
    problems: list[str] = []
    verdict = answer.get("verdict")
    if verdict not in S4_VERDICTS:
        problems.append(f"verdict {verdict!r} is not one of {S4_VERDICTS}")
    checks = answer.get("checks")
    if not isinstance(checks, list) or not checks:
        return problems + ["`checks` must be a non-empty list"]
    failed = set()
    for check in checks:
        cid = check.get("id")
        status = check.get("status")
        if status not in S4_CHECK_STATUS:
            problems.append(f"check {cid!r}: status {status!r} is not one of {S4_CHECK_STATUS}")
        if status == "FAIL":
            failed.add(cid)
        pointer = check.get("evidence_pointer")
        if not pointer:
            problems.append(f"check {cid!r}: no evidence_pointer")
            continue
        try:
            resolve_artefact(root, pointer)
        except (PointerError, json.JSONDecodeError) as exc:
            problems.append(f"check {cid!r}: {exc}")
    blocking = answer.get("blocking")
    if blocking is not None:
        if not isinstance(blocking, list):
            problems.append("`blocking` must be a list")
        else:
            unknown = [b for b in blocking if b not in {c.get("id") for c in checks}]
            if unknown:
                problems.append(f"`blocking` names checks that do not exist: {unknown}")
            not_failed = [b for b in blocking if b not in failed]
            if not_failed:
                problems.append(f"`blocking` names checks that did not fail: {not_failed}")
    if verdict == "PASS" and failed:
        problems.append(f"PASS with failed checks: {sorted(failed)}")
    return problems


def check_s7(root: Path, answer: dict) -> list[str]:
    """Return the reasons an S7 answer is inadmissible."""
    problems: list[str] = []
    verdict = answer.get("verdict")
    if verdict not in S4_VERDICTS:
        problems.append(f"verdict {verdict!r} is not one of {S4_VERDICTS}")
    objections = answer.get("objections")
    if not isinstance(objections, list):
        return problems + ["`objections` must be a list"]
    unresolved_fatal = 0
    for i, obj in enumerate(objections):
        label = f"objection {i}"
        severity = obj.get("severity")
        category = obj.get("category")
        if severity not in SEVERITIES:
            problems.append(f"{label}: severity {severity!r} is not one of {SEVERITIES}")
        if category not in CATEGORIES:
            problems.append(f"{label}: category {category!r} is not one of {tuple(CATEGORIES)}")
        if obj.get("resolvable") is False and severity in ("major", "fatal"):
            unresolved_fatal += 1
        pointer = obj.get("evidence_pointer")
        if not pointer:
            problems.append(f"{label}: no evidence_pointer")
            continue
        try:
            path, _ = resolve_artefact(root, pointer)
        except (PointerError, json.JSONDecodeError) as exc:
            problems.append(f"{label}: {exc}")
            continue
        required = CATEGORIES.get(category, "")
        if required and required not in str(path).replace("\\", "/"):
            problems.append(f"{label}: category {category!r} must point into {required}, "
                            f"not {path.name}")
    if verdict == "PASS" and unresolved_fatal:
        problems.append(f"PASS with {unresolved_fatal} unresolved major/fatal objection(s)")
    return problems
