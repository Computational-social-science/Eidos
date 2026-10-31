"""Execute the fixed prospective grokking reconstruction and conditional distillation."""
from __future__ import annotations
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import copy
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from reference.softmax_grokking.model import Transformer
from reference.softmax_grokking.common import digest, source_digest, json_digest, dataset, classification_metrics
from framework import stable_numerics_torch as kernels
from reference.softmax_training.train import actual_backend, state_hash, require_equal_logits


def execute(protocol):
    report = {'status':'RUNNING', 'started_at':datetime.now(timezone.utc).isoformat(),
              'protocol':protocol,'runs':[],'artifacts':{}}
    (HERE/'docs').mkdir(exist_ok=True)
    (HERE/'checkpoints').mkdir(exist_ok=True)
    def publish():
        temp = HERE/'docs/evidence.json.tmp'
        temp.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        os.replace(temp,HERE/'docs/evidence.json')
    publish()
    try:
        if protocol['device'] != 'cuda' or not torch.cuda.is_available():
            raise RuntimeError('protocol requires CUDA')
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
        report['runtime']={'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__,
            'cuda':torch.version.cuda,'device':torch.cuda.get_device_name(),'device_type':'cuda',
            'dtype':'float32','tf32':False,'deterministic_algorithms':True}
        sources=('reference/softmax_grokking_extension/run.py','reference/softmax_grokking/model.py',
                 'reference/softmax_grokking/common.py','reference/softmax_grokking_extension/protocol.json',
                 'reference/softmax_training/train.py','reference/softmax_training/validate.py',
                 'framework/stable_numerics_torch.py','framework/verifiers/numerics.py')
        report['source_sha256']={name:source_digest(ROOT/name) for name in sources}
        parent_path=ROOT/protocol['parent']
        parent=json.loads(parent_path.read_text(encoding='utf-8'))
        if parent.get('status')!='COMPLETE': raise RuntimeError('parent experiment is incomplete')
        report['parent_evidence_sha256']=digest(parent_path)
        report['parent_replay_checks']=[]
        report['backend_preflight']=actual_backend('cuda')
        if report['backend_preflight']['verdict'] != 'PASS': raise RuntimeError('backend unqualified')
        tokens,labels=dataset(protocol['modulus'])
        x=torch.tensor(tokens,device='cuda');y=torch.tensor(labels,device='cuda')
        def save(model, name):
            stem=HERE/'checkpoints'/name
            torch.save(model.state_dict(),stem.with_suffix('.pt'))
            stem.with_suffix('.json').write_text(json.dumps({k:v.detach().cpu().tolist() for k,v in model.state_dict().items()},separators=(',',':')),encoding='utf-8')
            for suffix in ('.pt','.json'):
                path=stem.with_suffix(suffix);report['artifacts'][path.relative_to(HERE).as_posix()]=digest(path)
            return state_hash(model)
        for seed in protocol['seeds']:
            torch.manual_seed(seed)
            order=torch.randperm(len(labels),generator=torch.Generator().manual_seed(seed)).tolist()
            cut=int(len(order)*protocol['train_fraction']);train,test=order[:cut],order[cut:]
            tx=x[train];ty=y[train]
            split={'seed':seed,'modulus':protocol['modulus'],'permutation':order}
            split_path=HERE/f'checkpoints/seed-{seed}-split.json'
            split_path.write_text(json.dumps(split),encoding='utf-8')
            report['artifacts'][split_path.relative_to(HERE).as_posix()]=digest(split_path)
            base=Transformer(protocol['modulus'],protocol['width'],protocol['heads']).cuda()
            initial=save(base,f'seed-{seed}-initial')
            run={'seed':seed,'split_sha256':json_digest(split),'initial_state_sha256':initial,'arms':{}}
            report['runs'].append(run)
            trained={}
            for name in ('standard','fixed'):
                model=copy.deepcopy(base)
                arm={'initial_state_sha256':state_hash(model),'checkpoints':[]}
                run['arms'][name]=arm
                optimizer=torch.optim.AdamW(model.parameters(),lr=protocol['lr'],betas=tuple(protocol['betas']),
                                            eps=protocol['epsilon'],weight_decay=protocol['weight_decay'])
                started=time.monotonic()
                for step in range(protocol['epochs']+1):
                    if step==10000:
                        expected=next(r for r in parent['runs'] if r['seed']==seed)['arms'][name]['final_state_sha256']
                        observed=state_hash(model)
                        if observed!=expected: raise RuntimeError('parent checkpoint replay differs; no continuous-training claim')
                        report['parent_replay_checks'].append({'seed':seed,'arm':name,'step':step,'sha256':observed})
                    if step%protocol['log_interval']==0:
                        with torch.no_grad(): logits=model(x).cpu().numpy()
                        metrics=classification_metrics(logits,labels,train,test)
                        arm['checkpoints'].append({'step':step,**metrics})
                        publish()
                        print(f"seed={seed} {name} step={step} train={metrics['train_accuracy']:.4f} test={metrics['test_accuracy']:.4f} margin={metrics['mean_margin']:.3f} elapsed={time.monotonic()-started:.1f}s",flush=True)
                    if step==protocol['epochs']: break
                    optimizer.zero_grad(set_to_none=True)
                    logits=model(tx)
                    loss=kernels.hard_cross_entropy(logits,ty).mean() if name=='fixed' else F.cross_entropy(logits,ty)
                    loss.backward();optimizer.step()
                arm['final_state_sha256']=save(model,f'seed-{seed}-{name}')
                trained[name]=model
                publish()
            teacher=trained['fixed'].eval().requires_grad_(False)
            teacher_accuracy=run['arms']['fixed']['checkpoints'][-1]['test_accuracy']
            if teacher_accuracy < protocol['teacher_minimum_test_accuracy']:
                run['distillation']={'status':'SKIP','reason':'final fixed teacher below prespecified accuracy threshold'}
                publish();continue
            d=protocol['distillation'];temperature=d['temperature']
            with torch.no_grad():
                target=teacher(tx)/temperature
                heldout_teacher=teacher(x[test])
                log_p=F.log_softmax((heldout_teacher/temperature).double(),-1)
                p64=log_p.exp();probabilities=F.softmax(target,-1)
            teacher_parameters=[v.detach().clone() for v in teacher.parameters()]
            run['distillation']={'status':'RUNNING','variants':{}}
            for name in ('standard','fixed'):
                model=copy.deepcopy(teacher).requires_grad_(True)
                variant={'initial_state_sha256':state_hash(model),'checkpoints':[]}
                run['distillation']['variants'][name]=variant
                optimizer=torch.optim.Adam(model.parameters(),lr=d['lr'],betas=tuple(d['betas']),eps=d['epsilon'],weight_decay=d['weight_decay'])
                for step in range(d['steps']+1):
                    if step%d['log_interval']==0:
                        with torch.no_grad():
                            logits=model(x[test]);log_q=F.log_softmax((logits/temperature).double(),-1)
                            drift=sum(((a.double()-b.double())**2).sum() for a,b in zip(model.parameters(),teacher_parameters)).sqrt().item()
                            variant['checkpoints'].append({'step':step,'parameter_displacement_l2':drift,
                                'heldout_kl_float64':(p64*(log_p-log_q)).sum(-1).mean().item(),
                                'test_accuracy':float((logits.argmax(-1)==y[test]).float().mean())})
                    if step==d['steps']:break
                    optimizer.zero_grad(set_to_none=True);logits=model(tx)/temperature
                    if step==0:
                        require_equal_logits(logits,target);variant['initial_logits_equal']=True
                    loss=kernels.logit_distillation(logits,target).mean() if name=='fixed' else -(probabilities*F.log_softmax(logits,-1)).sum(-1).mean()
                    loss.backward();optimizer.step()
                variant['final_state_sha256']=save(model,f'seed-{seed}-distill-{name}')
                print(f"seed={seed} distill {name} displacement={variant['checkpoints'][-1]['parameter_displacement_l2']:.8g}",flush=True)
            run['distillation']['status']='COMPLETE';publish()
        report['status']='COMPLETE';report['finished_at']=datetime.now(timezone.utc).isoformat();publish()
        return report
    except BaseException as exc:
        report['status']='INCOMPLETE' if isinstance(exc,KeyboardInterrupt) else 'ERROR'
        report['error']=f'{type(exc).__name__}: {exc}';publish();raise


if __name__=='__main__': execute(json.loads((HERE/'protocol.json').read_text(encoding='utf-8')))
