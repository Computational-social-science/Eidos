"""The availability probe must own inherited pipes, not just its root timeout."""
from __future__ import annotations

import json
import inspect
import shlex
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from framework.subprocesses import run_tree


ROOT = Path(__file__).resolve().parents[1]


def process_alive(pid: int) -> bool:
    """Independent process query, evaluated before the outer owner cleans up."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return False
            raise ctypes.WinError(error)
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ctypes.WinError(ctypes.get_last_error())
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    if Path('/proc/self/stat').is_file():
        try:
            state = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(') ', 1)[1]
        except FileNotFoundError:
            return False
        return not state.startswith('Z ')
    return True


def fake_ollama(folder: Path, mode: str) -> None:
    """A private CLI; never launches or contacts the host's Ollama service."""
    folder.mkdir()
    if mode == 'missing':
        return
    if os.name == 'nt':
        base = Path(sys.base_prefix)
        shutil.copy2(base / 'python.exe', folder / 'ollama.exe')
        dll = f'python{sys.version_info.major}{sys.version_info.minor}.dll'
        shutil.copy2(base / dll, folder / dll)
        # Only the fake executable gets an explicit stdlib; the worker's actual
        # interpreter/environment remain unchanged.
        (folder / dll.replace('.dll', '._pth')).write_text(
            str(base / 'Lib') + '\n' + str(base / 'DLLs') + '\n', encoding='utf-8')
    else:
        cli = folder / 'ollama'
        cli.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' list "$@"\n',
                       encoding='utf-8')
        cli.chmod(0o700)
    if mode == 'failure':
        script = 'raise SystemExit(3)\n'
    else:
        script = '''import subprocess,sys,time
from pathlib import Path
child = "from pathlib import Path; import time,os; Path('descendant-ready').write_text(str(os.getpid())); time.sleep(30); Path('late').write_text('escaped')"
subprocess.Popen([sys.executable, '-c', child])
deadline = time.monotonic()+5
while not Path('descendant-ready').exists():
    if time.monotonic()>deadline: raise RuntimeError('child did not start')
    time.sleep(.01)
Path('client-finished').write_text('root exiting')
print('NAME ID SIZE MODIFIED',flush=True)
'''
    (folder / 'list').write_text(script, encoding='utf-8')


@pytest.mark.parametrize('mode,expected', [('inherited', True), ('failure', False), ('missing', False)])
def test_private_probe_closes_descendants_and_reports_cli_outcome(tmp_path, mode, expected):
    folder = tmp_path / mode
    fake_ollama(folder, mode)
    code = ('import sys,json,os\nfrom pathlib import Path\n'
            'sys.path.insert(0,sys.argv[1])\n'
            'from framework.inference import ModelManager\n' + inspect.getsource(process_alive) +
            '\nvalue=ModelManager().ollama_available\n'
            'marker=Path("descendant-ready")\n'
            'alive=process_alive(int(marker.read_text())) if marker.exists() else False\n'
            'print(json.dumps({"available":value,"descendant_running_after_probe":alive}),flush=True)')
    try:
        result = run_tree([sys.executable, '-X', 'utf8', '-c', code, str(ROOT)],
                          cwd=folder, env=dict(os.environ, PATH=str(folder)), timeout=7)
    except subprocess.TimeoutExpired as error:
        if mode == 'inherited':
            assert (folder / 'descendant-ready').is_file(), 'child never started; invalid counterfactual'
            assert (folder / 'client-finished').is_file(), 'root never finished; invalid counterfactual'
        pytest.fail('availability probe outlived its root because inherited pipes stayed open: ' + str(error))
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed['available'] is expected
    assert observed['descendant_running_after_probe'] is False
    if mode == 'inherited':
        assert (folder / 'descendant-ready').is_file(), 'counterfactual child must really start'
        assert (folder / 'client-finished').is_file(), 'root must finish before timeout'
        assert not (folder / 'late').exists()


def test_probe_does_not_hide_programming_errors(monkeypatch):
    from framework.inference import ModelManager
    import framework.subprocesses as processes

    def invalid(*args, **kwargs):
        raise ValueError('invalid caller configuration')

    # Keep the pre-fix counterfactual away from the real host CLI as well.
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 1))
    monkeypatch.setattr(processes, 'run_tree', invalid)
    with pytest.raises(ValueError, match='invalid caller configuration'):
        ModelManager()


@pytest.mark.parametrize('kind', ['missing', 'os', 'timeout', 'containment'])
def test_operational_probe_errors_report_unavailable(monkeypatch, kind):
    from framework.inference import ModelManager
    import framework.subprocesses as processes

    error = {'missing': FileNotFoundError('private missing CLI'),
             'os': OSError('private launch failure'),
             'timeout': subprocess.TimeoutExpired(['private-ollama'], 10),
             'containment': processes.ProcessContainmentError('private ownership failure')}[kind]

    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setattr(processes, 'run_tree', unavailable)
    assert ModelManager().ollama_available is False
