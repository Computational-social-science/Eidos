"""A named metadata exception must leave the entire frozen graph unchanged."""

from pathlib import Path

import pytest

from framework.lock_compatibility import frozen_tracking_resolution
from framework.provenance import historical_lock_matches, source_hash

ORIGINAL = """version = 1
requires-python = ">=3.11"
resolution-markers = ["sys_platform == 'win32'", "sys_platform != 'win32'"]
[[package]]
name = "eidos"
version = "0.4.9"
source = {editable = "."}
dependencies = [{name = "numpy"}]
[package.optional-dependencies]
tracking = [{name = "mlflow"}, {name = "dvc"}]
[package.metadata]
requires-dist = [
 {name = "mlflow", marker = "extra == 'tracking'", specifier = ">=2.10"},
 {name = "mlflow", marker = "extra == 'all'", specifier = ">=2.10"},
 {name = "dvc", marker = "extra == 'tracking'", specifier = ">=3.0"},
 {name = "dvc", marker = "extra == 'all'", specifier = ">=3.0"},
]
[[package]]
name = "mlflow"
version = "3.17.2"
source = {registry = "https://pypi.org/simple"}
wheels = [
 {url = "https://example.invalid/mlflow.whl", hash = "sha256:AAAAAAAA", size = 2},
 {url = "https://example.invalid/mlflow-other.whl", hash = "sha256:BBBBBBBB", size = 3},
]
[[package]]
name = "dvc"
version = "3.67.1"
source = {registry = "https://pypi.org/simple"}
wheels = [{url = "https://example.invalid/dvc.whl", hash = "sha256:AAAAAAAA", size = 2}]
[[package]]
name = "numpy"
version = "2.5.4"
source = {registry = "https://pypi.org/simple"}
""".replace("AAAAAAAA", "a" * 64).replace("BBBBBBBB", "b" * 64)


def materialize(root, original=ORIGINAL, current=None):
    recorded = source_hash(original.encode())
    archive = root / "lock/snapshots/uv" / (recorded + ".lock")
    archive.parent.mkdir(parents=True)
    archive.write_text(original, encoding="utf-8")
    if current is None:
        current = (
            original.replace("0.4.9", "0.4.10")
            .replace(">=2.10", ">=3.17.2")
            .replace(">=3.0", ">=3.67.1")
        )
        current = current.replace(
            "[\"sys_platform == 'win32'\", \"sys_platform != 'win32'\"]",
            "[\"sys_platform != 'win32'\", \"sys_platform == 'win32'\"]",
        )
    (root / "uv.lock").write_text(current, encoding="utf-8")
    return recorded, archive


def test_tracking_constraint_migration_is_separate_from_strict_original_match(tmp_path):
    recorded, archive = materialize(tmp_path)
    original_bytes = archive.read_bytes()
    assert historical_lock_matches(tmp_path, recorded) is False
    result = frozen_tracking_resolution(tmp_path, recorded)
    assert result["status"] == "COMPATIBLE_FROZEN_RESOLUTION"
    assert result["unchanged_third_party_records"] is True
    assert result["original_canonical_sha256"] == recorded
    assert result["delivery_canonical_sha256"] != recorded
    assert (
        len(
            [
                row
                for row in result["changes"]
                if row["field"] == "eidos.requires-dist.specifier"
            ]
        )
        == 4
    )
    assert archive.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "before,after",
    [
        ('version = "2.5.4"', 'version = "2.6.0"'),
        ('hash = "sha256:' + "a" * 64, 'hash = "sha256:' + "c" * 64),
        ("https://pypi.org/simple", "https://different.invalid/simple"),
        ('dependencies = [{name = "numpy"}]', 'dependencies = [{name = "dvc"}]'),
        ("sys_platform == 'win32'", "sys_platform == 'linux'"),
        ("size = 2", "size = true"),
        ("version = 1\n", "version = true\n"),
        ('requires-python = ">=3.11"', 'requires-python = ">=3.12"'),
        ("marker = \"extra == 'tracking'\"", "marker = \"extra == 'other'\""),
        ('specifier = ">=3.17.2"', 'specifier = ">=3.18"'),
    ],
)
def test_changed_frozen_graph_or_unapproved_metadata_is_refused(
    tmp_path, before, after
):
    recorded, _ = materialize(tmp_path)
    path = tmp_path / "uv.lock"
    content = path.read_text(encoding="utf-8")
    assert before in content
    path.write_text(content.replace(before, after, 1), encoding="utf-8")
    assert (
        frozen_tracking_resolution(tmp_path, recorded)["status"]
        == "INCOMPATIBLE_FROZEN_RESOLUTION"
    )


