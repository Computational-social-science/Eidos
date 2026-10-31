"""Snapshot proposed model presence and task evidence without loading any model."""
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def collect(root: Path = ROOT) -> dict:
    from framework.inference import StageAwareScheduler
    from framework.provenance import source_hash
    models={};error=None
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:
            data=json.load(response)
        if not isinstance(data,dict) or not isinstance(data.get('models'),list):
            raise ValueError('invalid model inventory')
        if any(not isinstance(m,dict) or not isinstance(m.get('name'),str) for m in data['models']):
            raise ValueError('invalid model entry')
        models={m['name']:m for m in data['models'] if isinstance(m,dict) and isinstance(m.get('name'),str)}
    except (OSError,ValueError) as exc:
        error=type(exc).__name__
    entries=[]
    for name in ('llama3.1:8b','qwen2.5:14b','gemma2:9b'):
        local=models.get(name)
        entries.append({'name':name,'installed':None if error else local is not None,
                        'digest':local.get('digest') if local else None,
                        'task_qualification':'UNQUALIFIED','scope':'No accepted EIDOS research-task evaluation for this exact model/quantization.'})
    evidence={}
    for key,name in (('sciencersi_s4','artifacts/evaluation/s4_probe_structured.json'),
                     ('sciencersi_s7_holdout','artifacts/evaluation/s7_constrained_holdout.json'),
                     ('startlux_calibration','artifacts/decision_calibration_100.json')):
        path=root/name
        evidence[key]={'path':name,'sha256':source_hash(path.read_bytes()),
                       'status':'historical measured record; not rerun by this inventory snapshot'}
    return {'observed_at':datetime.now(timezone.utc).isoformat(),'source':'Ollama /api/tags; read-only, no model loaded',
            'inventory_error':error,'models':entries,'evidence':evidence,
            'hash_policy':'Evidence JSON canonical UTF-8/LF SHA-256; no measurement rerun.',
            'stages':[StageAwareScheduler.describe_stage(s) for s in StageAwareScheduler.STAGE_MODELS],
            'scientific_reasoner_qualified':False,'scope':'Model presence is a dated observation, not availability, deployment identity or scientific task acceptance.'}


if __name__=='__main__':
    from tools.consumer_snapshot import atomic_json
    record=collect()
    atomic_json(ROOT/'docs/MODEL_TASK_READINESS.json',record)
    print(json.dumps({'observed_at':record['observed_at'],'models':record['models'],
                      'scientific_reasoner_qualified':False},indent=2))
    raise SystemExit(1 if record['inventory_error'] else 0)
