"""Compile and evaluate an explicitly selected known method beside a saved response.

No model inference, silent response repair, scientific promotion or RSI occurs.
Historical provenance remains a trusted-input assumption, not remote attestation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import sys
import time
import uuid

import numpy as np

from . import compiler
from reference.rsi_bootstrap import c0, grader

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.Codex/evals/numerical-method-compiler.md'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8')


def runtime() -> dict:
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
            'platform': platform.platform(), 'numpy': np.__version__, 'device': 'CPU'}


def source_snapshot() -> dict:
    paths = [ROOT / name for name in c0.source_snapshot()]
    paths += list(Path(__file__).parent.glob('*.py'))
    paths += [compiler.CATALOG, compiler.BANK, CONTRACT, ROOT/'pyproject.toml', ROOT/'uv.lock',
              ROOT/'.github/workflows/ci.yml']
    return {path.relative_to(ROOT).as_posix(): sha(path.read_bytes()) for path in sorted(set(paths))}


def response_text(raw: bytes) -> str:
    value = compiler.strict_json(raw)
    if (not isinstance(value, dict) or not isinstance(value.get('choices'), list)
            or len(value['choices']) != 1 or not isinstance(value['choices'][0], dict)
            or not isinstance(value['choices'][0].get('message'), dict)):
        raise ValueError('Input must be a saved single-choice chat response')
    content = value['choices'][0]['message'].get('content')
    if content is not None and not isinstance(content, str):
        raise ValueError('Response content must be text or null')
    return content or ''


def assess(raw: str) -> dict:
    convergence = []
    for case in grader.development_cases():
        low, high = grader.reference(case), grader.reference(case, precision=520)
        with localcontext() as context:
            context.prec = 120
            errors = {name: abs(low[name]/high[name]-1) for name in ('loss', 'gradient')}
        if any(error >= Decimal('1e-100') for error in errors.values()):
            raise ValueError('Public Decimal reference failed precision convergence')
        convergence.append({'case': case.name, 'dtype': case.value.dtype.name,
                            'relative_errors_decimal': {key: str(value) for key, value in errors.items()}})
    core = c0.run_once(lambda _: raw)  # Explicit recorded-text/tool replay, not inference.
    evaluated = core['status'] in {'DEVELOPMENT_CONFORMING', 'DEVELOPMENT_NONCONFORMING'}
    signs = []
    for point in core['points']:
        loss, gradient = point['actual_outputs']
        signs.append({'case': point['case'], 'dtype': point['dtype'],
                      'loss_negative': type(loss) in (int, float) and math.isfinite(loss) and loss < 0,
                      'gradient_positive': type(gradient) in (int, float) and math.isfinite(gradient) and gradient > 0})
    accepted = (core['status'] == 'DEVELOPMENT_CONFORMING' and len(signs) == 23
                and all(row['loss_negative'] and row['gradient_positive'] for row in signs))
    return {'core': core, 'sign_checks': signs, 'reference_convergence': convergence,
            'summary': {'status': core['status'], 'points_evaluated': len(core['points']),
                        'joint_points': core['candidate_conforming_points'] if evaluated else None,
                        'accepted': accepted}}


def scientific_projection(assessment: dict) -> dict:
    # Only timestamp/duration vary on replay. Preserve every outcome, authority,
    # prompt, provenance and unknown field rather than selecting a few verdicts.
    return {**assessment, 'core': {key: value for key, value in assessment['core'].items()
                                  if key not in {'observed_at', 'wall_seconds'}}}


def identical(left, right) -> bool:
    """Canonical JSON equality preserves boolean/integer/float distinctions."""
    options = {'sort_keys': True, 'separators': (',', ':'), 'allow_nan': False}
    return json.dumps(left, **options) == json.dumps(right, **options)


def program_record(method: dict) -> dict:
    return {'method': method, 'origin': 'external_known_method_tool',
            'program': compiler.compile_formulas(method['loss'], method['gradient'])}


def tool_response(program: dict) -> str:
    return json.dumps({'program': program['program'],
                       'explanation': 'External known method compiled deterministically; not a model-generated repair.'},
                      allow_nan=False)


def file_inventory(output: Path) -> set[str]:
    files = set()
    for path in output.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError('Nonregular or linked output refused')
        if path.is_file():
            files.add(path.relative_to(output).as_posix())
    return files


def run(response: Path, expected_sha: str, method_id: str, output: Path) -> dict:
    started = time.perf_counter()
    response, output = Path(response).resolve(strict=True), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Output must be a new directory')
    if not isinstance(expected_sha, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha):
        raise ValueError('An explicit lowercase response SHA-256 is required')
    if not response.is_file() or response.stat().st_size > 131072:
        raise ValueError('Response must be a regular file of at most 128 KiB')
    raw = response.read_bytes()
    if len(raw) > 131072 or sha(raw) != expected_sha:
        raise ValueError('Response bytes differ from the explicit input pin')
    before, environment = source_snapshot(), runtime()
    method = compiler.load_method(method_id)
    compiled = program_record(method)
    proposal = assess(response_text(raw))
    tool = assess(tool_response(compiled))
    payloads = {'response.json': raw, 'method-program.json': encoded(compiled),
                'proposal-evaluation.json': encoded(proposal), 'tool-evaluation.json': encoded(tool)}
    for relative, digest in before.items():
        data = (ROOT / relative).read_bytes()
        if sha(data) != digest:
            raise ValueError('Source changed before snapshot publication')
        payloads['source/' + relative + '.snapshot'] = data
    if before != source_snapshot() or environment != runtime() or sha(response.read_bytes()) != expected_sha:
        raise ValueError('Source/runtime/input changed during evaluation')
    record = {'schema': 'eidos.numerical-method-execution.v1', 'run_id': uuid.uuid4().hex,
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'origin': 'external_known_method_tool', 'new_model_inference': False,
              'scientific_promotion': False, 'scientific_rsi': 'NOT_DEMONSTRATED',
              'sealed_evaluation': 'NOT_RUN', 'seed': 'not applicable; deterministic compilation and replay',
              'response_sha256': expected_sha, 'response_original_path': str(response),
              'method_id': method_id, 'source_sha256': before, 'runtime': environment,
              'proposal': proposal['summary'], 'tool': tool['summary'],
              'files': {name: sha(data) for name, data in sorted(payloads.items())},
              'evaluation_seconds': time.perf_counter()-started,
              'scope': 'Public 23-point recorded-response comparison; externally supplied formula and derivative, no general-domain or RSI qualification'}
    # Publish only after source/input/evaluation coherence has been established.
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        destination = output/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(data)
    if before != source_snapshot() or environment != runtime() or sha(response.read_bytes()) != expected_sha:
        raise ValueError('Source/runtime/input changed during publication; partial output is not accepted')
    if (file_inventory(output) != set(payloads)
            or any((output/name).read_bytes() != data for name, data in payloads.items())):
        raise ValueError('Published payload differs; no terminal acceptance is written')
    # This receipt is the terminal marker. Partial file publication is not acceptance.
    with (output/'record.json').open('xb') as stream:
        stream.write(encoded(record))
    return record


def verify(output: Path) -> dict:
    output = Path(output).resolve(strict=True)
    terminal = output/'record.json'
    if terminal.is_symlink() or not terminal.is_file() or terminal.stat().st_size > 131072:
        raise ValueError('Terminal receipt must be a bounded regular file')
    terminal_raw = terminal.read_bytes()
    record = compiler.strict_json(terminal_raw)
    if (not isinstance(record, dict) or record.get('schema') != 'eidos.numerical-method-execution.v1'
            or record['origin'] != 'external_known_method_tool' or record['new_model_inference'] is not False
            or record['scientific_promotion'] is not False or record['scientific_rsi'] != 'NOT_DEMONSTRATED'
            or record['sealed_evaluation'] != 'NOT_RUN'):
        raise ValueError('Unrecognized receipt or overstated authority')
    sources = source_snapshot()
    if record['source_sha256'] != sources or record['runtime'] != runtime():
        raise ValueError('Receipt source/runtime differs; freeze and execute a new replay')
    expected = {'response.json', 'method-program.json', 'proposal-evaluation.json', 'tool-evaluation.json'}
    expected |= {'source/' + name + '.snapshot' for name in sources}
    if not isinstance(record['files'], dict) or set(record['files']) != expected:
        raise ValueError('Receipt file inventory differs')
    actual = file_inventory(output)
    if actual != expected | {'record.json'}:
        raise ValueError('Published file inventory differs')
    payloads = {}
    for name, digest in record['files'].items():
        with (output/name).open('rb') as stream:
            data = stream.read(8*1024*1024+1)
        if len(data) > 8*1024*1024 or sha(data) != digest:
            raise ValueError('Published file hash differs')
        payloads[name] = data
    for name, digest in sources.items():
        if record['files']['source/' + name + '.snapshot'] != digest:
            raise ValueError('Archived source does not bind its declared identity')
    raw = payloads['response.json']
    if sha(raw) != record['response_sha256']:
        raise ValueError('Raw response does not bind its explicit pin')
    compiled = program_record(compiler.load_method(record['method_id']))
    if not identical(compiler.strict_json(payloads['method-program.json']), compiled):
        raise ValueError('Compiled method differs from the explicitly selected catalog entry')
    for name, replay in (('proposal', assess(response_text(raw))), ('tool', assess(tool_response(compiled)))):
        saved = compiler.strict_json(payloads[f'{name}-evaluation.json'])
        if (not identical(scientific_projection(saved), scientific_projection(replay))
                or not identical(record[name], replay['summary'])):
            raise ValueError('Saved outcome differs from the actual program replay')
    if (sources != source_snapshot() or record['runtime'] != runtime()
            or terminal.read_bytes() != terminal_raw
            or file_inventory(output) != actual
            or any(sha((output/name).read_bytes()) != digest for name, digest in record['files'].items())):
        raise ValueError('Receipt/input/source/runtime changed during verification')
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--response', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--method')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            if any(value is not None for value in (args.response, args.sha256, args.method, args.output)):
                raise ValueError('Verify is a separate command')
            record = verify(args.verify)
        else:
            if any(value is None for value in (args.response, args.sha256, args.method, args.output)):
                raise ValueError('Response, sha256, method and new output directory are required')
            record = run(args.response, args.sha256, args.method, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Numerical method execution refused: {error}\n')
    print(json.dumps({'run_id': record['run_id'], 'proposal': record['proposal'],
                      'tool': record['tool'], 'new_model_inference': False,
                      'scientific_rsi': 'NOT_DEMONSTRATED'}))
    return 0 if record['tool']['accepted'] else 2