def test_every_conditional_candidate_must_satisfy_both_bounds(tmp_path):
    extra = """
[[package]]
name = "mlflow"
version = "2.20.0"
source = {registry = "https://pypi.org/simple"}
wheels = [{url = "https://example.invalid/old.whl", hash = "sha256:AAAAAAAA", size = 2}]
resolution-markers = ["python_version < '3.12'"]
""".replace("AAAAAAAA", "a" * 64)
    recorded, _ = materialize(tmp_path, ORIGINAL + extra)
    result = frozen_tracking_resolution(tmp_path, recorded)
    assert result["status"] == "INCOMPATIBLE_FROZEN_RESOLUTION"
    assert "both constraints" in result["error"]


def test_duplicate_requirements_are_not_normalized_away(tmp_path):
    duplicate = (
        ' {name = "mlflow", marker = "extra == \'tracking\'", specifier = ">=2.10"},'
    )
    original = ORIGINAL.replace(duplicate, duplicate + "\n" + duplicate)
    recorded, _ = materialize(tmp_path, original)
    result = frozen_tracking_resolution(tmp_path, recorded)
    assert result["status"] == "INCOMPATIBLE_FROZEN_RESOLUTION"
    assert "duplicate" in result["error"]


def test_marker_multiplicity_cannot_change(tmp_path):
    recorded, _ = materialize(tmp_path)
    path = tmp_path / "uv.lock"
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        "resolution-markers = [",
        "resolution-markers = [\"sys_platform == 'win32'\", ",
        1,
    )
    path.write_text(content, encoding="utf-8")
    assert (
        frozen_tracking_resolution(tmp_path, recorded)["status"]
        == "INCOMPATIBLE_FROZEN_RESOLUTION"
    )


@pytest.mark.parametrize(
    "failure", ["missing", "corrupt", "ordinary-order", "no-candidate"]
)
def test_original_and_ordinary_lists_remain_strict(tmp_path, failure):
    recorded, archive = materialize(tmp_path)
    path = tmp_path / "uv.lock"
    if failure == "missing":
        archive.unlink()
    elif failure == "corrupt":
        archive.write_text("corrupt", encoding="utf-8")
    elif failure == "ordinary-order":
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'tracking = [{name = "mlflow"}, {name = "dvc"}]',
                'tracking = [{name = "dvc"}, {name = "mlflow"}]',
            ),
            encoding="utf-8",
        )
    else:
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'name = "mlflow"\nversion = "3.17.2"',
                'name = "absent"\nversion = "3.17.2"',
            ),
            encoding="utf-8",
        )
    assert (
        frozen_tracking_resolution(tmp_path, recorded)["status"]
        == "INCOMPATIBLE_FROZEN_RESOLUTION"
    )


@pytest.mark.parametrize(
    "failure", ["missing-candidate", "unverifiable-source", "duplicate-candidate"]
)
def test_incomplete_original_candidate_coverage_is_refused(tmp_path, failure):
    original = ORIGINAL
    if failure == "missing-candidate":
        original = original.replace(
            'name = "mlflow"\nversion = "3.17.2"', 'name = "absent"\nversion = "3.17.2"'
        )
    elif failure == "unverifiable-source":
        original = original.replace(
            'source = {registry = "https://pypi.org/simple"}', "source = {}", 1
        )
    else:
        block = ORIGINAL.split('[[package]]\nname = "mlflow"')[1].split("[[package]]")[
            0
        ]
        original += '\n[[package]]\nname = "mlflow"' + block
    recorded, _ = materialize(tmp_path, original)
    assert (
        frozen_tracking_resolution(tmp_path, recorded)["status"]
        == "INCOMPATIBLE_FROZEN_RESOLUTION"
    )
