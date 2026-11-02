"""Release metadata must agree without weakening historical scientific provenance."""
import pytest
from framework.provenance import source_hash


def setup_project(root):
    (root / 'pyproject.toml').write_text('[project]\nname="eidos"\nversion="4.3.32"\n', encoding='utf-8')
    (root / 'uv.lock').write_text('version=1\n[[package]]\nname="eidos"\nversion="4.3.32"\nsource={editable="."}\n'
                                '[[package]]\nname="numpy"\nversion="2.5.4"\n', encoding='utf-8')


def test_bump_synchronizes_only_local_package_and_archives_original_lock(tmp_path):
    import tomllib
    from tools.versioning import bump
    setup_project(tmp_path)
    technical=tmp_path/'Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'
    technical.write_text('**实现基线：4.3.32；同步日期：2026-10-31。**',encoding='utf-8')
    original = (tmp_path / 'uv.lock').read_bytes()
    assert bump('patch', tmp_path) == '4.3.33'
    assert '**实现基线：4.3.33' in technical.read_text(encoding='utf-8')
    doc = tomllib.loads((tmp_path / 'uv.lock').read_text())
    assert [p['version'] for p in doc['package']] == ['4.3.33', '2.5.4']
    assert (tmp_path / 'lock/snapshots/uv' / (source_hash(original)+'.lock')).read_bytes() == original


def test_failed_lock_write_rolls_back_project_version(tmp_path, monkeypatch):
    from tools import versioning
    setup_project(tmp_path)
    original = (tmp_path / 'pyproject.toml').read_bytes()
    actual = versioning.atomic_bytes
    def fail(path, content):
        if path.name == 'uv.lock':
            raise PermissionError('locked')
        actual(path, content)
    monkeypatch.setattr(versioning, 'atomic_bytes', fail)
    with pytest.raises(PermissionError):
        versioning.bump('patch', tmp_path)
    assert (tmp_path / 'pyproject.toml').read_bytes() == original


def test_release_coherence_detects_stale_history_and_page(tmp_path):
    from tools.versioning import consistency_errors
    setup_project(tmp_path)
    (tmp_path / 'site').mkdir()
    (tmp_path / 'site/versions.json').write_text('[{"version":"4.1.0"}]')
    (tmp_path / 'site/index.html').write_text('<span class="ver">v4.0.0</span>')
    (tmp_path / 'README.md').write_text('**Version 4.3.32**')
    errors = consistency_errors(tmp_path)
    assert any('history' in e for e in errors) and any('index' in e for e in errors)


@pytest.mark.parametrize('wrong',['4.3.320','4.3.32.9'])
def test_technical_version_prefix_cannot_satisfy_consistency(tmp_path,wrong):
    from tools.versioning import consistency_errors
    setup_project(tmp_path)
    (tmp_path/'site').mkdir()
    (tmp_path/'site/versions.json').write_text('[{"version":"4.3.32"}]')
    (tmp_path/'site/index.html').write_text('<span class="ver">v4.3.32</span>')
    (tmp_path/'README.md').write_text('**Version 4.3.32**')
    (tmp_path/'Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md').write_text(f'**实现基线：{wrong}；日期。**',encoding='utf-8')
    assert consistency_errors(tmp_path)==['technical framework version disagrees with project']


def test_same_release_is_idempotent_but_different_source_cannot_reuse_version():
    from tools.versioning import append_release
    entry = {'version':'4.3.33', 'commit':'aaa', 'source_commit':'aaa'}
    assert append_release([entry], entry) == [entry]
    with pytest.raises(ValueError):
        append_release([entry], {**entry, 'commit':'bbb', 'source_commit':'bbb'})


@pytest.mark.parametrize('change', ['version', 'dependency', 'field', 'corrupt', 'missing','schema_bool','schema_float'])
def test_archived_lock_accepts_only_local_version_metadata(tmp_path, change):
    from framework.provenance import historical_lock_matches
    setup_project(tmp_path)
    lock = tmp_path / 'uv.lock'
    old = lock.read_bytes()
    digest = source_hash(old)
    archive = tmp_path / 'lock/snapshots/uv' / (digest+'.lock')
    archive.parent.mkdir(parents=True)
    archive.write_bytes(old)
    text = old.decode().replace('4.3.32', '4.3.33')
    if change == 'dependency':
        text = text.replace('2.5.4', '2.6.0')
    elif change == 'field':
        text = text.replace('editable="."', 'editable="elsewhere"')
    elif change == 'corrupt':
        archive.write_text('bad archive')
    elif change == 'missing':
        archive.unlink()
    elif change == 'schema_bool':
        text = text.replace('version=1','version=true',1)
    elif change == 'schema_float':
        text = text.replace('version=1','version=1.0',1)
    lock.write_bytes(text.encode())
    assert historical_lock_matches(tmp_path, digest) is (change == 'version')


def test_release_render_failure_restores_metadata_and_existing_artifacts(tmp_path):
    from tools.versioning import release_transaction, set_version
    setup_project(tmp_path)
    folder=tmp_path/'site/reports/numerics';folder.mkdir(parents=True)
    artifact=folder/'report.html';artifact.write_bytes(b'old verified report')
    original=(tmp_path/'pyproject.toml').read_bytes()
    with pytest.raises(RuntimeError):
        with release_transaction(tmp_path):
            set_version('0.4.1',tmp_path)
            artifact.write_bytes(b'failed new report')
            (folder/'new-incomplete.json').write_bytes(b'incomplete')
            raise RuntimeError('renderer failed')
    assert (tmp_path/'pyproject.toml').read_bytes()==original
    assert artifact.read_bytes()==b'old verified report'
    assert not (folder/'new-incomplete.json').exists()
