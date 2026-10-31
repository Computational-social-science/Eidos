"""Install one per-user hidden monitor entry; preserve existing runtime configuration."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def startup_script(runner: Path) -> str:
    literal=str(runner.resolve()).replace('"','""')
    return ('Option Explicit\nDim shell, q\nSet shell = CreateObject("WScript.Shell")\nq = Chr(34)\n'
            f'shell.Run "wscript.exe " & q & "{literal}" & q, 0, False\n')


def runtime_assignment(executable: str) -> str:
    if any(c in executable for c in ('"','\r','\n','%')):
        raise ValueError('configure an interpreter path without quotes, newlines or percent signs')
    return f'set "PYTHON={executable}"\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remove',action='store_true')
    parser.add_argument('--no-start',action='store_true')
    args=parser.parse_args(argv)
    if os.name!='nt':
        parser.error('Windows per-user Startup installer; use the platform service manager elsewhere')
    startup=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup'
    startup.mkdir(parents=True,exist_ok=True)
    target=startup/'eidos-monitor.vbs'
    legacy=startup/'eidos-monitor.cmd'
    for entry in (target,legacy):
        if entry.exists():
            content=entry.read_bytes()
            text=content.decode('utf-16' if content.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
            if 'eidos-monitor' not in text.lower():
                raise ValueError('existing Startup entry is not an EIDOS launcher')
    if args.remove:
        target.unlink(missing_ok=True);legacy.unlink(missing_ok=True)
        print('Removed EIDOS Startup entries; running service is unchanged')
        return 0
    envfile=ROOT/'scripts/monitor.env'
    if not envfile.exists():
        envfile.write_text(runtime_assignment(sys.executable),encoding='utf-8')
    target.write_text(startup_script(ROOT/'scripts/eidos-monitor.vbs'),encoding='utf-16')
    legacy.unlink(missing_ok=True)
    if not args.no_start:
        subprocess.Popen(['wscript.exe',str(ROOT/'scripts/eidos-monitor.vbs')],
                         cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Installed one hidden EIDOS monitor Startup entry')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
