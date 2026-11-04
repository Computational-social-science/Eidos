"""Local repair bookkeeping: sealed protocol, hash-bound receipts and derived states.

This verifies receipt integrity and lifecycle consistency, not the honesty of an
arbitrary evaluator or scientific truth. Nothing uploads, installs or restarts.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import os
import re
import stat
import sys
import uuid
import zipfile
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from framework.artifacts import atomic_output, output_lock
from framework.project_state import load_workspace

MAX_JSON = 1024 * 1024
MAX_ARTIFACT = 16 * MAX_JSON
ASSURANCE = (
    "Local receipt integrity; independent evaluator truth is a separate requirement"
)


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _encoded(value) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


@contextmanager
def _archive(body: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if any(
                i.flag_bits & 1
                or i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                for i in archive.infolist()
            ):
                raise ValueError("Encrypted/unsupported repair archive")
            yield archive
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error) as error:
        raise ValueError("Invalid repair archive: " + str(error)) from None


def _moment(value) -> float:
    if not isinstance(value, str):
        raise ValueError("Repair timestamp must be an aware ISO string")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("Repair timestamp requires a timezone")
    return stamp.timestamp()


def _rows(value) -> list[dict]:
    if (
        not isinstance(value, list)
        or len(value) > 1000
        or not all(isinstance(x, dict) for x in value)
    ):
        raise ValueError("Malformed repair evidence rows")
    return value


def _hex(value, count=64) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch("[0-9a-f]{" + str(count) + "}", value) is not None
    )


def _read(path: Path, limit=MAX_ARTIFACT) -> bytes:
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise ValueError("Symlinked repair input/state is unsupported")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Repair input is not a bounded regular file")
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError("Repair input exceeds size limit")
    return body


def _json(body: bytes) -> dict:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate repair JSON field")
            value[key] = item
        return value

    def nonfinite(value):
        raise ValueError("Nonfinite repair JSON value")

    try:
        value = json.loads(body, object_pairs_hook=pairs, parse_constant=nonfinite)
    except RecursionError:
        raise ValueError("Repair JSON nesting exceeds supported depth") from None
    if not isinstance(value, dict):
        raise ValueError("Repair JSON must be an object")
    return value


def _workspace(project: Path):
    project = project.resolve()
    if (project / ".eidos").resolve() != project / ".eidos":
        raise ValueError("Repair state must stay in its project")
    folder, config, _ = load_workspace(project)
    return folder, config


def _directory(project: Path, incident: str) -> Path:
    if not _hex(incident, 32):
        raise ValueError("Invalid incident ID")
    folder, _ = _workspace(project)
    target = folder / "incidents" / incident
    if target.resolve() != target:
        raise ValueError("Repair state escapes its selected project")
    return target


@contextmanager
def _locked(project: Path, incident: str):
    project = project.resolve()
    target = _directory(project, incident)
    # Every incident in a project shares this pin. Always take its lock before
    # the individual journal lock, including retries and closure.
    with output_lock(project / ".eidos/runtime-pin"):
        with output_lock(target):
            yield target


def _blob(folder: Path, digest: str) -> bytes:
    if not _hex(digest):
        raise ValueError("Invalid evidence digest")
    body = _read(folder / "blobs" / digest)
    if _sha(body) != digest:
        raise ValueError("Stored repair evidence changed")
    return body


def _store(folder: Path, body: bytes) -> str:
    digest = _sha(body)
    path = folder / "blobs" / digest
    if folder.resolve() != folder or path.parent.resolve() != path.parent:
        raise ValueError("Repair blob parent is redirected")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if _read(path) != body:
            raise ValueError("Existing repair blob differs") from None
    return digest


def _wheel(body: bytes) -> dict:
    with _archive(body) as archive:
        names = archive.namelist()
        metadata = [
            n for n in names if n.count("/") == 1 and n.endswith(".dist-info/METADATA")
        ]
        if len(names) > 5000 or len(set(names)) != len(names) or len(metadata) != 1:
            raise ValueError("Ambiguous wheel inventory")
        info = archive.getinfo(metadata[0])
        if info.file_size > MAX_JSON:
            raise ValueError("Oversized wheel metadata")
        value = BytesParser().parsebytes(archive.read(metadata[0]))
        if (
            len(value.get_all("Name", [])) != 1
            or len(value.get_all("Version", [])) != 1
        ):
            raise ValueError("Invalid wheel distribution identity")
        modules = {}
        expanded = info.file_size
        for name in names:
            if name.startswith("framework/") and name.endswith(".py"):
                expanded += archive.getinfo(name).file_size
                if expanded > MAX_ARTIFACT:
                    raise ValueError("Oversized SDK source")
                modules[name.removeprefix("framework/")] = _sha(archive.read(name))
    if not modules or not value["Name"] or not value["Version"]:
        raise ValueError("Wheel does not contain the qualified SDK namespace")
    return {
        "name": value["Name"],
        "version": value["Version"],
        "sdk_source_sha256": _sha(
            json.dumps(modules, sort_keys=True, separators=(",", ":")).encode()
        ),
        "sdk_module_count": len(modules),
    }


def _artifacts(receipt: dict, parent: Path) -> dict[str, bytes]:
    values = receipt.get("artifacts")
    if not isinstance(values, dict) or len(values) > 16:
        raise ValueError("Repair artifact inventory is invalid")
    result = {}
    for role, reference in values.items():
        if (
            not isinstance(role, str)
            or not re.fullmatch("[a-z][a-z0-9_]*", role)
            or not isinstance(reference, dict)
        ):
            raise ValueError("Invalid repair artifact role")
        name = reference.get("path")
        if (
            not isinstance(name, str)
            or not name
            or "\\" in name
            or ":" in name
            or PurePosixPath(name).is_absolute()
            or any(p in ("", ".", "..") for p in name.split("/"))
        ):
            raise ValueError("Repair artifact path must be relative without traversal")
        path = parent.joinpath(*PurePosixPath(name).parts)
        if not path.resolve().is_relative_to(parent.resolve()):
            raise ValueError("Repair artifact escapes its receipt directory")
        body = _read(path)
        if reference.get("sha256") != _sha(body):
            raise ValueError("Repair artifact hash differs")
        result[role] = body
    if sum(map(len, result.values())) > 64 * MAX_JSON:
        raise ValueError("Repair evidence batch is oversized")
    return result


def _origin(project: Path, policy: dict) -> bool:
    files = policy.get("origin_files")
    if not isinstance(files, dict) or not 1 <= len(files) <= 32:
        raise ValueError("Repair protocol must declare bounded project origin inputs")
    if _sha(_encoded(files)) != policy.get("origin_sha256"):
        raise ValueError("Repair origin inventory digest differs")
    for name, digest in files.items():
        if (
            not isinstance(name, str)
            or not name
            or "\\" in name
            or ":" in name
            or PurePosixPath(name).is_absolute()
            or any(p in ("", ".", "..") for p in name.split("/"))
            or not _hex(digest)
        ):
            raise ValueError("Repair origin paths/digests are invalid")
        path = project.joinpath(*PurePosixPath(name).parts)
        if not path.resolve().is_relative_to(project):
            raise ValueError("Origin input escapes project")
        try:
            current = _sha(_read(path))
        except OSError:
            return False
        if current != digest:
            return False
    return True


def _check(context: dict, artifacts: dict, passed: bool, *, stage: str, baseline=False):
    check = _json(artifacts["check"])
    if (
        check.get("schema") != "eidos.repair-check.v1"
        or check.get("project_id") != context["project_id"]
        or check.get("protocol_sha256") != context["protocol_sha256"]
        or check.get("artifact_sha256") != _sha(artifacts["wheel"])
    ):
        raise ValueError(
            "Repair check belongs to a different protocol/project/artifact"
        )
    when = _moment(check.get("recorded_at"))
    if (
        not _hex(check.get("run_id"), 32)
        or check["run_id"] in context["used_runs"]
        or check.get("stage") != stage
        or check.get("origin_sha256") != context["protocol"]["origin_sha256"]
        or when < context["last_event_at"]
        or when > context["event_at"] + 30
    ):
        raise ValueError(
            "Repair execution is reused, stale or belongs to another stage/origin"
        )
    checks = check.get("checks")
    required = context["protocol"]["required_checks"]
    if not isinstance(checks, dict) or set(checks) != set(required):
        raise ValueError("Repair check inventory differs from sealed protocol")
    for row in checks.values():
        if (
            not isinstance(row, dict)
            or row.get("executed") is not True
            or row.get("status") not in ("PASS", "FAIL")
        ):
            raise ValueError("An unexecuted or unknown check is not repair evidence")
    actual = all(row["status"] == "PASS" for row in checks.values())
    if actual != passed:
        raise ValueError("Repair result does not meet the requested transition")
    if passed and check.get("fault_injection"):
        raise ValueError("Injected controls cannot qualify a successful repair/replay")
    if baseline and (
        checks[context["protocol"]["regression_check"]]["status"] != "FAIL"
        or any(
            row["status"] != "PASS"
            for key, row in checks.items()
            if key != context["protocol"]["regression_check"]
        )
    ):
        raise ValueError("Baseline defect was not isolated from unaffected controls")
    context["used_runs"].append(check["run_id"])


def _pin(pin: dict, context: dict, identity: dict) -> None:
    if (
        pin.get("schema") != "eidos.project-runtime-pin.v1"
        or pin.get("project_id") != context["project_id"]
        or pin.get("incident_id") != context["incident_id"]
        or pin.get("artifact_sha256") != context["candidate_sha256"]
        or pin.get("version") != identity["version"]
        or pin.get("sdk_source_sha256") != identity["sdk_source_sha256"]
        or pin.get("sdk_module_count") != identity["sdk_module_count"]
        or not _hex(pin.get("distributions_sha256"))
        or not isinstance(pin.get("python"), str)
        or not Path(pin["python"]).is_absolute()
        or not isinstance(pin.get("prefix"), str)
        or not Path(pin["prefix"]).is_absolute()
    ):
        raise ValueError(
            "Project runtime pin is incomplete or bound to another release"
        )
    _moment(pin.get("adopted_at"))


def _configuration(project: Path, journal: dict, context: dict) -> None:
    if (
        _sha(_read(project.resolve() / ".eidos/project.yaml", MAX_JSON))
        != journal["configuration_sha256"]
    ):
        raise ValueError("Incident project configuration changed")
    if not _origin(project.resolve(), context["protocol"]):
        raise ValueError("Incident project origin inputs changed")


def _history(project: Path) -> bytes:
    folder = project.resolve() / ".eidos/runs"
    files = (
        sorted(
            p for p in folder.iterdir() if re.fullmatch("[0-9a-f]{32}\\.json", p.name)
        )
        if folder.exists()
        else []
    )
    if len(files) > 10000:
        raise ValueError("Run history is too large for this rollback profile")
    return _encoded({p.name: _sha(_read(p)) for p in files if p.is_file()})


def _publication(context: dict, artifacts: dict, identity: dict, digest: str) -> dict:
    proof = _json(artifacts["publication"])
    if (
        proof.get("schema") != "eidos.release-proof.v1"
        or proof.get("published") is not True
        or proof.get("artifact_sha256") != digest
        or proof.get("version") != identity["version"]
        or not _hex(proof.get("head_commit"), 40)
        or not _hex(proof.get("source_commit"), 40)
        or proof.get("ci_head") != proof["head_commit"]
        or proof.get("ci_conclusion") != "success"
        or proof.get("tag") != "v" + identity["version"]
    ):
        raise ValueError(
            "Publication/CI evidence is missing or bound to another release"
        )
    release = _json(artifacts["release"])
    ci = _json(artifacts["ci"])
    tag = _json(artifacts["tag"])
    if release.get("tag_name") != proof["tag"] or release.get("draft") is not False:
        raise ValueError("The release is not published at the intended tag")
    assets = [
        row
        for row in _rows(release.get("assets", []))
        if row.get("name") == proof.get("asset_name")
    ]
    if (
        len(assets) != 1
        or assets[0].get("digest") != "sha256:" + digest
        or assets[0].get("size") != len(artifacts["wheel"])
    ):
        raise ValueError("Published release asset differs from the accepted wheel")
    required = context["protocol"].get("ci_workflows")
    if not isinstance(required, list) or not required:
        raise ValueError("The sealed protocol must name required remote CI workflows")
    for name in required:
        runs = [
            row
            for row in _rows(ci.get("workflow_runs", []))
            if row.get("name") == name and row.get("head_sha") == proof["head_commit"]
        ]
        if not runs or any(
            type(row.get("id")) is not int or type(row.get("run_attempt", 1)) is not int
            for row in runs
        ):
            raise ValueError("Required exact-head CI execution is missing")
        latest = max(runs, key=lambda row: (row["id"], row.get("run_attempt", 1)))
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise ValueError("Required exact-head CI has not succeeded")
    ref = tag.get("ref", {})
    if not isinstance(ref, dict) or not isinstance(ref.get("object"), dict):
        raise ValueError("Malformed tag reference")
    if ref.get("ref") != "refs/tags/" + proof["tag"]:
        raise ValueError("Release tag reference differs")
    target = ref.get("object", {})
    if target.get("type") == "tag":
        annotation = tag.get("annotation", {})
        if not isinstance(annotation, dict) or not isinstance(
            annotation.get("object"), dict
        ):
            raise ValueError("Malformed tag annotation")
        if (
            annotation.get("sha") != target.get("sha")
            or annotation.get("tag") != proof["tag"]
        ):
            raise ValueError("Annotated tag identity differs")
        target = annotation.get("object", {})
    if target.get("type") != "commit" or target.get("sha") != proof["head_commit"]:
        raise ValueError("Published tag does not identify the accepted delivery commit")
    return proof


def _advance(context: dict, receipt: dict, artifacts: dict) -> None:
    kind = receipt["kind"]
    state = context["state"]
    details = receipt.get("details")
    if not isinstance(details, dict):
        raise ValueError("Repair receipt details must be an object")
    allowed = {
        "triage": ("DETECTED",),
        "reproduction": ("TRIAGED",),
        "candidate": ("REPRODUCED", "ROLLED_BACK"),
        "rejection": ("CANDIDATE",),
        "validation": ("CANDIDATE",),
        "rollback": ("REJECTED",),
        "release": ("VALIDATED",),
        "adoption": ("RELEASED", "REVERTED"),
        "replay": ("ADOPTED",),
        "reversion": ("ADOPTED", "REPLAY_FAILED"),
    }
    if kind not in allowed or state not in allowed[kind]:
        raise ValueError("Repair transition is out of order")
    if kind == "triage":
        if details.get("classification") not in (
            "core",
            "environment",
            "downstream",
            "unknown",
            "scientific_negative",
            "unsupported",
        ):
            raise ValueError("Unknown incident classification")
        context.update(state="TRIAGED", classification=details["classification"])
        return
    if kind == "reproduction":
        if context.get("classification") not in ("core", "environment", "downstream"):
            raise ValueError(
                "Unattributed/non-software incident cannot enter a repair campaign"
            )
        _wheel(artifacts["wheel"])
        _check(context, artifacts, False, stage=kind, baseline=True)
        context.update(state="REPRODUCED", baseline_sha256=_sha(artifacts["wheel"]))
        return
    digest = _sha(artifacts["wheel"])
    identity = _wheel(artifacts["wheel"])
    if kind == "candidate":
        if digest == context["baseline_sha256"] or digest in context["rejected"]:
            raise ValueError(
                "Baseline or rejected artifact cannot become a new candidate"
            )
        context.update(
            state="CANDIDATE", candidate_sha256=digest, version=identity["version"]
        )
        return
    if kind == "rollback":
        before = _json(artifacts["pin_before"])
        after = _json(artifacts["pin_after"])
        if (
            digest != context["baseline_sha256"]
            or before.get("project_id") != context["project_id"]
            or after.get("project_id") != context["project_id"]
            or before.get("artifact_sha256") != context["candidate_sha256"]
            or after.get("artifact_sha256") != digest
            or artifacts["history_before"] != artifacts["history_after"]
        ):
            raise ValueError(
                "Rollback did not restore the baseline and preserve history"
            )
        _check(context, artifacts, False, stage=kind, baseline=True)
        context["rolled_back"].append(context["candidate_sha256"])
        context["state"] = "ROLLED_BACK"
        return
    if digest != context["candidate_sha256"]:
        raise ValueError("Receipt refers to another candidate")
    if kind == "adoption":
        pin = _json(artifacts["pin_after"])
        _pin(pin, context, identity)
        if type(details.get("prior_pin_existed")) is not bool or (
            not details["prior_pin_existed"] and artifacts["pin_before"] != b""
        ):
            raise ValueError("Prior pin existence must be preserved explicitly")
        if _moment(pin["adopted_at"]) < context["last_event_at"]:
            raise ValueError("Adoption predates the required lifecycle stage")
        context.update(
            state="ADOPTED",
            pin_sha256=_sha(artifacts["pin_after"]),
            pin=pin,
            prior_pin_sha256=_sha(artifacts["pin_before"]),
            history_sha256=_sha(artifacts["history"]),
            prior_pin_existed=details["prior_pin_existed"],
        )
        return
    if kind == "reversion":
        if (
            _sha(artifacts["pin_after"]) != context["prior_pin_sha256"]
            or _sha(artifacts["history_before"]) != context["history_sha256"]
        ):
            raise ValueError(
                "Reversion does not restore the actual pre-adoption pin/history"
            )
        before = _json(artifacts["history_before"])
        after = _json(artifacts["history_after"])
        if any(after.get(key) != value for key, value in before.items()):
            raise ValueError("Reversion lost or changed existing run history")
        context["state"] = "REVERTED"
        return
    if kind in ("rejection", "validation", "replay"):
        passed = kind != "rejection"
        if kind == "replay":
            pin = _json(artifacts["pin_after"])
            _pin(pin, context, identity)
            check = _json(artifacts["check"])
            passed = all(
                row.get("status") == "PASS"
                for row in check.get("checks", {}).values()
                if isinstance(row, dict)
            )
            if (
                _sha(artifacts["pin_after"]) != context["pin_sha256"]
                or check.get("pin_sha256") != context["pin_sha256"]
                or _moment(check.get("recorded_at")) < _moment(pin["adopted_at"])
            ):
                raise ValueError(
                    "Replay is not a fresh execution after the actual project adoption"
                )
        _check(context, artifacts, passed, stage=kind)
        if kind == "rejection":
            context["rejected"].append(digest)
            context["state"] = "REJECTED"
        elif kind == "validation":
            context["state"] = "VALIDATED"
        else:
            context.update(state="REPLAYED" if passed else "REPLAY_FAILED")
        return
    proof = _publication(context, artifacts, identity, digest)
    context.update(state="RELEASED", publication=proof)


def _load(project: Path, incident: str):
    folder = _directory(project, incident)
    journal = _json(_read(folder / "journal.json", MAX_JSON))
    return _validate_journal(project, incident, folder, journal)


def _validate_journal(project: Path, incident: str, folder: Path, journal: dict):
    _, config = _workspace(project)
    if (
        journal.get("schema") != "eidos.incident-journal.v1"
        or journal.get("incident_id") != incident
        or journal.get("project_id") != config["project_id"]
        or journal.get("project_root") != str(project.resolve())
    ):
        raise ValueError("Incident belongs to a different project")
    if not _hex(journal.get("protocol_sha256")) or not _hex(
        journal.get("configuration_sha256")
    ):
        raise ValueError("Incident genesis digest is invalid")
    policy = _json(_blob(folder, journal["protocol_sha256"]))
    context = dict(
        project_id=config["project_id"],
        incident_id=incident,
        protocol_sha256=journal["protocol_sha256"],
        protocol=policy,
        state="DETECTED",
        rejected=[],
        rolled_back=[],
        used_runs=[],
        last_event_at=0.0,
    )
    events = journal.get("events")
    previous = None
    if not isinstance(events, list) or not 1 <= len(events) <= 256:
        raise ValueError("Invalid incident event inventory")
    for number, event in enumerate(events):
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("artifacts"), dict)
            or not isinstance(event.get("kind"), str)
            or not _hex(event.get("receipt_sha256"))
        ):
            raise ValueError("Invalid incident event shape")
        context["event_at"] = _moment(event.get("recorded_at"))
        raw = {k: v for k, v in event.items() if k != "sha256"}
        if (
            event.get("sequence") != number
            or event.get("previous_sha256") != previous
            or _sha(_encoded(raw)) != event.get("sha256")
        ):
            raise ValueError("Incident event chain changed")
        receipt = _json(_blob(folder, event["receipt_sha256"]))
        if (
            receipt.get("schema") != "eidos.repair-receipt.v1"
            or receipt.get("project_id") != config["project_id"]
            or receipt.get("incident_id") != incident
            or receipt.get("protocol_sha256") != journal["protocol_sha256"]
            or receipt.get("kind") != event["kind"]
        ):
            raise ValueError("Incident receipt identity changed")
        if (
            not isinstance(receipt.get("artifacts"), dict)
            or not isinstance(receipt.get("details"), dict)
            or not all(
                isinstance(ref, dict) and _hex(ref.get("sha256"))
                for ref in receipt["artifacts"].values()
            )
        ):
            raise ValueError("Invalid stored receipt shape")
        artifacts = {
            role: _blob(folder, digest) for role, digest in event["artifacts"].items()
        }
        if event["artifacts"] != {
            role: reference["sha256"]
            for role, reference in receipt["artifacts"].items()
        }:
            raise ValueError("Event artifact inventory differs from its receipt")
        if number == 0:
            if (
                event["kind"] != "create"
                or receipt["details"].get("configuration_sha256")
                != journal["configuration_sha256"]
                or receipt["details"].get("project_root") != journal["project_root"]
            ):
                raise ValueError("Invalid incident genesis")
        elif event["kind"] == "close":
            _can_close(context)
            if receipt["details"].get("pin_sha256") != context["pin_sha256"]:
                raise ValueError("Closure pin differs from adopted replay")
            context.update(state="CLOSED", pin_sha256=receipt["details"]["pin_sha256"])
        else:
            _advance(context, receipt, artifacts)
        context["last_event_at"] = context["event_at"]
        previous = event["sha256"]
    return folder, journal, context


def _append(folder: Path, journal: dict, receipt: dict, artifacts: dict) -> None:
    refs = {role: _store(folder, body) for role, body in artifacts.items()}
    event = {
        "sequence": len(journal["events"]),
        "previous_sha256": journal["events"][-1]["sha256"]
        if journal["events"]
        else None,
        "kind": receipt["kind"],
        "receipt_sha256": _store(folder, _encoded(receipt)),
        "artifacts": refs,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    event["sha256"] = _sha(_encoded(event))
    journal["events"].append(event)
    body = _encoded(journal)
    if len(body) > MAX_JSON or len(journal["events"]) > 256:
        raise ValueError("Incident journal limit reached")
    # Writers and readers use exactly one validation path. Rejected/malformed
    # input may leave unreferenced blobs, but cannot poison the committed head.
    _validate_journal(folder.parents[2], folder.name, folder, journal)
    with atomic_output(folder / "journal.json") as temporary:
        temporary.write_bytes(body)


def _can_close(context):
    if context["state"] != "REPLAYED":
        raise ValueError("Release and originating-project replay are required")
    if context["protocol"].get("require_rejection_control") and (
        not context["rejected"]
        or set(context["rejected"]) != set(context["rolled_back"])
    ):
        raise ValueError(
            "Qualification requires rejected-candidate and actual rollback controls"
        )


def create(
    project: Path, message: str, protocol: Path, *, feedback_bundle: Path | None = None
) -> dict:
    project = project.resolve()
    folder, config = _workspace(project)
    body = _read(protocol, MAX_JSON)
    policy = _json(body)
    checks = policy.get("required_checks")
    if (
        policy.get("schema") != "eidos.repair-protocol.v1"
        or policy.get("project_id") != config["project_id"]
        or not isinstance(policy.get("scope"), str)
        or not policy["scope"].strip()
        or not isinstance(checks, list)
        or not checks
        or len(checks) > 32
        or not all(
            isinstance(x, str) and re.fullmatch("[a-z][a-z0-9_]*", x) for x in checks
        )
        or len(set(checks)) != len(checks)
        or not _hex(policy.get("origin_sha256"))
        or policy.get("regression_check") not in checks
        or type(policy.get("require_rejection_control", False)) is not bool
        or not message.strip()
    ):
        raise ValueError("Invalid sealed repair protocol")
    if not _origin(project, policy):
        raise ValueError("Origin inputs differ from the selected repair protocol")
    incident = uuid.uuid4().hex
    export = None
    if feedback_bundle is not None:
        export = _read(feedback_bundle, MAX_JSON)
        with _archive(export) as archive:
            if sorted(archive.namelist()) != ["feedback.json", "manifest.json"] or any(
                i.file_size > MAX_JSON for i in archive.infolist()
            ):
                raise ValueError("Invalid feedback export inventory")
            metadata_body = archive.read("feedback.json")
            metadata = _json(metadata_body)
            manifest = _json(archive.read("manifest.json"))
        if (
            metadata.get("schema") != "eidos.feedback.v1"
            or metadata.get("project_id") != config["project_id"]
            or not _hex(metadata.get("incident_id"), 32)
            or manifest.get("schema") != "eidos.feedback-manifest.v1"
            or manifest.get("files") != {"feedback.json": _sha(metadata_body)}
        ):
            raise ValueError("Feedback export is corrupt or belongs to another project")
        incident = metadata["incident_id"]
    target = _directory(project, incident)
    target.mkdir(parents=True, exist_ok=False)
    protocol_digest = _store(target, body)
    configuration = _sha(_read(folder / "project.yaml", MAX_JSON))
    journal = {
        "schema": "eidos.incident-journal.v1",
        "incident_id": incident,
        "project_id": config["project_id"],
        "project_root": str(project),
        "protocol_sha256": protocol_digest,
        "configuration_sha256": configuration,
        "events": [],
    }
    receipt = {
        "schema": "eidos.repair-receipt.v1",
        "incident_id": incident,
        "project_id": config["project_id"],
        "protocol_sha256": protocol_digest,
        "kind": "create",
        "artifacts": {
            "protocol": {"path": "sealed-protocol.json", "sha256": protocol_digest}
        },
        "details": {
            "message": message,
            "configuration_sha256": configuration,
            "project_root": str(project),
        },
    }
    artifacts = {"protocol": body}
    if export is not None:
        receipt["artifacts"]["feedback_export"] = {
            "path": "feedback.zip",
            "sha256": _sha(export),
        }
        artifacts["feedback_export"] = export
    with output_lock(target):
        _append(target, journal, receipt, artifacts)
    return status(project, incident)


def record(project: Path, incident: str, evidence: Path) -> dict:
    project = project.resolve()
    with _locked(project, incident):
        folder, journal, context = _load(project, incident)
        _configuration(project, journal, context)
        receipt = _json(_read(evidence, MAX_JSON))
        if (
            receipt.get("schema") != "eidos.repair-receipt.v1"
            or receipt.get("project_id") != journal["project_id"]
            or receipt.get("incident_id") != incident
            or receipt.get("protocol_sha256") != journal["protocol_sha256"]
        ):
            raise ValueError("Repair receipt identity differs")
        if receipt.get("kind") in ("create", "adoption", "reversion", "close"):
            raise ValueError("This lifecycle step requires its dedicated operation")
        artifacts = _artifacts(receipt, evidence.absolute().parent)
        if receipt.get("kind") == "replay" and _read(
            project / ".eidos/runtime-pin.json", MAX_JSON
        ) != artifacts.get("pin_after"):
            raise ValueError(
                "Project runtime changed since the replay evidence was recorded"
            )
        context["event_at"] = datetime.now(timezone.utc).timestamp()
        try:
            _advance(context, receipt, artifacts)
        except KeyError as error:
            raise ValueError(
                "Required repair artifact is missing: " + str(error)
            ) from None
        _append(folder, journal, receipt, artifacts)
    return status(project, incident)


def _runtime_matches(wheel: bytes) -> bool:
    from framework.worker_observation import sdk_source_identity

    try:
        identity = _wheel(wheel)
        distribution = importlib.metadata.distribution(identity["name"])
        direct = _json((distribution.read_text("direct_url.json") or "{}").encode())
        return (
            Path(__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
            and isinstance(direct.get("dir_info", {}), dict)
            and not direct.get("dir_info", {}).get("editable")
            and Path(distribution.locate_file("framework/feedback.py")).resolve()
            == Path(__file__).resolve()
            and distribution.version == identity["version"]
            and sdk_source_identity()
            == {k: identity[k] for k in ("sdk_source_sha256", "sdk_module_count")}
        )
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
        return False


def _pin_runtime(pin: dict, wheel: bytes, context: dict) -> bool:
    from framework.project_state import runtime_identity

    _pin(pin, context, _wheel(wheel))
    return (
        Path(pin["python"]).is_file()
        and Path(os.path.abspath(pin["python"]))
        == Path(os.path.abspath(sys.executable))
        and Path(pin["prefix"]).resolve() == Path(sys.prefix).resolve()
        and runtime_identity()["distributions_sha256"] == pin["distributions_sha256"]
        and _runtime_matches(wheel)
    )


def status(project: Path, incident: str) -> dict:
    with _locked(project, incident):
        return _status(project, incident)


def _status(project: Path, incident: str) -> dict:
    folder, journal, context = _load(project.resolve(), incident)
    historical = context["state"]
    stale = (
        _sha(_read(project.resolve() / ".eidos/project.yaml", MAX_JSON))
        != journal["configuration_sha256"]
    )
    stale = stale or not _origin(project.resolve(), context["protocol"])
    if historical == "CLOSED":
        try:
            pin = _read(project.resolve() / ".eidos/runtime-pin.json", MAX_JSON)
            stale = (
                stale
                or _sha(pin) != context["pin_sha256"]
                or not _pin_runtime(
                    _json(pin), _blob(folder, context["candidate_sha256"]), context
                )
            )
        except FileNotFoundError:
            stale = True
    elif historical in ("ADOPTED", "REPLAYED", "REPLAY_FAILED", "REVERTED"):
        path = project.resolve() / ".eidos/runtime-pin.json"
        try:
            actual = _read(path, MAX_JSON)
        except FileNotFoundError:
            actual = None
        expected = (
            _blob(folder, context["prior_pin_sha256"])
            if historical == "REVERTED" and context["prior_pin_existed"]
            else None
        )
        if historical != "REVERTED":
            expected = _blob(folder, context["pin_sha256"])
        stale = stale or actual != expected
    return {
        "status": "STALE" if stale else "PASS",
        "state": "STALE" if stale else historical,
        "historical_state": historical,
        "incident_id": incident,
        "project_id": context["project_id"],
        "events": len(journal["events"]),
        "head_sha256": journal["events"][-1]["sha256"],
        "candidate_sha256": context.get("candidate_sha256"),
        "assurance": ASSURANCE,
        "scientific_status": "UNRUN",
    }


def adopt(project: Path, incident: str, python: Path) -> dict:
    from framework.monitor_registry import query_worker

    with _locked(project, incident):
        folder, journal, context = _load(project.resolve(), incident)
        _configuration(project, journal, context)
        if context["state"] not in ("RELEASED", "REVERTED", "ADOPTED"):
            raise ValueError("Only a published validated candidate may be adopted")
        path = project.resolve() / ".eidos/runtime-pin.json"
        if context["state"] == "REVERTED":
            try:
                actual = _read(path, MAX_JSON)
            except FileNotFoundError:
                actual = None
            prior = (
                _blob(folder, context["prior_pin_sha256"])
                if context["prior_pin_existed"]
                else None
            )
            if actual != prior:
                raise ValueError("Complete the pending reversion before adopting again")
        identity = _wheel(_blob(folder, context["candidate_sha256"]))
        observed = query_worker(project.resolve(), python)
        worker = observed["worker"]
        if (
            worker["installation_mode"] != "installed"
            or worker["eidos_version"] != identity["version"]
            or any(
                worker[key] != identity[key]
                for key in ("sdk_source_sha256", "sdk_module_count")
            )
        ):
            raise ValueError("Selected worker differs from the released SDK")
        _configuration(project, journal, context)
        if context["state"] == "ADOPTED":
            pin_body = _blob(folder, context["pin_sha256"])
            pin = _json(pin_body)
            if Path(pin["python"]) != Path(os.path.abspath(python)):
                raise ValueError("Adoption retry targets another worker")
            if (
                Path(worker["prefix"]).resolve() != Path(pin["prefix"]).resolve()
                or worker["distributions_sha256"] != pin["distributions_sha256"]
            ):
                raise ValueError(
                    "Adoption retry observed a different runtime/dependency identity"
                )
            try:
                actual = _read(path, MAX_JSON)
            except FileNotFoundError:
                actual = None
            prior = (
                _blob(folder, context["prior_pin_sha256"])
                if context["prior_pin_existed"]
                else None
            )
            if actual not in (pin_body, prior):
                raise ValueError("Adoption retry must not overwrite an unrelated pin")
            with atomic_output(path) as temporary:
                temporary.write_bytes(pin_body)
            return {
                "status": "PASS",
                "state": "ADOPTED",
                "incident_id": incident,
                "pin": pin,
                "scientific_status": "UNRUN",
            }
        try:
            prior = _read(path, MAX_JSON)
            prior_exists = True
        except FileNotFoundError:
            prior = b""
            prior_exists = False
        pin = {
            "schema": "eidos.project-runtime-pin.v1",
            "project_id": journal["project_id"],
            "incident_id": incident,
            "artifact_sha256": context["candidate_sha256"],
            "version": identity["version"],
            "python": str(Path(os.path.abspath(python))),
            "sdk_source_sha256": identity["sdk_source_sha256"],
            "prefix": worker["prefix"],
            "sdk_module_count": identity["sdk_module_count"],
            "distributions_sha256": worker["distributions_sha256"],
            "adopted_at": datetime.now(timezone.utc).isoformat(),
        }
        artifacts = {
            "wheel": _blob(folder, context["candidate_sha256"]),
            "pin_after": _encoded(pin),
            "pin_before": prior,
            "history": _history(project),
        }
        receipt = {
            "schema": "eidos.repair-receipt.v1",
            "project_id": journal["project_id"],
            "incident_id": incident,
            "protocol_sha256": journal["protocol_sha256"],
            "kind": "adoption",
            "details": {"prior_pin_existed": prior_exists},
            "artifacts": {
                role: {"path": role + ".data", "sha256": _sha(body)}
                for role, body in artifacts.items()
            },
        }
        context["event_at"] = datetime.now(timezone.utc).timestamp()
        _advance(context, receipt, artifacts)
        # Commit intent and previous bytes first. A failed pin publication is
        # visible as STALE and can be retried without losing the old pin.
        _append(folder, journal, receipt, artifacts)
        with atomic_output(path) as temporary:
            temporary.write_bytes(artifacts["pin_after"])
    return {
        "status": "PASS",
        "state": "ADOPTED",
        "incident_id": incident,
        "pin": pin,
        "scientific_status": "UNRUN",
    }


def close(project: Path, incident: str) -> dict:
    with _locked(project, incident):
        folder, journal, context = _load(project.resolve(), incident)
        _can_close(context)
        _configuration(project, journal, context)
        pin = _read(project.resolve() / ".eidos/runtime-pin.json", MAX_JSON)
        if _sha(pin) != context["pin_sha256"] or not _pin_runtime(
            _json(pin), _blob(folder, context["candidate_sha256"]), context
        ):
            raise ValueError(
                "Closure requires the originating project pin and actual installed released SDK"
            )
        receipt = {
            "schema": "eidos.repair-receipt.v1",
            "project_id": journal["project_id"],
            "incident_id": incident,
            "protocol_sha256": journal["protocol_sha256"],
            "kind": "close",
            "artifacts": {},
            "details": {"pin_sha256": _sha(pin)},
        }
        _append(folder, journal, receipt, {})
    return status(project.resolve(), incident)


def revert(project: Path, incident: str) -> dict:
    """Restore the actual pre-adoption pin; preserve all existing run records."""
    project = project.resolve()
    with _locked(project, incident):
        folder, journal, context = _load(project, incident)
        _configuration(project, journal, context)
        if context["state"] not in ("ADOPTED", "REPLAY_FAILED", "REVERTED"):
            raise ValueError("No pending/failed adopted runtime can be reverted")
        path = project / ".eidos/runtime-pin.json"
        try:
            actual = _read(path, MAX_JSON)
        except FileNotFoundError:
            actual = None
        prior = (
            _blob(folder, context["prior_pin_sha256"])
            if context["prior_pin_existed"]
            else None
        )
        adopted = _blob(folder, context["pin_sha256"])
        if actual not in (adopted, prior):
            raise ValueError("Current pin was changed outside this adoption")
        if context["state"] == "REVERTED":
            if prior is None:
                path.unlink(missing_ok=True)
            else:
                with atomic_output(path) as temporary:
                    temporary.write_bytes(prior)
            return status(project, incident)
        before = _blob(folder, context["history_sha256"])
        after = _history(project)
        artifacts = {
            "wheel": _blob(folder, context["candidate_sha256"]),
            "pin_after": prior if prior is not None else b"",
            "history_before": before,
            "history_after": after,
        }
        receipt = {
            "schema": "eidos.repair-receipt.v1",
            "project_id": journal["project_id"],
            "incident_id": incident,
            "protocol_sha256": journal["protocol_sha256"],
            "kind": "reversion",
            "details": {},
            "artifacts": {
                role: {"path": role + ".data", "sha256": _sha(body)}
                for role, body in artifacts.items()
            },
        }
        context["event_at"] = datetime.now(timezone.utc).timestamp()
        _advance(context, receipt, artifacts)
        _append(folder, journal, receipt, artifacts)
        if prior is None:
            path.unlink(missing_ok=True)
        else:
            with atomic_output(path) as temporary:
                temporary.write_bytes(prior)
    return status(project, incident)
