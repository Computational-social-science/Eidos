"""A tag must publish the exact qualified SDK, not a fresh unmeasured build."""

import zipfile

import pytest


@pytest.fixture
def source(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="eidos"\nversion="0.5.0"\nrequires-python=">=3.11"\n'
        '[project.scripts]\neidos="framework.cli:main"\n'
        'eidos-agent="framework.cli:main"\n'
    )
    (tmp_path / "framework").mkdir()
    (tmp_path / "framework/example.py").write_bytes(b"ANSWER=42\r\n")
    return tmp_path


def wheel(
    root,
    *,
    name="eidos",
    version="0.5.0",
    code=b"ANSWER=42\n",
    duplicate=False,
    entries="[console_scripts]\neidos=framework.cli:main\neidos-agent=framework.cli:main\n",
    python=">=3.11",
):
    path = root / "candidate.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "eidos.dist-info/METADATA",
            f"Name: {name}\nVersion: {version}\nRequires-Python: {python}\n\n",
        )
        if entries is not None:
            archive.writestr("eidos.dist-info/entry_points.txt", entries)
        archive.writestr("framework/example.py", code)
        if duplicate:
            archive.writestr("framework/example.py", code)
    return path


def test_qualified_sdk_binds_canonical_source(source):
    from tools.check_release_wheel import errors

    assert errors(source, wheel(source)) == []


@pytest.mark.parametrize("field", ["name", "version", "code", "duplicate"])
def test_wrong_distribution_or_source_refuses_publication(source, field):
    from tools.check_release_wheel import errors

    values = {
        "name": "other",
        "version": "9.9.9",
        "code": b"ANSWER=0\n",
        "duplicate": True,
    }
    assert errors(source, wheel(source, **{field: values[field]}))


def test_invalid_archive_is_a_failed_publication_check(source):
    from tools.check_release_wheel import errors

    path = source / "bad.whl"
    path.write_bytes(b"not a wheel")
    assert errors(source, path)


@pytest.mark.parametrize(
    "entries",
    [
        None,
        "[console_scripts]\neidos=framework.cli:main\n",
        "[console_scripts]\neidos=framework.cli:main\neidos-agent=other:main\n",
    ],
)
def test_missing_or_wrong_console_alias_refuses_publication(source, entries):
    from tools.check_release_wheel import errors

    assert errors(source, wheel(source, entries=entries))


def test_changed_python_requirement_refuses_publication(source):
    from tools.check_release_wheel import errors

    assert errors(source, wheel(source, python=">=3.14"))
