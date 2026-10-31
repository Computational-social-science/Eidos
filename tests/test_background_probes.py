"""Scheduled probes keep their output without opening interactive console windows."""
import os
import subprocess


def test_noninteractive_process_policy():
    from framework.subprocesses import quiet_flags
    assert quiet_flags() == (subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def test_process_command_probe_requests_hidden_console(monkeypatch):
    from types import SimpleNamespace
    from framework import recovery
    seen=[]
    def run(*a,**kw):
        seen.append(kw)
        return SimpleNamespace(returncode=0,stdout='python service.py',stderr='')
    monkeypatch.setattr(recovery.subprocess,'run',run)
    recovery.command_line(123)
    from framework.subprocesses import quiet_flags
    assert seen and seen[0].get('creationflags') == quiet_flags()
