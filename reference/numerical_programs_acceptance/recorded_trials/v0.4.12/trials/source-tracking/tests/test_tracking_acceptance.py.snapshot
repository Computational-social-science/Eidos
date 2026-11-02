"""Acceptance must bind the actual package and use only disposable resources."""

import base64
from contextlib import nullcontext
import csv
import hashlib
from importlib import util
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest


@pytest.fixture
def checker():
    path = (
        Path(__file__).resolve().parents[1] / "reference/tracking_acceptance/check.py"
    )
    spec = util.spec_from_file_location("tracking_acceptance_protocol", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_wheel(directory, *, metadata=None, wheel_metadata=None, alter_record=False):
    path = directory / "eidos-0.4.10-py3-none-any.whl"
    prefix = "eidos-0.4.10.dist-info/"
    members = {
        "framework/tracking/__init__.py": b"# fixture only\n",
        prefix + "METADATA": metadata
        or b"Metadata-Version: 2.4\nName: eidos\nVersion: 0.4.10\n\n",
        prefix + "WHEEL": wheel_metadata
        or b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n",
    }
    output = StringIO(newline="")
    writer = csv.writer(output)
    for name, body in members.items():
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
        )
        writer.writerow((name, "sha256=" + digest, len(body)))
    writer.writerow((prefix + "RECORD", "", ""))
    members[prefix + "RECORD"] = output.getvalue().encode()
    if alter_record:
        members["framework/tracking/__init__.py"] += b"# unrecorded edit\n"
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return path


