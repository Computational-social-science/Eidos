"""A status label alone cannot close a repair; artifacts and identities must bind."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.cli import main as cli


def sha(body):
    return hashlib.sha256(body).hexdigest()


@pytest.fixture
def case(tmp_path):
    from framework import feedback

    project = tmp_path / "study"
    assert cli(["init", "--project", str(project), "--json"]) == 0
    project_id = __import__("yaml").safe_load(
        (project / ".eidos/project.yaml").read_text()
    )["project_id"]
    origin = {".eidos/validate.py": sha((project / ".eidos/validate.py").read_bytes())}
    origin_digest = sha(
        (json.dumps(origin, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    protocol = {
        "schema": "eidos.repair-protocol.v1",
        "project_id": project_id,
        "scope": "Private software lifecycle qualification",
        "required_checks": ["pipe", "unaffected"],
        "regression_check": "pipe",
        "require_rejection_control": True,
        "ci_workflows": ["ci"],
        "origin_sha256": origin_digest,
        "origin_files": origin,
    }
    source = tmp_path / "evidence"
    source.mkdir()
    policy = source / "protocol.json"
    policy.write_text(json.dumps(protocol))
    created = feedback.create(project, "availability probe hangs", policy)
    return (
        feedback,
        project,
        project_id,
        source,
        created["incident_id"],
        sha(policy.read_bytes()),
    )


def receipt(case, kind, *, artifacts=None, **details):
    feedback, project, project_id, source, incident, protocol = case
    refs = {}
    for role, value in (artifacts or {}).items():
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        name = role + "-" + sha(body)[:12] + ".data"
        (source / name).write_bytes(body)
        refs[role] = {"path": name, "sha256": sha(body)}
    value = {
        "schema": "eidos.repair-receipt.v1",
        "incident_id": incident,
        "project_id": project_id,
        "protocol_sha256": protocol,
        "kind": kind,
        "artifacts": refs,
        "details": details,
    }
    path = source / (kind + ".json")
    path.write_text(json.dumps(value))
    return path


def wheel(version, code=b"pass\n"):
    import io

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            f"eidos-{version}.dist-info/METADATA",
            f"Name: eidos\nVersion: {version}\n\n",
        )
        archive.writestr("framework/feedback.py", code)
    return stream.getvalue()


def result(case, artifact, ok, stage=None):
    return {
        "schema": "eidos.repair-check.v1",
        "project_id": case[2],
        "protocol_sha256": case[5],
        "artifact_sha256": sha(artifact),
        "run_id": uuid.uuid4().hex,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage or ("validation" if ok else "reproduction"),
        "origin_sha256": json.loads((case[3] / "protocol.json").read_text())[
            "origin_sha256"
        ],
        "checks": {
            "pipe": {"executed": True, "status": "PASS" if ok else "FAIL"},
            "unaffected": {"executed": True, "status": "PASS"},
        },
    }


def begin(case):
    f, p, _, _, i, _ = case
    f.record(p, i, receipt(case, "triage", classification="core"))
    baseline = wheel("0.4.12")
    f.record(
        p,
        i,
        receipt(
            case,
            "reproduction",
            artifacts={"wheel": baseline, "check": result(case, baseline, False)},
        ),
    )
    return baseline


def test_cannot_skip_from_detected_to_validation(case):
    f, p, _, _, i, _ = case
    candidate = wheel("0.5.0")
    with pytest.raises(ValueError):
        f.record(
            p,
            i,
            receipt(
                case,
                "validation",
                artifacts={"wheel": candidate, "check": result(case, candidate, True)},
            ),
        )
    assert f.status(p, i)["state"] == "DETECTED"


def test_failed_candidate_cannot_be_validated(case):
    f, p, _, _, i, _ = case
    begin(case)
    bad = wheel("0.5.0.dev0")
    f.record(p, i, receipt(case, "candidate", artifacts={"wheel": bad}))
    f.record(
        p,
        i,
        receipt(
            case,
            "rejection",
            artifacts={"wheel": bad, "check": result(case, bad, False, "rejection")},
        ),
    )
    with pytest.raises(ValueError):
        f.record(
            p,
            i,
            receipt(
                case,
                "validation",
                artifacts={"wheel": bad, "check": result(case, bad, True)},
            ),
        )
    assert f.status(p, i)["state"] == "REJECTED"


def test_wrong_project_and_protocol_refused(case):
    f, p, _, _, i, _ = case
    path = receipt(case, "triage", classification="core")
    value = json.loads(path.read_text())
    value["project_id"] = "f" * 32
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        f.record(p, i, path)
    value["project_id"] = case[2]
    value["protocol_sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        f.record(p, i, path)


def test_tampered_stored_evidence_withdraws_state(case):
    f, p, _, _, i, _ = case
    f.record(p, i, receipt(case, "triage", classification="core"))
    blob = next((p / ".eidos/incidents" / i / "blobs").iterdir())
    blob.write_bytes(b"changed")
    with pytest.raises(ValueError):
        f.status(p, i)


@pytest.mark.parametrize(
    "path", ["../outside", "/absolute", "C:/outside", "nested\\outside"]
)
def test_artifact_path_escape_refused(case, path):
    f, p, _, _, i, _ = case
    begin(case)
    candidate = receipt(case, "candidate")
    value = json.loads(candidate.read_text())
    value["artifacts"] = {"wheel": {"path": path, "sha256": "0" * 64}}
    candidate.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        f.record(p, i, candidate)


def test_configuration_change_is_stale(case):
    f, p, _, _, i, _ = case
    with (p / ".eidos/project.yaml").open("a") as stream:
        stream.write("\n# changed protocol context\n")
    assert f.status(p, i)["state"] == "STALE"
    with pytest.raises(ValueError):
        f.record(p, i, receipt(case, "triage", classification="core"))


def test_close_without_release_replay_and_rollback_refused(case):
    f, p, _, _, i, _ = case
    begin(case)
    with pytest.raises(ValueError):
        f.close(p, i)


def test_rollback_must_preserve_actual_history_bytes(case):
    f, p, _, _, i, _ = case
    base = begin(case)
    bad = wheel("0.5.0.dev0")
    f.record(p, i, receipt(case, "candidate", artifacts={"wheel": bad}))
    f.record(
        p,
        i,
        receipt(
            case,
            "rejection",
            artifacts={"wheel": bad, "check": result(case, bad, False, "rejection")},
        ),
    )
    artifacts = {
        "wheel": base,
        "check": result(case, base, False, "rollback"),
        "history_before": b"old history",
        "history_after": b"changed history",
        "pin_before": {"project_id": case[2], "artifact_sha256": sha(bad)},
        "pin_after": {"project_id": case[2], "artifact_sha256": sha(base)},
    }
    with pytest.raises(ValueError):
        f.record(p, i, receipt(case, "rollback", artifacts=artifacts))
    assert f.status(p, i)["state"] == "REJECTED"


def publication(candidate):
    return {
        "schema": "eidos.release-proof.v1",
        "published": True,
        "artifact_sha256": sha(candidate),
        "version": "0.5.0",
        "source_commit": "a" * 40,
        "head_commit": "b" * 40,
        "ci_head": "b" * 40,
        "ci_conclusion": "success",
        "tag": "v0.5.0",
        "asset_name": "eidos-0.5.0-py3-none-any.whl",
    }


def validated(case):
    f, p, _, _, i, _ = case
    baseline = begin(case)
    bad = wheel("0.5.0.dev0")
    f.record(p, i, receipt(case, "candidate", artifacts={"wheel": bad}))
    f.record(
        p,
        i,
        receipt(
            case,
            "rejection",
            artifacts={"wheel": bad, "check": result(case, bad, False, "rejection")},
        ),
    )
    f.record(
        p,
        i,
        receipt(
            case,
            "rollback",
            artifacts={
                "wheel": baseline,
                "check": result(case, baseline, False, "rollback"),
                "history_before": b"preserved history",
                "history_after": b"preserved history",
                "pin_before": {"project_id": case[2], "artifact_sha256": sha(bad)},
                "pin_after": {"project_id": case[2], "artifact_sha256": sha(baseline)},
            },
        ),
    )
    candidate = wheel("0.5.0", b"corrected\n")
    f.record(p, i, receipt(case, "candidate", artifacts={"wheel": candidate}))
    f.record(
        p,
        i,
        receipt(
            case,
            "validation",
            artifacts={"wheel": candidate, "check": result(case, candidate, True)},
        ),
    )
    return candidate


def test_a_written_publication_pass_without_raw_release_ci_and_tag_is_refused(case):
    f, p, _, _, i, _ = case
    candidate = validated(case)
    with pytest.raises(ValueError):
        f.record(
            p,
            i,
            receipt(
                case,
                "release",
                artifacts={"wheel": candidate, "publication": publication(candidate)},
            ),
        )
    assert f.status(p, i)["state"] == "VALIDATED"


def release_artifacts(candidate):
    return {
        "wheel": candidate,
        "publication": publication(candidate),
        "release": {
            "tag_name": "v0.5.0",
            "draft": False,
            "assets": [
                {
                    "name": "eidos-0.5.0-py3-none-any.whl",
                    "size": len(candidate),
                    "digest": "sha256:" + sha(candidate),
                }
            ],
        },
        "ci": {
            "workflow_runs": [
                {
                    "name": "ci",
                    "head_sha": "b" * 40,
                    "status": "completed",
                    "conclusion": "success",
                    "id": 123,
                    "run_attempt": 1,
                }
            ]
        },
        "tag": {
            "ref": {
                "ref": "refs/tags/v0.5.0",
                "object": {"type": "commit", "sha": "b" * 40},
            }
        },
    }


def test_full_receipt_chain_then_closed_status_withdrawn_on_pin_change(
    case, monkeypatch
):
    f, p, _, _, i, _ = case
    candidate = validated(case)
    f.record(p, i, receipt(case, "release", artifacts=release_artifacts(candidate)))
    adopt(case, candidate, monkeypatch)
    raw = (p / ".eidos/runtime-pin.json").read_bytes()
    replay = result(case, candidate, True, "replay")
    replay["pin_sha256"] = sha(raw)
    f.record(
        p,
        i,
        receipt(
            case,
            "replay",
            artifacts={"wheel": candidate, "check": replay, "pin_after": raw},
        ),
    )
    with pytest.raises(ValueError):
        f.close(p, i)  # Source checkout is not the installed released SDK.
    monkeypatch.setattr(f, "_runtime_matches", lambda _: True)
    closed = f.close(p, i)
    assert closed["state"] == "CLOSED" and closed["scientific_status"] == "UNRUN"
    (p / ".eidos/runtime-pin.json").write_bytes(b"changed pin")
    current = f.status(p, i)
    assert current["state"] == "STALE" and current["historical_state"] == "CLOSED"


@pytest.mark.parametrize("part", ["ci", "asset", "tag"])
def test_wrong_remote_release_identity_refused(case, part):
    f, p, _, _, i, _ = case
    candidate = validated(case)
    artifacts = release_artifacts(candidate)
    if part == "ci":
        artifacts["ci"]["workflow_runs"][0]["head_sha"] = "c" * 40
    elif part == "asset":
        artifacts["release"]["assets"][0]["digest"] = "sha256:" + "0" * 64
    else:
        artifacts["tag"]["ref"]["object"]["sha"] = "c" * 40
    with pytest.raises(ValueError):
        f.record(p, i, receipt(case, "release", artifacts=artifacts))


def test_cli_incident_status_returns_structured_receipt(case, capsys):
    _, project, _, _, incident, _ = case
    capsys.readouterr()
    assert (
        cli(
            [
                "incident",
                "status",
                "--project",
                str(project),
                "--incident",
                incident,
                "--json",
            ]
        )
        == 0
    )
    value = json.loads(capsys.readouterr().out)
    assert value["state"] == "DETECTED" and value["operation"] == "incident.status"


def test_exported_feedback_can_become_same_incident(case, tmp_path):
    f, p, _, source, _, _ = case
    bundle = tmp_path / "capture.zip"
    assert (
        cli(
            [
                "feedback",
                "--project",
                str(p),
                "--message",
                "actual captured defect",
                "--out",
                str(bundle),
                "--json",
            ]
        )
        == 0
    )
    with zipfile.ZipFile(bundle) as archive:
        captured = json.loads(archive.read("feedback.json"))
    created = f.create(
        p, "actual captured defect", source / "protocol.json", feedback_bundle=bundle
    )
    assert created["incident_id"] == captured["incident_id"]
    with pytest.raises((ValueError, FileExistsError)):
        f.create(p, "duplicate", source / "protocol.json", feedback_bundle=bundle)


def adopt(case, candidate, monkeypatch, callback=None):
    f, p, _, _, i, _ = case
    import framework.monitor_registry as registry

    identity = f._wheel(candidate)

    def query(*args):
        from framework.project_state import runtime_identity

        if callback:
            callback()
        return {
            "worker": {
                "installation_mode": "installed",
                "eidos_version": "0.5.0",
                "distributions_sha256": runtime_identity()["distributions_sha256"],
                "prefix": sys.prefix,
                **{k: identity[k] for k in ("sdk_source_sha256", "sdk_module_count")},
            }
        }

    monkeypatch.setattr(registry, "query_worker", query)
    return f.adopt(p, i, Path(sys.executable))


def released(case):
    candidate = validated(case)
    f, p, _, _, i, _ = case
    f.record(p, i, receipt(case, "release", artifacts=release_artifacts(candidate)))
    return candidate


@pytest.mark.parametrize("when", ["before", "during"])
def test_stale_context_cannot_change_runtime_pin(case, monkeypatch, when):
    f, p, _, _, i, _ = case
    candidate = released(case)
    pin = p / ".eidos/runtime-pin.json"
    pin.write_bytes(b"prior pin")

    def change():
        with (p / ".eidos/project.yaml").open("a") as stream:
            stream.write("\n# concurrent config edit\n")

    if when == "before":
        change()
    with pytest.raises(ValueError):
        adopt(case, candidate, monkeypatch, change if when == "during" else None)
    assert pin.read_bytes() == b"prior pin"


def test_validation_cannot_be_reused_as_post_adoption_replay(case, monkeypatch):
    f, p, _, source, i, _ = case
    candidate = released(case)
    validation = json.loads((source / "validation.json").read_text())
    prior = json.loads((source / validation["artifacts"]["check"]["path"]).read_text())
    adopt(case, candidate, monkeypatch)
    raw = (p / ".eidos/runtime-pin.json").read_bytes()
    with pytest.raises(ValueError):
        f.record(
            p,
            i,
            receipt(
                case,
                "replay",
                artifacts={"wheel": candidate, "check": prior, "pin_after": raw},
            ),
        )


def test_incident_parent_symlink_is_refused_before_writing(case, tmp_path):
    f, p, _, source, _, _ = case
    outside = tmp_path / "outside"
    outside.mkdir()
    # Use a new project whose incidents parent does not already exist.
    other = tmp_path / "other"
    assert cli(["init", "--project", str(other), "--json"]) == 0
    import yaml

    policy = json.loads((source / "protocol.json").read_text())
    policy["project_id"] = yaml.safe_load((other / ".eidos/project.yaml").read_text())[
        "project_id"
    ]
    policy_path = source / "other-policy.json"
    policy_path.write_text(json.dumps(policy))
    try:
        (other / ".eidos/incidents").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit this symlink control")
    with pytest.raises(ValueError):
        f.create(other, "must not escape", policy_path)
    assert list(outside.iterdir()) == []


def test_malformed_receipt_and_zip_are_structured_refusals(case, capsys):
    f, p, _, source, i, _ = case
    path = receipt(case, "triage", classification="core")
    value = json.loads(path.read_text())
    value["details"] = ["core"]
    path.write_text(json.dumps(value))
    capsys.readouterr()
    assert (
        cli(
            [
                "incident",
                "record",
                "--project",
                str(p),
                "--incident",
                i,
                "--receipt",
                str(path),
                "--json",
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["status"] == "REFUSED"
    bad = source / "bad.zip"
    bad.write_bytes(b"not zip")
    assert (
        cli(
            [
                "incident",
                "create",
                "--project",
                str(p),
                "--message",
                "bad",
                "--protocol",
                str(source / "protocol.json"),
                "--feedback-bundle",
                str(bad),
                "--json",
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["status"] == "REFUSED"


def test_failed_post_adoption_replay_restores_exact_prior_pin_and_history(
    case, monkeypatch
):
    f, p, _, _, i, _ = case
    candidate = released(case)
    path = p / ".eidos/runtime-pin.json"
    path.write_bytes(b"prior legacy selection")
    runs = p / ".eidos/runs"
    runs.mkdir()
    history = runs / ("a" * 32 + ".json")
    history.write_bytes(b"original history")
    adopt(case, candidate, monkeypatch)
    pin = path.read_bytes()
    check = result(case, candidate, False, "replay")
    check["pin_sha256"] = sha(pin)
    check["fault_injection"] = True
    failed = f.record(
        p,
        i,
        receipt(
            case,
            "replay",
            artifacts={"wheel": candidate, "check": check, "pin_after": pin},
        ),
    )
    assert failed["state"] == "REPLAY_FAILED"
    with pytest.raises(ValueError):
        f.close(p, i)
    reverted = f.revert(p, i)
    assert (
        reverted["state"] == "REVERTED"
        and path.read_bytes() == b"prior legacy selection"
    )
    assert history.read_bytes() == b"original history"
    adopt(case, candidate, monkeypatch)
    assert f.status(p, i)["state"] == "ADOPTED"


def test_other_caller_cannot_claim_the_pinned_runtime_is_closed(
    case, monkeypatch, tmp_path
):
    f, p, _, _, i, _ = case
    candidate = released(case)
    adopt(case, candidate, monkeypatch)
    pin = (p / ".eidos/runtime-pin.json").read_bytes()
    check = result(case, candidate, True, "replay")
    check["pin_sha256"] = sha(pin)
    f.record(
        p,
        i,
        receipt(
            case,
            "replay",
            artifacts={"wheel": candidate, "check": check, "pin_after": pin},
        ),
    )
    monkeypatch.setattr(f, "_runtime_matches", lambda _: True)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "unselected-python.exe"))
    with pytest.raises(ValueError):
        f.close(p, i)


def test_changed_origin_withdraws_incident_currency(case):
    f, p, _, _, i, _ = case
    with (p / ".eidos/validate.py").open("a") as stream:
        stream.write("\n# changed origin\n")
    assert f.status(p, i)["state"] == "STALE"
    with pytest.raises(ValueError):
        f.record(p, i, receipt(case, "triage", classification="core"))


@pytest.mark.parametrize("target", ["journal", "pin"])
def test_interrupted_adoption_is_retryable_without_losing_prior_pin(
    case, monkeypatch, target
):
    f, p, _, _, i, _ = case
    candidate = released(case)
    path = p / ".eidos/runtime-pin.json"
    path.write_bytes(b"prior pin")
    original = f.atomic_output
    remaining = [True]

    @contextmanager
    def fail_once(output):
        selected = Path(output).name == (
            "journal.json" if target == "journal" else "runtime-pin.json"
        )
        if selected and remaining[0]:
            remaining[0] = False
            raise OSError("injected publication failure")
        with original(output) as temporary:
            yield temporary

    monkeypatch.setattr(f, "atomic_output", fail_once)
    with pytest.raises(OSError):
        adopt(case, candidate, monkeypatch)
    assert path.read_bytes() == b"prior pin"
    assert f.status(p, i)["state"] == ("RELEASED" if target == "journal" else "STALE")
    adopt(case, candidate, monkeypatch)
    assert f.status(p, i)["state"] == "ADOPTED"


def test_interrupted_reversion_restores_prior_pin_on_retry(case, monkeypatch):
    f, p, _, _, i, _ = case
    candidate = released(case)
    path = p / ".eidos/runtime-pin.json"
    path.write_bytes(b"prior pin")
    adopt(case, candidate, monkeypatch)
    original = f.atomic_output
    remaining = [True]

    @contextmanager
    def fail_once(output):
        if Path(output) == path and remaining[0]:
            remaining[0] = False
            raise OSError("injected pin failure")
        with original(output) as temporary:
            yield temporary

    monkeypatch.setattr(f, "atomic_output", fail_once)
    with pytest.raises(OSError):
        f.revert(p, i)
    assert f.status(p, i)["state"] == "STALE"
    assert f.revert(p, i)["state"] == "REVERTED" and path.read_bytes() == b"prior pin"


def test_reversion_restores_absence_if_no_prior_pin_existed(case, monkeypatch):
    f, p, _, _, i, _ = case
    candidate = released(case)
    adopt(case, candidate, monkeypatch)
    assert (p / ".eidos/runtime-pin.json").exists()
    assert f.revert(p, i)["state"] == "REVERTED"
    assert not (p / ".eidos/runtime-pin.json").exists()


def test_pending_reversion_cannot_become_the_next_adoption_baseline(case, monkeypatch):
    f, p, _, _, i, _ = case
    candidate = released(case)
    path = p / ".eidos/runtime-pin.json"
    path.write_bytes(b"original baseline")
    adopt(case, candidate, monkeypatch)
    original = f.atomic_output

    @contextmanager
    def fail(output):
        if Path(output) == path:
            raise OSError("interrupted prior-pin restoration")
        with original(output) as temporary:
            yield temporary

    monkeypatch.setattr(f, "atomic_output", fail)
    with pytest.raises(OSError):
        f.revert(p, i)
    monkeypatch.setattr(f, "atomic_output", original)
    with pytest.raises(ValueError):
        adopt(case, candidate, monkeypatch)
    f.revert(p, i)
    adopt(case, candidate, monkeypatch)
    f.revert(p, i)
    assert path.read_bytes() == b"original baseline"


def test_retry_cannot_republish_pin_for_changed_dependencies(case, monkeypatch):
    f, p, _, _, i, _ = case
    candidate = released(case)
    adopt(case, candidate, monkeypatch)
    original = (p / ".eidos/runtime-pin.json").read_bytes()
    import framework.monitor_registry as registry

    identity = f._wheel(candidate)
    monkeypatch.setattr(
        registry,
        "query_worker",
        lambda *a: {
            "worker": {
                "installation_mode": "installed",
                "eidos_version": "0.5.0",
                "prefix": sys.prefix,
                "distributions_sha256": "0" * 64,
                **{k: identity[k] for k in ("sdk_source_sha256", "sdk_module_count")},
            }
        },
    )
    with pytest.raises(ValueError):
        f.adopt(p, i, Path(sys.executable))
    assert (p / ".eidos/runtime-pin.json").read_bytes() == original


def test_two_incidents_serialize_changes_to_one_project_pin(case, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    f, p, pid, source, incident, protocol = case
    first = released(case)
    second_id = f.create(p, "second independent incident", source / "protocol.json")[
        "incident_id"
    ]
    other = (f, p, pid, source, second_id, protocol)
    released(other)
    path = p / ".eidos/runtime-pin.json"
    path.write_bytes(b"baseline")
    adopt(case, first, monkeypatch)
    entered = threading.Event()
    resume = threading.Event()
    finished = threading.Event()
    original = f._append

    def pause(folder, journal, document, artifacts):
        if document["kind"] == "reversion" and document["incident_id"] == incident:
            entered.set()
            if not resume.wait(5):
                raise RuntimeError("test release signal missing")
        return original(folder, journal, document, artifacts)

    monkeypatch.setattr(f, "_append", pause)

    def second_adoption():
        value = f.adopt(p, second_id, Path(sys.executable))
        finished.set()
        return value

    with ThreadPoolExecutor(max_workers=2) as executor:
        rollback = executor.submit(f.revert, p, incident)
        assert entered.wait(3)
        adoption = executor.submit(second_adoption)
        try:
            assert not finished.wait(0.3), (
                "Another incident changed the pin inside rollback ownership"
            )
        finally:
            resume.set()
        rollback.result(timeout=5)
        adoption.result(timeout=5)
    assert json.loads(path.read_text())["incident_id"] == second_id


def test_corrupt_compressed_wheel_is_structured_refusal(case, capsys):
    import io
    import struct

    f, p, _, _, i, _ = case
    begin(case)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "eidos-0.5.0.dist-info/METADATA", "Name: eidos\nVersion: 0.5.0\n\n"
        )
        archive.writestr("framework/feedback.py", "pass\n")
    body = bytearray(stream.getvalue())
    name, extra = struct.unpack_from("<HH", body, 26)
    offset = 30 + name + extra
    body[offset] = (body[offset] & 0xF8) | 7
    path = receipt(case, "candidate", artifacts={"wheel": bytes(body)})
    capsys.readouterr()
    assert (
        cli(
            [
                "incident",
                "record",
                "--project",
                str(p),
                "--incident",
                i,
                "--receipt",
                str(path),
                "--json",
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["status"] == "REFUSED"


def test_missing_details_never_poison_the_readable_journal(case):
    f, p, _, _, i, _ = case
    begin(case)
    before = f.status(p, i)
    path = receipt(case, "candidate", artifacts={"wheel": wheel("0.5.0")})
    value = json.loads(path.read_text())
    value.pop("details")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        f.record(p, i, path)
    after = f.status(p, i)
    assert (after["events"], after["head_sha256"]) == (
        before["events"],
        before["head_sha256"],
    )


def test_history_ignores_unpublished_atomic_staging_files(case, monkeypatch):
    f, p, _, _, i, _ = case
    candidate = released(case)
    runs = p / ".eidos/runs"
    runs.mkdir()
    staged = runs / ("b" * 32 + ".json")
    with f.atomic_output(staged) as temporary:
        temporary.write_bytes(b"committing run")
        adopt(case, candidate, monkeypatch)
    assert f.revert(p, i)["state"] == "REVERTED"
    assert staged.read_bytes() == b"committing run"
