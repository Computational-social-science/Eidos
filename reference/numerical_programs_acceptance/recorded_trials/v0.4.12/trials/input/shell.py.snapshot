"""Installed recovery-shell qualification; finite fixtures, no real services."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import time
import uuid

from framework import recovery
from framework.subprocesses import run_tree


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def controls():
    original_cwd = Path.cwd()
    original_env = {name: os.environ.get(name) for name in ('EIDOS_BASH', 'SHELL', 'EIDOS_SHELL_PARENT')}
    checks = []
    try:
        for name in ('EIDOS_BASH', 'SHELL'):
            os.environ.pop(name, None)
        selected = Path(recovery._shell())
        require(selected.is_absolute() and selected.is_file(), 'Discovery did not bind an absolute executable')
        checks.append('default discovery without terminal SHELL')
        with ExitStack() as ownership:
            directory = ownership.enter_context(tempfile.TemporaryDirectory(prefix='eidos shell space \u03b1 '))
            ownership.callback(os.chdir, original_cwd)
            base = Path(directory)
            service = base/'different service cwd';service.mkdir()
            script = base/'script with spaces \u03b2.sh'
            script.write_text('printf "%s" "$1"\n', encoding='utf-8', newline='\n')
            nonce = uuid.uuid4().hex
            # Relative configuration is based on the configuration caller cwd,
            # never the later service cwd. No writes occur in the Git directory.
            os.chdir(selected.parent.parent)
            os.environ['EIDOS_BASH'] = os.path.relpath(selected, Path.cwd())
            relative = recovery._shell()
            require(Path(relative) == selected, 'Relative override changed executable identity')
            os.chdir(service)
            result = run_tree([relative, recovery._msys(script), nonce], cwd=service, timeout=5)
            require(result.returncode == 0 and result.stdout == nonce,
                    'Actual bash script failed after changing service cwd')
            checks.append('relative override executes unicode/space script after cwd change')
            os.environ['EIDOS_SHELL_PARENT'] = str(selected.parent)
            os.environ['EIDOS_BASH'] = '$EIDOS_SHELL_PARENT/'+selected.name
            expanded = recovery._shell()
            require(Path(expanded) == selected, 'Expanded override changed executable identity')
            result = run_tree([expanded, recovery._msys(script), nonce], cwd=service, timeout=5)
            require(result.returncode == 0 and result.stdout == nonce, 'Expanded shell execution failed')
            checks.append('expanded override executes the same absolute binary')
            os.environ['EIDOS_BASH'] = str(base/'missing-shell')
            recovery.STATE = base/'state.json'
            recovery.LOG = base/'events.jsonl'
            recovery.ACTIONS = {'candidate': {'root': 'repo', 'script': ('unused.sh',), 'kind': 'bash'}}
            recovery.preflight = lambda name: {
                'healthy': False, 'ports': {}, 'conflict': False, 'owned_by_self': False}
            outcome = recovery.execute(recovery.RecoveryPlan('candidate', 'start', 'controlled refusal', True))
            require(outcome.get('ok') is False and outcome.get('attempted') is False,
                    'Missing shell was treated as a launch')
            require(json.loads(recovery.STATE.read_text()) == {}, 'Refusal consumed a service budget')
            events = [json.loads(line) for line in recovery.LOG.read_text().splitlines()]
            require([event['phase'] for event in events] == ['refused'], 'Refusal event differs')
            checks.append('actual missing shell refuses without budget reservation')
            # The temporary service cwd must not be removed while selected.
            os.chdir(original_cwd)
        return {'checks': checks, 'selected_shell': str(selected), 'fixture_only': True,
                'real_model_services_touched': False,
                'refusal_preflight': 'controlled empty-port fixture; not a transport test'}
    finally:
        os.chdir(original_cwd)
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--identity-driver', type=Path, required=True)
    parser.add_argument('--identity-sha256', required=True)
    args = parser.parse_args()
    started = time.monotonic()
    require(sys.flags.isolated and not sys.flags.optimize, 'Use -I without optimization')
    require(sys.prefix != sys.base_prefix and Path(recovery.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()),
            'Recovery must be imported from the installed virtual environment')
    driver = Path(__file__).resolve();before_driver = driver.read_bytes()
    identity_path = args.identity_driver.resolve()
    body = identity_path.read_bytes()
    require(sha(body) == args.identity_sha256, 'Identity helper input pin differs')
    identity = runpy.run_path(str(identity_path), run_name='_pinned_identity')['identity']
    before = identity(args.wheel, args.expected_version)
    result = controls()
    require(identity(args.wheel, args.expected_version) == before, 'Installed environment changed')
    require(driver.read_bytes() == before_driver and identity_path.read_bytes() == body,
            'Qualification source changed')
    print(json.dumps({'schema': 'eidos.installed-recovery-shell.v1', 'status': 'PASS',
                      'observed_at': datetime.now(timezone.utc).isoformat(),
                      'driver_sha256_raw': sha(before_driver), 'identity_driver_sha256_raw': sha(body),
                      'python': sys.version, 'platform': sys.platform, 'identity': before,
                      'controls': result, 'elapsed_seconds': time.monotonic()-started,
                      'scope': 'Installed shell path and finite script controls, not real-service recovery, binary attestation or a hostile-code sandbox.'},
                     indent=2))


if __name__ == '__main__':
    main()
