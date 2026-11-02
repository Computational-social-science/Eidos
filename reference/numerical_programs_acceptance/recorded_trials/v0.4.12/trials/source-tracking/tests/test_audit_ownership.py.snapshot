"""An audit owns execution, markers and publication; a skipped run is not evidence."""

from pathlib import Path
import json
import subprocess
import sys
import time

import pytest

from tools import audit_chains as audit


def invoke(tmp_path, monkeypatch, capsys, entries, *args):
    monkeypatch.setattr(audit, "CHAINS", entries)
    code = audit.main(["--status-dir", str(tmp_path), "--json", *args])
    output = capsys.readouterr()
    return code, output


def test_exact_selection_does_not_run_a_second_chain_with_the_same_prefix(
    tmp_path, monkeypatch, capsys
):
    def forbidden():
        pytest.fail("prefix match ran despite an exact chain")

    code, out = invoke(
        tmp_path,
        monkeypatch,
        capsys,
        [
            ("gates", lambda: ("PASS", "one"), "", ()),
            ("gates+project checker", forbidden, "", ()),
        ],
        "--only",
        "gates",
    )
    assert code == 0 and [r["chain"] for r in json.loads(out.out)] == ["gates"]


def test_ambiguous_or_unknown_prefix_has_no_side_effects(tmp_path, monkeypatch, capsys):
    for requested in ["g", "unknown"]:
        code, out = invoke(
            tmp_path,
            monkeypatch,
            capsys,
            [
                ("gates", lambda: ("PASS", ""), "", ()),
                ("gates+project checker", lambda: ("PASS", ""), "", ()),
            ],
            "--only",
            requested,
        )
        assert code == 2 and not (tmp_path / "running.json").exists()
        assert not (tmp_path / "chains.json").exists()


def test_repeated_calls_do_not_republish_previous_results(
    tmp_path, monkeypatch, capsys
):
    entries = [
        ("first", lambda: ("PASS", "first"), "", ()),
        ("second", lambda: ("FAIL", "second"), "", ()),
    ]
    code, out = invoke(tmp_path, monkeypatch, capsys, entries, "--only", "first")
    assert code == 0 and len(json.loads(out.out)) == 1
    code, out = invoke(tmp_path, monkeypatch, capsys, entries, "--only", "second")
    assert code == 1 and [r["chain"] for r in json.loads(out.out)] == ["second"]
    assert set(json.loads((tmp_path / "chains.json").read_text())["chains"]) == {
        "first",
        "second",
    }


def test_api_arguments_reach_the_selected_chain_and_do_not_leak(
    tmp_path, monkeypatch, capsys
):
    seen = []

    def check():
        seen.append(audit._option("--manuscript"))
        return "PASS", "checked"

    invoke(
        tmp_path,
        monkeypatch,
        capsys,
        [("quarto", check, "", ())],
        "--manuscript",
        "real manuscript",
    )
    assert seen == ["real manuscript"] and audit._option("--manuscript") == ""


def test_checker_logs_cannot_corrupt_the_json_result(tmp_path, monkeypatch, capsys):
    def check():
        print("diagnostic from a subsystem")
        return "PASS", "checked"

    code, out = invoke(tmp_path, monkeypatch, capsys, [("one", check, "", ())])
    assert code == 0 and len(json.loads(out.out)) == 1 and "diagnostic" in out.err


def test_publication_failure_clears_its_running_marker(tmp_path, monkeypatch, capsys):
    import framework.artifacts as artifacts

    old = artifacts.os.replace

    def fail(source, target):
        if Path(target).name == "chains.json":
            raise PermissionError("publication locked")
        return old(source, target)

    monkeypatch.setattr(artifacts.os, "replace", fail)
    with pytest.raises(PermissionError):
        invoke(tmp_path, monkeypatch, capsys, [("one", lambda: ("PASS", ""), "", ())])
    assert not (tmp_path / "running.json").exists()


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "[]",
        '{"chains":[]}',
        "{}",
        '{"ts":123}',
        '{"chains":{"a":{"status":"PASS","ts":NaN}}}',
        '{"chains":{"a":{"status":"PASS","ts":"yesterday"}}}',
        '{"chains":{},"chains":{}}',
    ],
)
def test_corrupt_previous_state_is_not_discarded_or_called_a_pass(
    tmp_path, monkeypatch, capsys, body
):
    path = tmp_path / "chains.json"
    path.write_text(body)

    def forbidden():
        pytest.fail("work launched before corrupt state was refused")

    code, _ = invoke(tmp_path, monkeypatch, capsys, [("one", forbidden, "", ())])
    assert (
        code != 0
        and path.read_text() == body
        and not (tmp_path / "running.json").exists()
    )


@pytest.mark.parametrize(
    "name",
    [
        "chains.json",
        "running.json",
        "scheduler.json",
        ".eidos-export-audit-target-chains.json.lock",
    ],
)
def test_trace_cannot_replace_other_roles_or_ownership_locks(
    tmp_path, monkeypatch, capsys, name
):
    status = tmp_path / "other"
    status.mkdir()
    target = status / name
    target.write_text('{"chains":{"prior":{"status":"FAIL","ts":1}}}')
    before = target.read_bytes()

    def forbidden():
        pytest.fail("reserved output launched work")

    code, _ = invoke(
        tmp_path / "mine",
        monkeypatch,
        capsys,
        [("one", forbidden, "", ())],
        "--spans",
        str(target),
    )
    assert code == 2 and target.read_bytes() == before


