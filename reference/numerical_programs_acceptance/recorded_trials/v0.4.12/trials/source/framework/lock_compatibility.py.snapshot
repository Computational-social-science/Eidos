"""Narrow attestation of frozen resolution after the tracking-minimum migration.

This does not change historical_lock_matches, replay training, prove installed
runtime equivalence, or permit third-party resolution/artifact changes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import tomllib

from framework.provenance import _typed_equal, source_hash

POLICY = "eidos.tracking-minima-frozen-resolution.v1"
_BOUNDS = {"mlflow": (">=2.10", ">=3.17.2"), "dvc": (">=3.0", ">=3.67.1")}
_EXTRAS = {"extra == 'tracking'", "extra == 'all'"}


def frozen_tracking_resolution(root: Path, recorded: str) -> dict:
    """Require original lock provenance and the same frozen third-party graph."""
    result = {
        "policy": POLICY,
        "status": "INCOMPATIBLE_FROZEN_RESOLUTION",
        "scope": "Frozen resolution only; no runtime, training or future re-resolution equivalence.",
        "changes": [],
    }
    try:
        if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded):
            raise ValueError("invalid recorded lock digest")
        root = Path(root)
        current = (root / "uv.lock").read_bytes()
        original_path = (
            Path("uv.lock")
            if source_hash(current) == recorded
            else Path("lock/snapshots/uv") / (recorded + ".lock")
        )
        original = (root / original_path).read_bytes()
        if source_hash(original) != recorded:
            raise ValueError("original archived lock digest differs")
        old, new = [
            tomllib.loads(body.decode("utf-8-sig")) for body in (original, current)
        ]
        result.update(
            original_lock=original_path.as_posix(),
            original_canonical_sha256=recorded,
            original_raw_sha256=hashlib.sha256(original).hexdigest(),
            delivery_canonical_sha256=source_hash(current),
            delivery_raw_sha256=hashlib.sha256(current).hexdigest(),
        )
        _normalize_markers(old, new, result["changes"])
        old_local, new_local = _local(old), _local(new)
        for local in (old_local, new_local):
            if not isinstance(local.get("version"), str) or not re.fullmatch(
                r"\d+\.\d+\.\d+", local["version"]
            ):
                raise ValueError("invalid local project version")
        if old_local["version"] != new_local["version"]:
            result["changes"].append(
                {
                    "field": "eidos.version",
                    "from": old_local["version"],
                    "to": new_local["version"],
                }
            )
            old_local["version"] = new_local["version"]
        old_requirements, new_requirements = [
            _requirements(local) for local in (old_local, new_local)
        ]
        if len(old_requirements) != len(new_requirements):
            raise ValueError("local requirements added or removed")
        for before, after in zip(old_requirements, new_requirements):
            if _identity(before) != _identity(after):
                raise ValueError("local requirement identity/order differs")
            if _typed_equal(before, after):
                continue
            before_other = {
                key: value for key, value in before.items() if key != "specifier"
            }
            after_other = {
                key: value for key, value in after.items() if key != "specifier"
            }
            if not _typed_equal(before_other, after_other):
                raise ValueError("local requirement fields other than specifier differ")
            name = before["name"]
            bounds = (before.get("specifier"), after.get("specifier"))
            if (
                name not in _BOUNDS
                or bounds != _BOUNDS[name]
                or before.get("marker") not in _EXTRAS
                or before.get("extras")
            ):
                raise ValueError(
                    "requirement change is outside the explicit tracking policy"
                )
            _verify_candidates(old, name, bounds)
            result["changes"].append(
                {
                    "field": "eidos.requires-dist.specifier",
                    "name": name,
                    "marker": before["marker"],
                    "from": bounds[0],
                    "to": bounds[1],
                }
            )
            before["specifier"] = after["specifier"]
        if not _typed_equal(old, new):
            raise ValueError("remaining lock graph/policy/artifact fields differ")
        result["status"] = "COMPATIBLE_FROZEN_RESOLUTION"
        result["unchanged_third_party_records"] = True
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, ImportError) as exc:
        result["error"] = (
            str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        )
    return result


def _local(document):
    packages = document.get("package")
    if not isinstance(packages, list):
        raise ValueError("lock packages must be a list")
    found = [
        entry
        for entry in packages
        if isinstance(entry, dict)
        and entry.get("name") == "eidos"
        and entry.get("source") == {"editable": "."}
    ]
    if len(found) != 1:
        raise ValueError("one local editable eidos package is required")
    return found[0]


def _requirements(local):
    metadata = local.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("local metadata must be a mapping")
    entries = metadata.get("requires-dist", [])
    if not isinstance(entries, list):
        raise ValueError("requires-dist must be a list")
    identities = [_identity(entry) for entry in entries]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate local requirement identity")
    return entries


def _identity(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
        raise ValueError("invalid local requirement")
    extras = entry.get("extras", [])
    marker = entry.get("marker", "")
    if (
        not isinstance(extras, list)
        or not all(isinstance(item, str) for item in extras)
        or not isinstance(marker, str)
    ):
        raise ValueError("invalid requirement identity")
    return entry["name"], marker, tuple(extras)


def _normalize_markers(old, new, changes):
    def collect(document):
        positions = [("root", document)]
        packages = document.get("package", [])
        if not isinstance(packages, list):
            raise ValueError("lock packages must be a list")
        positions.extend(
            (f"package[{index}]", entry) for index, entry in enumerate(packages)
        )
        found = {}
        for path, mapping in positions:
            if not isinstance(mapping, dict):
                raise ValueError("lock package must be a mapping")
            if "resolution-markers" in mapping:
                values = mapping["resolution-markers"]
                if not isinstance(values, list) or not all(
                    isinstance(value, str) for value in values
                ):
                    raise ValueError("resolution markers must be string lists")
                found[path] = list(values)
                mapping["resolution-markers"] = sorted(values)
        return found

    before, after = collect(old), collect(new)
    for path in sorted(before.keys() | after.keys()):
        if before.get(path) != after.get(path):
            if (
                path not in before
                or path not in after
                or sorted(before[path]) != sorted(after[path])
            ):
                raise ValueError("resolution marker literals/multiplicity differ")
            changes.append(
                {
                    "field": path + ".resolution-markers.order",
                    "from": before[path],
                    "to": after[path],
                }
            )


def _verify_candidates(document, name, bounds):
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version

    candidates = [entry for entry in document["package"] if entry.get("name") == name]
    if not candidates:
        raise ValueError("no frozen candidate for changed requirement")
    identities = set()
    for candidate in candidates:
        source = candidate.get("source")
        if (
            not isinstance(source, dict)
            or set(source) != {"registry"}
            or not isinstance(source["registry"], str)
            or not source["registry"]
        ):
            raise ValueError("candidate has no verifiable registry identity")
        version = candidate.get("version")
        if not isinstance(version, str):
            raise ValueError("candidate version must be a string")
        parsed = Version(version)
        if not all(SpecifierSet(bound).contains(parsed) for bound in bounds):
            raise ValueError("frozen candidate does not satisfy both constraints")
        identity = (
            str(parsed),
            source["registry"],
            tuple(candidate.get("resolution-markers", [])),
        )
        if identity in identities:
            raise ValueError("ambiguous duplicate frozen candidate")
        identities.add(identity)
        artifacts = [*candidate.get("wheels", [])]
        if "sdist" in candidate:
            artifacts.append(candidate["sdist"])
        if not artifacts:
            raise ValueError("candidate has no frozen artifacts")
        for artifact in artifacts:
            if (
                not isinstance(artifact, dict)
                or not isinstance(artifact.get("hash"), str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["hash"])
                or not isinstance(artifact.get("url"), str)
                or not artifact["url"]
                or type(artifact.get("size")) is not int
                or artifact["size"] <= 0
            ):
                raise ValueError("candidate artifact identity is unverifiable")
