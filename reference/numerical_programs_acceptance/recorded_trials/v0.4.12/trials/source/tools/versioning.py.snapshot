"""Release-label consistency. Run `python tools/versioning.py --check`."""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def bump(kind: str, root: Path = ROOT) -> str:
    if kind not in {'patch', 'minor', 'major'}:
        raise ValueError('invalid version increment')
    metadata = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8-sig'))['project']
    version = metadata['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('a three-part release version is required')
    major, minor, patch = map(int, version.split('.'))
    if kind == 'major':
        major, minor, patch = major+1, 0, 0
    elif kind == 'minor':
        minor, patch = minor+1, 0
    else:
        patch += 1
    new = f'{major}.{minor}.{patch}'
    return set_version(new, root)


def set_version(new: str, root: Path = ROOT) -> str:
    """Explicit version migration; historical tags and records remain intact."""
    from framework.provenance import source_hash
    if not re.fullmatch(r'\d+\.\d+\.\d+', new):
        raise ValueError('a three-part release version is required')
    project, lock = root / 'pyproject.toml', root / 'uv.lock'
    originals = {p: p.read_bytes() for p in (project, lock)}
    text = originals[project].decode('utf-8-sig')
    metadata = tomllib.loads(text)['project']
    version = metadata['version']
    table = re.search(r'(?ms)^\[project\]\s*\n(.*?)(?=^\[|\Z)', text)
    if not table:
        raise ValueError('project table missing')
    body, count = re.subn(r'(?m)^version\s*=\s*"[^"\n]+"', f'version = "{new}"', table[1])
    if count != 1:
        raise ValueError('one static project version required')
    updated_project = text[:table.start(1)] + body + text[table.end(1):]
    lock_text = originals[lock].decode('utf-8-sig')
    blocks = list(re.finditer(r'(?ms)^\[\[package\]\]\s*\n.*?(?=^\[\[package\]\]|\Z)', lock_text))
    candidates = [m for m in blocks if tomllib.loads(m[0])['package'][0].get('name') == metadata['name']]
    if len(candidates) != 1:
        raise ValueError('one local lock entry required')
    entry = candidates[0]
    local = tomllib.loads(entry[0])['package'][0]
    if local.get('version') != version or local.get('source') != {'editable': '.'}:
        raise ValueError('project and editable lock version disagree')
    updated_entry, count = re.subn(r'(?m)^version\s*=\s*"[^"\n]+"', f'version = "{new}"', entry[0], count=1)
    if count != 1:
        raise ValueError('local lock version missing')
    updated_lock = lock_text[:entry.start()] + updated_entry + lock_text[entry.end():]
    snapshot = root / 'lock/snapshots/uv' / (source_hash(originals[lock])+'.lock')
    if snapshot.exists() and source_hash(snapshot.read_bytes()) != source_hash(originals[lock]):
        raise ValueError('historical lock collision')
    if not snapshot.exists():
        atomic_bytes(snapshot, originals[lock])
    updates = [(project,updated_project.encode()),(lock,updated_lock.encode())]
    readme = root/'README.md'
    if readme.is_file():
        originals[readme] = readme.read_bytes()
        body = originals[readme].decode('utf-8-sig')
        body, count = re.subn(r'\*\*Version [0-9]+\.[0-9]+\.[0-9]+\*\*',f'**Version {new}**',body,count=1)
        if count != 1:
            raise ValueError('README has no release version marker')
        updates.append((readme,body.encode()))
    technical=root/'Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'
    if technical.is_file():
        originals[technical]=technical.read_bytes()
        body=originals[technical].decode('utf-8-sig')
        body,count=re.subn(r'(\*\*实现基线：)[0-9]+\.[0-9]+\.[0-9]+',lambda m:m[1]+new,body,count=1)
        if count!=1:
            raise ValueError('technical framework has no release version marker')
        updates.append((technical,body.encode()))
    written = []
    try:
        for path, content in updates:
            atomic_bytes(path, content)
            written.append(path)
    except BaseException:
        for path in reversed(written):
            atomic_bytes(path, originals[path])
        raise
    return new


@contextmanager
def release_transaction(root: Path = ROOT):
    from framework.artifacts import output_lock
    with output_lock(root/'site'), output_lock(root/'site/reports/numerics'):
        with _release_transaction(root):
            yield


@contextmanager
def _release_transaction(root: Path):
    """Restore canonical release files and generated numerical outputs on failure."""
    paths = [root/p for p in ('pyproject.toml','uv.lock','README.md','Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md','site/versions.json','site/index.html',
                             'site/README.md','site/Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md')]
    generated = [root/'site/reports/numerics',root/'site/docs']
    paths += [p for folder in generated if folder.exists() for p in folder.rglob('*') if p.is_file()]
    originals = {p:p.read_bytes() if p.is_file() else None for p in paths}
    try:
        yield
    except BaseException:
        for folder in generated:
            if folder.exists():
                for path in folder.rglob('*'):
                    if path.is_file() and path not in originals:
                        if not path.resolve().is_relative_to((root/'site').resolve()):
                            raise RuntimeError('refusing rollback outside publication tree')
                        path.unlink()
        for path,content in originals.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_bytes(path,content)
        raise


def append_release(history: list[dict], entry: dict) -> list[dict]:
    matches = [r for r in history if r.get('version') == entry['version']]
    if matches:
        source = lambda r: r.get('source_commit') or r.get('commit')
        if len(matches) != 1 or source(matches[0]) != source(entry):
            raise ValueError('version already recorded for another source; increment it')
        return [entry if r is matches[0] else r for r in history]
    return (history + [entry])[-50:]


def consistency_errors(root: Path = ROOT) -> list[str]:
    errors = []
    try:
        version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
        lock = tomllib.loads((root / 'uv.lock').read_text(encoding='utf-8'))
        local = [p for p in lock['package'] if p.get('name') == 'eidos' and p.get('source') == {'editable': '.'}]
        if len(local) != 1 or local[0].get('version') != version:
            errors.append('editable lock version disagrees with project')
        history = json.loads((root / 'site/versions.json').read_text(encoding='utf-8'))
        if not history or history[-1].get('version') != version:
            errors.append('release history is behind project version')
        if f'<span class="ver">v{version}</span>' not in (root / 'site/index.html').read_text(encoding='utf-8'):
            errors.append('index version disagrees with project')
        if f'**Version {version}**' not in (root / 'README.md').read_text(encoding='utf-8'):
            errors.append('README version disagrees with project')
        technical=root/'Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'
        if technical.is_file():
            marker=re.search(r'\*\*实现基线：([0-9]+\.[0-9]+\.[0-9]+)(?=[；\s（(*]|$)',technical.read_text(encoding='utf-8'))
            if not marker or marker[1]!=version:
                errors.append('technical framework version disagrees with project')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f'release metadata unreadable: {type(exc).__name__}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True)
    parser.parse_args()
    problems = consistency_errors()
    print('\n'.join(problems) if problems else 'Release labels and history agree')
    raise SystemExit(1 if problems else 0)
