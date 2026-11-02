"""Wheel identity checks reused verbatim from numerical_programs_acceptance/check.py v0.4.11."""

from __future__ import annotations

import argparse

import base64

import csv

from datetime import datetime, timezone

from decimal import Decimal, localcontext

from email.parser import BytesParser

import hashlib

from importlib.metadata import distribution, distributions

import io

import json

from pathlib import Path

import sys

import time

import zipfile

import numpy as np

from packaging.requirements import Requirement

from packaging.utils import canonicalize_name

import framework.numerical_programs as api

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def digest(body):
    return hashlib.sha256(body).hexdigest()

def identity(wheel, expected_version):
    """Bind actual installed bytes, metadata, RECORD and all framework modules."""
    dist = distribution('eidos')
    prefix = Path(sys.prefix).resolve()
    module = Path(api.__file__).resolve()
    require(sys.flags.isolated == 1 and sys.flags.no_site == 0,
            'Run with -I and ordinary site initialization')
    require(sys.prefix != sys.base_prefix and module.is_relative_to(prefix),
            'A non-editable virtual environment is required')
    require(dist.version == expected_version, 'Installed version differs')
    body = wheel.read_bytes()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate wheel members')
        info = 'eidos-' + expected_version + '.dist-info/'
        metadata = BytesParser().parsebytes(archive.read(info + 'METADATA'))
        require(metadata['Name'] == 'eidos' and metadata['Version'] == expected_version,
                'Wheel METADATA identity differs')
        rows = list(csv.reader(io.StringIO(archive.read(info + 'RECORD').decode())))
        require(len(rows) == len(names) and set(names) == {row[0] for row in rows},
                'RECORD inventory differs')
        for name, encoded, size in rows:
            require(not Path(name).is_absolute() and '..' not in Path(name).parts
                    and '\\' not in name and '.data/' not in name, 'Unsupported wheel path')
            content = archive.read(name)
            if name == info + 'RECORD':
                require(encoded == size == '', 'RECORD self-entry differs')
                continue
            expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip('=')
            require(encoded == expected and size == str(len(content)), 'Wheel RECORD hash differs')
            installed = Path(dist.locate_file(name)).resolve()
            require(installed.is_relative_to(prefix) and installed.read_bytes() == content,
                    'Installed wheel member differs: ' + name)
        expected = {name: digest(archive.read(name)) for name in names
                    if name.startswith('framework/') and name.endswith('.py')}
        expected_lf = {name: digest(archive.read(name).decode('utf-8-sig').replace('\r\n', '\n').encode())
                       for name in expected}
    framework = module.parents[1]
    actual = {'framework/' + path.relative_to(framework).as_posix(): digest(path.read_bytes())
              for path in framework.rglob('*.py')}
    require(actual == expected and 'framework/numerical_programs/__init__.py' in actual,
            'Full framework inventory differs')
    installed_record = {p.as_posix(): p for p in dist.files or []}
    for name, sha in expected.items():
        entry = installed_record[name]
        require(entry.hash is not None and entry.hash.mode == 'sha256'
                and base64.urlsafe_b64encode(bytes.fromhex(sha)).decode().rstrip('=') == entry.hash.value,
                'Installed RECORD differs: ' + name)
    installed_distributions = list(distributions())
    packages = {canonicalize_name(d.metadata['Name']): d for d in installed_distributions}
    require(len(packages) == len(installed_distributions), 'Duplicate installed distributions')
    require(all(Path(d.locate_file('')).resolve().is_relative_to(prefix) for d in packages.values()),
            'Host distributions leaked into the virtual environment')
    require(Path(np.__file__).resolve().is_relative_to(prefix), 'NumPy imported outside the virtual environment')
    for package in packages.values():
        for raw in package.requires or []:
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate({'extra': ''}):
                target = packages.get(canonicalize_name(req.name))
                require(target is not None and req.specifier.contains(target.version, prereleases=True),
                        'Unmet installed dependency: ' + raw)
    dependency_metadata = {}
    for name, package in packages.items():
        files = {}
        for filename in ('METADATA', 'RECORD'):
            text = package.read_text(filename)
            require(text is not None, 'Installed distribution lacks ' + filename + ': ' + name)
            files[filename] = digest(text.replace('\r\n', '\n').encode())
        dependency_metadata[name] = files
    return {'sdk_version': dist.version, 'wheel_sha256': digest(body),
            'wheel_name': wheel.name, 'installed_module': str(module), 'prefix': str(prefix),
            'source_sha256_raw': actual, 'source_sha256_canonical_lf': expected_lf,
            'module_count': len(actual),
            'dependencies': sorted((name, d.version) for name, d in packages.items()),
            'dependency_metadata_sha256_lf': dependency_metadata,
            'all_installed_metadata_requirements_met': True}
