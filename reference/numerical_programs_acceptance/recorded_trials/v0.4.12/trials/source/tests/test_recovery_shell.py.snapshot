"""A Windows recovery script requires MSYS paths, never WSL path guessing."""
from pathlib import Path
import os
from types import SimpleNamespace

import pytest

from framework import recovery


def windows(monkeypatch, tmp_path):
    monkeypatch.setattr(recovery, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.delenv('SHELL', raising=False)
    monkeypatch.delenv('EIDOS_BASH', raising=False)
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        monkeypatch.setenv(name, str(tmp_path/name))
    monkeypatch.setattr(recovery.shutil, 'which', lambda name: None)


def test_windows_does_not_fall_back_to_wsl(monkeypatch, tmp_path):
    windows(monkeypatch, tmp_path)
    wrong = tmp_path/'System32'/'bash.exe'
    wrong.parent.mkdir();wrong.touch()
    monkeypatch.setattr(recovery.shutil, 'which', lambda name: str(wrong))
    monkeypatch.setattr(recovery, '_msys_shell', lambda path: False, raising=False)
    with pytest.raises(OSError, match='MSYS'):
        recovery._shell()


def test_git_bash_wins_over_wsl_on_path(monkeypatch, tmp_path):
    windows(monkeypatch, tmp_path)
    git = tmp_path/'ProgramFiles'/'Git'/'bin'/'bash.exe'
    git.parent.mkdir(parents=True);git.touch()
    wrong = tmp_path/'bash.exe';wrong.touch()
    monkeypatch.setattr(recovery.shutil, 'which', lambda name: str(wrong))
    monkeypatch.setattr(recovery, '_msys_shell', lambda path: Path(path) == git, raising=False)
    assert Path(recovery._shell()) == git


def test_explicit_invalid_override_is_not_silently_ignored(monkeypatch, tmp_path):
    windows(monkeypatch, tmp_path)
    explicit = tmp_path/'wrong.exe';explicit.touch()
    monkeypatch.setenv('EIDOS_BASH', str(explicit))
    monkeypatch.setattr(recovery, '_msys_shell', lambda path: False, raising=False)
    with pytest.raises(OSError, match='EIDOS_BASH'):
        recovery._shell()


def test_posix_keeps_native_bash(monkeypatch, tmp_path):
    monkeypatch.setattr(recovery, 'sys', SimpleNamespace(platform='linux'))
    bash = tmp_path/'bash';bash.touch()
    monkeypatch.setenv('SHELL', str(bash))
    monkeypatch.delenv('EIDOS_BASH', raising=False)
    assert recovery._shell() == str(bash)


@pytest.mark.skipif(os.name != 'nt', reason='native Windows Git Bash path contract')
def test_actual_git_bash_reads_windows_source():
    git = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Git/bin/bash.exe'
    if not git.is_file():
        pytest.skip('Git for Windows not installed')
    assert recovery._msys_shell(str(git))


@pytest.mark.parametrize('platform', ['win32', 'linux'])
@pytest.mark.parametrize('configuration', ['relative', 'expanded'])
def test_override_binds_absolute_executable_before_cwd_changes(monkeypatch, tmp_path, platform, configuration):
    windows(monkeypatch, tmp_path)
    monkeypatch.setattr(recovery, 'sys', SimpleNamespace(platform=platform))
    directory = tmp_path/'Git with spaces';directory.mkdir()
    executable = directory/'bash.exe';executable.touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('EIDOS_SHELL_ROOT', str(directory))
    value = str(Path('Git with spaces')/'bash.exe') if configuration == 'relative' else '$EIDOS_SHELL_ROOT/bash.exe'
    monkeypatch.setenv('EIDOS_BASH', value)
    probes = []
    def probe(path):
        probes.append(path)
        return Path(path) == executable
    monkeypatch.setattr(recovery, '_msys_shell', probe)
    result = recovery._shell()
    assert Path(result).is_absolute() and Path(result) == executable
    if platform == 'win32':
        assert probes == [str(executable)]
    elsewhere = tmp_path/'service';elsewhere.mkdir();monkeypatch.chdir(elsewhere)
    assert Path(result).is_file()


def test_posix_relative_path_discovery_is_also_bound(monkeypatch, tmp_path):
    windows(monkeypatch, tmp_path)
    monkeypatch.setattr(recovery, 'sys', SimpleNamespace(platform='linux'))
    directory = tmp_path/'bin';directory.mkdir()
    executable = directory/'bash';executable.touch();monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(recovery.shutil, 'which', lambda name: 'bin/bash')
    assert recovery._shell() == str(executable)


def test_posix_missing_bash_is_refused_before_launch(monkeypatch, tmp_path):
    windows(monkeypatch, tmp_path)
    monkeypatch.setattr(recovery, 'sys', SimpleNamespace(platform='linux'))
    with pytest.raises(OSError, match='Bash'):
        recovery._shell()