def test_valid_wheel_binds_raw_archive_and_metadata(tmp_path, checker):
    path = make_wheel(tmp_path)
    identity = checker.wheel_identity(path, "0.4.10")
    assert identity["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert set(identity["modules"]) == {"framework/tracking/__init__.py"}


@pytest.mark.parametrize(
    "metadata",
    [
        b"Name: another\nVersion: 0.4.10\n\n",
        b"Name: eidos\nVersion: 0.4.9\n\n",
        b"Name: eidos\nName: another\nVersion: 0.4.10\n\n",
        b"Name: eidos\nVersion: 0.4.10\nVersion: 0.4.10\n\n",
    ],
)
def test_wrong_or_ambiguous_wheel_metadata_refused(tmp_path, checker, metadata):
    with pytest.raises(ValueError, match="identity"):
        checker.wheel_identity(make_wheel(tmp_path, metadata=metadata), "0.4.10")


def test_invalid_record_refused(tmp_path, checker):
    with pytest.raises(ValueError, match="checksum"):
        checker.wheel_identity(make_wheel(tmp_path, alter_record=True), "0.4.10")


@pytest.mark.parametrize(
    "entry",
    [
        "framework/../escape.py",
        "framework//alias.py",
        "framework/C:escape.py",
        "framework\\escape.py",
        "framework/tracking/__init__.py",
    ],
)
def test_unsafe_or_duplicate_archive_member_refused(tmp_path, checker, entry):
    path = make_wheel(tmp_path)
    with zipfile.ZipFile(path, "a") as archive:
        with (
            pytest.warns(UserWarning)
            if entry.endswith("__init__.py")
            else nullcontext()
        ):
            info = zipfile.ZipInfo("fixture")
            info.filename = info.orig_filename = entry
            archive.writestr(info, b"unbound")
    with pytest.raises(ValueError, match="Unsafe|Duplicate"):
        checker.wheel_identity(path, "0.4.10")


def test_installed_metadata_is_compared_even_when_python_code_is_identical(
    tmp_path, checker, monkeypatch
):
    identity = checker.wheel_identity(make_wheel(tmp_path), "0.4.10")
    environment = tmp_path / "environment"
    base = environment / "site-packages"
    source = tmp_path / "source"
    for name, body in identity["members"].items():
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        if name.startswith("framework/"):
            original = source / name
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(body)

    class Distribution:
        _path = base / identity["directory"]
        files = list(identity["members"])

        def locate_file(self, path):
            return base / path

        def read_text(self, name):
            path = self._path / name
            return path.read_text(encoding="utf-8") if path.exists() else None

    monkeypatch.setattr(checker.metadata, "distribution", lambda name: Distribution())
    monkeypatch.setattr(checker.sys, "prefix", str(environment))
    monkeypatch.setattr(
        checker.util,
        "find_spec",
        lambda name: SimpleNamespace(
            origin=str(base / "framework/tracking/__init__.py")
        ),
    )
    checker.installed_inventory(identity, source)
    (base / identity["directory"] / "METADATA").write_text(
        "Name: eidos\nVersion: 0.4.10\nRequires-Dist: unqualified\n\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="payload/metadata"):
        checker.installed_inventory(identity, source)


@pytest.mark.parametrize(
    "mutation",
    [
        "wheel",
        "driver",
        "source",
        "copied",
        "dependencies",
        "empty",
        "duplicate",
        "skip",
        "failure",
    ],
)
def test_qualification_refuses_rebound_inputs_and_vacuous_results(
    tmp_path, checker, monkeypatch, mutation
):
    from framework import subprocesses

    source = tmp_path / "source"
    (source / "tests").mkdir(parents=True)
    for name in checker.PROTOCOL_FILES:
        (source / "tests" / name).write_text("# pinned protocol\n", encoding="utf-8")
    monkeypatch.setattr(
        checker, "PROTOCOL_SHA256_LF", checker.protocol_inventory(source / "tests")
    )
    driver = tmp_path / "driver.py"
    driver.write_text("# executed driver\n", encoding="utf-8")
    monkeypatch.setattr(checker, "__file__", str(driver))
    wheel = make_wheel(tmp_path)
    monkeypatch.setattr(checker.metadata, "version", lambda name: "0.4.10")
    monkeypatch.setattr(
        checker, "installed_inventory", lambda identity, source: identity["modules"]
    )
    dependency_samples = iter(
        [
            [{"name": "fixture", "version": "before"}],
            [
                {
                    "name": "fixture",
                    "version": "after" if mutation == "dependencies" else "before",
                }
            ],
        ]
    )
    monkeypatch.setattr(
        checker, "dependency_inventory", lambda: next(dependency_samples)
    )

    def execute(command, *, cwd, env, timeout):
        assert "--basetemp=" + str(cwd / "pytest-tmp") in command
        for variable in (
            "DVC_GLOBAL_CONFIG_DIR",
            "DVC_SYSTEM_CONFIG_DIR",
            "DVC_SITE_CACHE_DIR",
        ):
            assert Path(env[variable]).is_relative_to(cwd)
        if mutation == "failure":
            return subprocess.CompletedProcess(command, 17, "", "deliberate failure")
        rows = []
        for index in range(0 if mutation == "empty" else checker.EXPECTED_CASES):
            name = "duplicate" if mutation == "duplicate" else str(index)
            rows.append(
                f'<testcase classname="protocol" name="{name}">'
                + ("<skipped/>" if mutation == "skip" and index == 0 else "")
                + "</testcase>"
            )
        (cwd / "junit.xml").write_text(
            "<testsuite>" + "".join(rows) + "</testsuite>", encoding="utf-8"
        )
        if mutation == "wheel":
            with zipfile.ZipFile(wheel, "a") as archive:
                archive.comment = b"repacked during execution"
        elif mutation == "driver":
            driver.write_text("# another driver\n", encoding="utf-8")
        elif mutation in ("source", "copied"):
            directory = source / "tests" if mutation == "source" else cwd / "protocol"
            (directory / checker.PROTOCOL_FILES[0]).write_text(
                "# mutated protocol\n", encoding="utf-8"
            )
        return subprocess.CompletedProcess(command, 0, "49 passed, 2 deselected", "")

    monkeypatch.setattr(subprocesses, "run_tree", execute)
    args = SimpleNamespace(
        source=source,
        wheel=wheel,
        expected_version="0.4.10",
        timeout=10,
        fault_child=False,
    )
    with pytest.raises(ValueError):
        checker.qualify(args)


def test_private_environment_overrides_external_dvc_cache(tmp_path, checker):
    pytest.importorskip("dvc")
    from framework.subprocesses import run_tree

    external = tmp_path / "external-cache"
    external.mkdir()
    (external / "sentinel").write_bytes(b"must not change")
    hostile = tmp_path / "external-config"
    hostile.mkdir()
    (hostile / "config").write_text(
        "[cache]\n    dir = " + external.as_posix() + "\n", encoding="utf-8"
    )
    workspace = tmp_path / "private"
    workspace.mkdir()
    hostile_env = dict(os.environ)
    hostile_env.update(
        DVC_GLOBAL_CONFIG_DIR=str(hostile),
        DVC_SYSTEM_CONFIG_DIR=str(hostile),
        DVC_SITE_CACHE_DIR=str(external),
        DVC_NO_ANALYTICS="1",
    )
    probe = 'from dvc.config import Config; import json; print(json.dumps(dict(Config()["cache"])))'
    before = run_tree(
        [sys.executable, "-I", "-c", probe], cwd=workspace, env=hostile_env, timeout=60
    )
    assert before.returncode == 0, before.stderr
    assert Path(json.loads(before.stdout)["dir"]).resolve() == external.resolve()
    environment = checker.private_environment(workspace, hostile_env)
    code = (
        "from pathlib import Path; from dvc.repo import Repo; import json; "
        'Repo.init(".", no_scm=True); Path("data.txt").write_text("fixture\\n"); '
        'repo=Repo("."); repo.add("data.txt"); '
        'print(json.dumps({"cache": str(repo.cache.repo.path)})); repo.close()'
    )
    result = run_tree(
        [sys.executable, "-I", "-c", code], cwd=workspace, env=environment, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert (
        Path(json.loads(result.stdout.splitlines()[-1])["cache"])
        .resolve()
        .is_relative_to(workspace)
    )
    assert {
        path.relative_to(external).as_posix(): path.read_bytes()
        for path in external.rglob("*")
        if path.is_file()
    } == {"sentinel": b"must not change"}
