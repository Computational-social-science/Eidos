"""Route two existing Hermes EIDOS jobs through the quiet project cron entry.

The scheduler's jobs, intervals and delivery policy are not changed. Existing
EIDOS shims are backed up; unrelated script files are never replaced.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def shim(kind: str, root: Path = ROOT) -> str:
    entry=str(root/'tools/cron_entry.py')
    return f'''"""EIDOS managed scheduler shim; configuration lives in the project."""
import os
import runpy
import subprocess
import sys

entry={entry!r}
# Load only the stdlib configuration reader in the scheduler's environment.
configuration=runpy.run_path(entry,run_name="_eidos_scheduler_config")
configured=configuration["runtime"]()
environment=os.environ.copy()
# Descendants run without -I; do not reintroduce the scheduler's import/ABI paths.
environment.pop("PYTHONPATH",None)
environment.pop("PYTHONHOME",None)
environment["PYTHONUTF8"]="1"
# A fresh isolated interpreter removes scheduler PYTHONPATH and imported-module state.
result=subprocess.run([configured["PYTHON"],"-I","-X","utf8",entry,{kind!r}],
                      stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr,
                      env=environment,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
raise SystemExit(result.returncode)
'''


def install(home: Path, root: Path = ROOT) -> list[str]:
    from framework.artifacts import atomic_output
    folder=home/'scripts'
    if not folder.is_dir():
        raise ValueError('existing Hermes scripts directory required')
    plans=[]
    for kind,name in (('watchdog','eidos_watchdog.py'),('contracts','eidos_contracts.py')):
        path=folder/name
        if not path.is_file():
            raise ValueError('existing EIDOS shim required: '+name)
        original=path.read_bytes()
        if 'eidos' not in original.decode('utf-8-sig').lower():
            raise ValueError('refusing to replace unrelated script: '+name)
        content=shim(kind,root).encode('utf-8')
        compile(content,str(path),'exec')
        if content==original:
            continue
        backup=root/'.scratch/cron-backups'/hashlib.sha256(original).hexdigest()/name
        if backup.exists() and backup.read_bytes()!=original:
            raise ValueError('backup collision')
        plans.append((path,original,content,backup))
    # Preflight both existing jobs before mutating either one.
    for path,original,content,backup in plans:
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            backup.write_bytes(original)
    written=[]
    try:
        for path,original,content,backup in plans:
            with atomic_output(path) as temporary:
                temporary.write_bytes(content)
            written.append((path,original))
    except BaseException:
        for path,original in reversed(written):
            with atomic_output(path) as temporary:
                temporary.write_bytes(original)
        raise
    return [path.name for path,_,_,_ in plans]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    default=Path(os.environ['LOCALAPPDATA'])/'hermes' if os.name=='nt' else Path.home()/'.hermes'
    parser.add_argument('--home',type=Path,default=default)
    args=parser.parse_args()
    print('Updated EIDOS shims: '+(', '.join(install(args.home)) or 'already current'))
