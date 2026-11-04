"""Bind a wheel's SDK, name/version, Python requirement and console declarations.

Dependency installation and runtime qualification remain separate release gates.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import re
import tomllib
import zipfile
import zlib
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _canonical(body: bytes) -> bytes:
    return body.decode("utf-8-sig").replace("\r\n", "\n").encode()


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def errors(root: Path, wheel: Path) -> list[str]:
    try:
        metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) > 5000:
                return ["Wheel inventory is ambiguous/oversized"]
            candidates = [
                n
                for n in names
                if n.count("/") == 1 and n.endswith(".dist-info/METADATA")
            ]
            if (
                len(candidates) != 1
                or archive.getinfo(candidates[0]).file_size > 1024 * 1024
            ):
                return ["Wheel distribution metadata is missing/ambiguous/oversized"]
            info = BytesParser().parsebytes(archive.read(candidates[0]))
            if (
                len(info.get_all("Name", [])) != 1
                or len(info.get_all("Version", [])) != 1
                or _normalized_name(info["Name"]) != _normalized_name(metadata["name"])
                or info["Version"] != metadata["version"]
                or info.get_all("Requires-Python", [])
                != (
                    [metadata["requires-python"]]
                    if "requires-python" in metadata
                    else []
                )
            ):
                return ["Wheel name/version/Python requirement differs from pyproject"]
            entry_name = candidates[0].rsplit("/", 1)[0] + "/entry_points.txt"
            scripts = {}
            if entry_name in names:
                if archive.getinfo(entry_name).file_size > 1024 * 1024:
                    return ["Wheel console declarations exceed the qualification limit"]
                entry = configparser.ConfigParser(interpolation=None)
                entry.optionxform = str
                entry.read_string(archive.read(entry_name).decode("utf-8"))
                if entry.defaults():
                    return ["Wheel entry-point defaults are unsupported"]
                if entry.has_section("console_scripts"):
                    scripts = dict(entry.items("console_scripts"))
            if scripts != metadata.get("scripts", {}):
                return ["Wheel console declarations differ from pyproject scripts"]
            selected = [
                n for n in names if n.startswith("framework/") and n.endswith(".py")
            ]
            if sum(archive.getinfo(n).file_size for n in selected) > 16 * 1024 * 1024:
                return ["Wheel SDK inventory exceeds the qualification limit"]
            packaged = {
                n: hashlib.sha256(_canonical(archive.read(n))).hexdigest()
                for n in selected
            }
        files = [
            p
            for p in (root / "framework").rglob("*.py")
            if "__pycache__" not in p.parts
        ]
        if not files or any(p.is_symlink() for p in files):
            return ["SDK source is missing or symlinked"]
        source = {
            p.relative_to(root).as_posix(): hashlib.sha256(
                _canonical(p.read_bytes())
            ).hexdigest()
            for p in files
        }
        return [] if packaged == source else ["Qualified wheel SDK differs from source"]
    except (
        OSError,
        ValueError,
        KeyError,
        configparser.Error,
        zipfile.BadZipFile,
        zlib.error,
    ) as error:
        return ["Release wheel verification failed: " + type(error).__name__]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    issues = errors(ROOT, args.wheel)
    print(
        "\n".join(issues)
        if issues
        else "Qualified wheel matches SDK source, name/version, Python and console declarations"
    )
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
