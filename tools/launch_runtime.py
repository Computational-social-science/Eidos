"""Load literal runtime configuration before starting a hidden project process."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

CHECK_SCRIPT='''import json,os,sys
window=None
if os.name=="nt":
 import ctypes
 get=ctypes.windll.kernel32.GetConsoleWindow
 get.restype=ctypes.c_void_p
 window=int(get() or 0)
print(json.dumps({"executable":sys.executable,"python":sys.version.split()[0],
 "platform":sys.platform,"isolated":bool(sys.flags.isolated),
 "utf8_mode":bool(sys.flags.utf8_mode),"console_window":window,
 "pythonpath_present":bool(os.environ.get("PYTHONPATH")),
 "pythonhome_present":bool(os.environ.get("PYTHONHOME"))}))
'''


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',choices=('monitor','install'))
    parser.add_argument('legacy_action',nargs='?',choices=('remove',))
    parser.add_argument('--check',action='store_true',help='probe runtime selection without starting services or installing Startup entries')
    parser.add_argument('--remove',action='store_true')
    parser.add_argument('--no-start',action='store_true')
    args=parser.parse_args(argv)
    if args.legacy_action=='remove':args.remove=True
    if args.target=='monitor' and (args.remove or args.no_start):
        parser.error('--remove and --no-start apply only to the Startup installer')
    # The configuration reader is stdlib-only under a non-main name. Do not import
    # a scheduler/global environment's potentially unrelated regular tools package.
    configuration=runpy.run_path(str(ROOT/'tools/cron_entry.py'),run_name='_eidos_runtime_config')
    configured=configuration['runtime'](ROOT)
    environment=os.environ.copy()
    for name in ('PYTHONPATH','PYTHONHOME'):environment.pop(name,None)
    environment.update(PYTHON=configured['PYTHON'],PYTHONUTF8='1')
    environment['QUARTO_BIN']=configured.get('QUARTO_BIN') or environment.get('QUARTO_BIN') or str(ROOT.parent/'tools/quarto/bin/quarto.exe')
    command=[configured['PYTHON'],'-I','-X','utf8']
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    try:
        if args.check:
            bounded=runpy.run_path(str(ROOT/'tools/bounded_process.py'),run_name='_eidos_runtime_process')
            result=bounded['run_tree']([*command,'-c',CHECK_SCRIPT],cwd=ROOT,timeout=30,env=environment)
            if result.returncode:
                print(result.stderr,file=sys.stderr,end='')
                return result.returncode
            record=json.loads(result.stdout)
            record.update(bootstrap_python=sys.executable,configured_python=configured['PYTHON'],
                          scope='Runtime-selection probe only; no service started or Startup entry changed.')
            print(json.dumps(record))
            return 0
        if args.target=='install':
            command += [str(ROOT/'tools/install_autostart.py')]
            if args.remove:command.append('--remove')
            if args.no_start:command.append('--no-start')
            return subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,
                                  creationflags=flags).returncode
        command += [str(ROOT/'tools/monitor_supervisor.py')]
        log=ROOT/'docs/status/supervisor.out'
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('a',encoding='utf-8') as output:
            return subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,
                                  stdout=output,stderr=output,creationflags=flags).returncode
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
        print('EIDOS runtime launch failed: '+ascii(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
