"""Quiet scheduled checks, using the configured project interpreter and captured logs."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def runtime(root: Path = ROOT) -> dict:
    result={'PYTHON':os.environ.get('EIDOS_PYTHON') or sys.executable}
    path=root/'scripts/monitor.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            match=re.fullmatch(r'\s*set\s+"?(PYTHON|QUARTO_BIN)=(.*?)"?\s*',line,re.I)
            if match and match[2].strip(): result[match[1].upper()]=os.path.expandvars(match[2].strip())
    if os.environ.get('EIDOS_PYTHON'): result['PYTHON']=os.environ['EIDOS_PYTHON']
    return result


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=('watchdog','contracts'))
    args=parser.parse_args(argv)
    configured=runtime()
    if configured.get('QUARTO_BIN'): os.environ['QUARTO_BIN']=configured['QUARTO_BIN']
    from tools.bounded_process import run_tree
    from tools.consumer_snapshot import atomic_json
    command=([configured['PYTHON'],str(ROOT/'tools/watchdog.py')] if args.kind=='watchdog' else
             [configured['PYTHON'],str(ROOT/'tools/contract_snapshot.py'),'--check','--json'])
    record={'generated':datetime.now(timezone.utc).isoformat(),'kind':args.kind,'ok':False}
    try:
        run=run_tree(command,cwd=ROOT,timeout=300)
        record['exit_code'] = run.returncode
        if args.kind=='contracts':
            data=json.loads(run.stdout)
            if not isinstance(data, dict) or not isinstance(data.get('boundaries'), dict):
                raise ValueError('invalid contract record')
            for name in ('regressions', 'findings'):
                if not isinstance(data.get(name), list) or not all(isinstance(v, str) for v in data[name]):
                    raise ValueError('invalid contract changes')
            boundaries=data['boundaries']
            if not boundaries or any(not isinstance(v, dict) or type(v.get('ok')) is not bool for v in boundaries.values()):
                raise ValueError('invalid contract boundaries')
            record.update(ok=run.returncode==0 and not data['regressions'],boundaries=boundaries)
            issues=[*data['regressions'],*data['findings']]
            record['findings']=issues
            if issues: print('EIDOS contract changes: '+ '; '.join(map(str,issues)))
            elif run.returncode: print('FAIL EIDOS contract checker returned an error')
        else:
            record['ok']=run.returncode==0
            if run.stdout.strip() or run.returncode:
                print(run.stdout.strip() or 'FAIL EIDOS watchdog execution')
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        record.update(ok=False,error=type(exc).__name__)
        print(f'FAIL EIDOS {args.kind}: {type(exc).__name__}')
    atomic_json(ROOT/'docs/status'/f'cron-{args.kind}.json',record)
    return 0 if record['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