def test_trace_cannot_overwrite_an_existing_nontrace_json(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / "study.json"
    target.write_text('{"scientific_data":123}')
    code, _ = invoke(
        tmp_path / "state",
        monkeypatch,
        capsys,
        [("one", lambda: pytest.fail("work launched"), "", ())],
        "--spans",
        str(target),
    )
    assert code == 2 and target.read_text() == '{"scientific_data":123}'


@pytest.mark.parametrize(
    "name",
    ["Running.json", "CHAINS.json", "Scheduler.json", ".EIDOS-EXPORT-test.lock.json"],
)
def test_trace_reserves_windows_case_aliases(tmp_path, monkeypatch, capsys, name):
    code, _ = invoke(
        tmp_path,
        monkeypatch,
        capsys,
        [("one", lambda: pytest.fail("work launched"), "", ())],
        "--spans",
        str(tmp_path / "other" / name),
    )
    assert code == 2 and not (tmp_path / "other" / name).exists()


def test_overlapping_api_audits_cannot_interleave_stdout_redirection(
    tmp_path, monkeypatch, capsys
):
    import threading

    entered, release = threading.Event(), threading.Event()

    def first():
        entered.set()
        assert release.wait(5)
        print("diagnostic")
        return "PASS", "one"

    monkeypatch.setattr(audit, "CHAINS", [("one", first, "", ())])
    results = []
    original_stdout = sys.stdout
    worker = threading.Thread(
        target=lambda: results.append(
            audit.main(["--json", "--status-dir", str(tmp_path / "one")])
        )
    )
    worker.start()
    try:
        assert entered.wait(2)
        assert (
            audit.main(
                ["--json", "--status-dir", str(tmp_path / "two"), "--lock-timeout", "0"]
            )
            == 75
        )
        assert not (tmp_path / "two/chains.json").exists()
    finally:
        release.set()
        worker.join(5)
    assert results == [0] and sys.stdout is original_stdout
    output = capsys.readouterr()
    assert len(json.loads(output.out)) == 1 and "diagnostic" in output.err


def test_nested_api_call_is_refused_without_overwriting_outer_marker(
    tmp_path, monkeypatch, capsys
):
    def nested():
        assert audit.main(["--json", "--status-dir", str(tmp_path)]) == 75
        assert (tmp_path / "running.json").exists()
        return "PASS", "nested refused"

    code, _ = invoke(tmp_path, monkeypatch, capsys, [("one", nested, "", ())])
    assert code == 0 and not (tmp_path / "running.json").exists()


@pytest.mark.parametrize("exit_code", [0, 1, None])
def test_a_chain_cannot_exit_without_returning_a_verdict(
    tmp_path, monkeypatch, capsys, exit_code
):
    def leave():
        raise SystemExit(exit_code)

    code, out = invoke(tmp_path, monkeypatch, capsys, [("one", leave, "", ())])
    assert code == 1 and json.loads(out.out)[0]["status"] == "ERROR"
    assert not (tmp_path / "running.json").exists()


def test_marker_owner_cannot_clear_a_replacement(tmp_path):
    from tools import chain_states

    path = tmp_path / "running.json"
    owner = chain_states.mark_running(path=path)
    path.write_text(json.dumps({"owner": "another audit", "started": time.time()}))
    chain_states.clear_running(path=path, owner=owner)
    assert path.exists()


def test_real_cli_contention_does_not_run_or_overwrite_another_audit(tmp_path):
    root = Path(__file__).resolve().parents[1]
    harness = tmp_path / "runner.py"
    harness.write_text(
        """import sys
from pathlib import Path
sys.path.insert(0,sys.argv.pop(1))
from tools import audit_chains as a
def first():
 Path(sys.argv[1]+'/entered').touch()
 sys.stdin.readline()
 return 'PASS','first executed'
a.CHAINS=[('first',first,'',()),('second',lambda:('PASS','second executed'),'',())]
raise SystemExit(a.main(['--status-dir',sys.argv[1],'--only',sys.argv[2],'--json','--lock-timeout',sys.argv[3]]))
""",
        encoding="utf-8",
    )
    state = tmp_path / "state"
    state.mkdir()
    (state / "chains.json").write_text('{"chains":{"prior":{"status":"FAIL","ts":1}}}')
    command = [sys.executable, "-I", str(harness), str(root), str(state)]
    first = subprocess.Popen(
        [*command, "first", "10"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 10
        while (
            not (state / "entered").exists()
            and first.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert (state / "entered").exists()
        marker = (state / "running.json").read_bytes()
        previous = (state / "chains.json").read_bytes()
        second = subprocess.run(
            [*command, "second", "0"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert second.returncode == 75, second.stdout + second.stderr
        assert (state / "running.json").read_bytes() == marker and (
            state / "chains.json"
        ).read_bytes() == previous
    finally:
        stdout, stderr = first.communicate("release\n", timeout=15)
    assert first.returncode == 0, stdout + stderr
    assert not (state / "running.json").exists()
    second = subprocess.run(
        [*command, "second", "10"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert second.returncode == 0, second.stdout + second.stderr
    saved = json.loads((state / "chains.json").read_text())["chains"]
    assert (
        set(saved) == {"prior", "first", "second"}
        and saved["prior"]["status"] == "FAIL"
    )
