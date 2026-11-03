"""Finite native installed-worker and browser acceptance; independent of live 8765."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys
import threading
import time
import urllib.request


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def main():
    require(not sys.flags.optimize, 'Optimized acceptance is unsupported')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='EIDOS checkout matching the candidate')
    parser.add_argument('--workspace', type=Path, required=True, help='Owned workspace containing env-a/env-b; results must not exist')
    parser.add_argument('--wheel', type=Path, required=True)
    args = parser.parse_args()
    require(sys.platform == 'win32', 'This entry qualifies Windows; use the separate offline Linux bootstrap on Linux')
    source = args.source.resolve(strict=True)
    root = args.workspace.resolve(strict=True)
    require(not root.is_relative_to(source) and not source.is_relative_to(root),
            'Acceptance workspace and source checkout must be separate')
    targets = [root / name for name in ('results', 'synthetic_positive', 'synthetic_negative', 'control')]
    for target in targets:
        require(not target.exists() and not target.is_symlink(), 'Existing acceptance target is preserved: ' + target.name)
    for target in targets:
        target.mkdir(exist_ok=False)
    sys.path.insert(0, str(source))
    from framework.subprocesses import run_tree
    from tools import dashboard, serve_site
    from tools.worker_monitor import WorkerMonitor
    from tools.browser import launch
    import yaml
    from playwright.sync_api import sync_playwright

    output = root / 'results'
    wheel = args.wheel.resolve(strict=True)
    wheel_before = wheel.read_bytes()

    def source_identity():
        files = [*sorted((source / 'framework').rglob('*.py')),
                 *[source / 'tools' / name for name in ('worker_monitor.py', 'dashboard.py', 'serve_site.py')]]
        return {path.relative_to(source).as_posix(): sha(path.read_bytes()) for path in files}

    before = source_identity()
    driver_before = Path(__file__).read_bytes()
    fixture_source = source / 'tests/test_validity.py'
    fixture_before = fixture_source.read_bytes()
    write_project = runpy.run_path(str(fixture_source))['write_project']
    identity_driver = source / 'reference/numerical_programs_acceptance/check.py'
    identity_driver_before = identity_driver.read_bytes()
    commands = []

    def run(name, command, expected=0, timeout=90):
        result = run_tree([str(item) for item in command], cwd=root, timeout=timeout)
        (output / (name + '.stdout')).write_text(result.stdout, encoding='utf-8')
        (output / (name + '.stderr')).write_text(result.stderr, encoding='utf-8')
        commands.append({'name': name, 'argv': [str(item) for item in command], 'exit': result.returncode})
        require(result.returncode == expected, name + ': unexpected command exit')
        return result.stdout

    identity_fields = ('sdk_version', 'wheel_sha256', 'wheel_name', 'installed_module', 'prefix',
                       'source_sha256_raw', 'source_sha256_canonical_lf', 'module_count',
                       'dependencies', 'dependency_metadata_sha256_lf', 'all_installed_metadata_requirements_met')
    identities, projects, registrations = {}, {}, {}
    control = root / 'control'
    for arm in ('a', 'b'):
        python = root / ('env-' + arm) / 'Scripts/python.exe'
        run(arm + '-pip-check', [python, '-I', '-m', 'pip', 'check'])
        identity = json.loads(run(arm + '-identity-before', [python, '-I', identity_driver, '--wheel', wheel, '--expected-version', '0.5.0']))
        require(identity['status'] == 'PASS', 'Installed identity failed')
        identities[arm] = {key: identity[key] for key in identity_fields}
        project = root / ('synthetic_' + ('positive' if arm == 'a' else 'negative'))
        write_project(project)
        (project / 'data/input.json').write_text('{"version":1}', encoding='utf-8')
        run(arm + '-init', [python, '-I', '-m', 'framework.cli', 'init', '--project', project, '--name', project.name, '--json'])
        path = project / '.eidos/project.yaml'
        config = yaml.safe_load(path.read_text(encoding='utf-8'))
        config.update(gate_command=['{python}', '-c', 'print("synthetic acceptance fixture")'],
                      validity_document='docs/MANUSCRIPT.html', validity_inputs=['.eidos/validate.py', 'data/input.json'])
        path.write_text(yaml.safe_dump(config), encoding='utf-8')
        if arm == 'b':
            evidence = project / 'data/evidence.json'
            value = json.loads(evidence.read_text(encoding='utf-8'))
            value['cross_arm']['separated'] = False
            evidence.write_text(json.dumps(value), encoding='utf-8')
        check = json.loads(run(arm + '-check', [python, '-I', '-m', 'framework.cli', 'check', '--project', project, '--json'], expected=0 if arm == 'a' else 1))
        require(check['scientific_status'] == ('PASS' if arm == 'a' else 'FAIL'), 'Synthetic gate control differs')
        enrolled = json.loads(run(arm + '-enroll', [python, '-I', '-m', 'framework.cli', 'enroll', '--project', project, '--monitor-root', control, '--json']))
        projects[arm] = {'root': project, 'id': enrolled['project_id'], 'run': check}
        registrations[arm] = Path(enrolled['registration'])
    require(identities['a']['dependencies'] != identities['b']['dependencies'], 'Independent dependency sets were not exercised')
    require(identities['a']['prefix'] != identities['b']['prefix'], 'Worker prefixes merged')

    def wait_for(observer, predicate, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            serve_site.refresh_worker_observations(observer)
            value = serve_site.worker_view()
            if value and predicate(value):
                return value
            time.sleep(.05)
        raise ValueError('Expected installed worker observation did not arrive')

    previews = []
    with WorkerMonitor(control, interval=.2, timeout=5) as observer:
        initial = wait_for(observer, lambda value: len(value['projects']) == 2 and all(row['monitor_status'] == 'OBSERVED' for row in value['projects']))
        by_id = {row['project_id']: row for row in initial['projects']}
        require(by_id[projects['a']['id']]['scientific_status'] == 'PASS', 'Positive worker was not accepted')
        require(by_id[projects['b']['id']]['scientific_status'] == 'FAIL', 'Negative worker became scientific success')
        (output / 'initial-observations.json').write_text(json.dumps(initial, indent=2) + '\n', encoding='utf-8')
        serve_site.STATE.update(payload={'overall': 'ALARM', 'derived': {'overall': 'ALARM', 'faults': ['Controlled acceptance preview; not the deployed monitor']}, 'seq': 1},
                                sampled=time.time(), page=dashboard.build(), interval=15)
        server = serve_site.ThreadingHTTPServer(('127.0.0.1', 0), serve_site.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        address = 'http://127.0.0.1:' + str(server.server_address[1])
        try:
            with sync_playwright() as playwright:
                browser = launch(playwright)
                try:
                    for width in (1440, 390):
                        page = browser.new_page(viewport={'width': width, 'height': 1000}, device_scale_factor=1.5)
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(address, wait_until='networkidle')
                        cards = page.locator('#worker-cards [data-worker-id]')
                        require(cards.count() == 2, 'Worker cards are missing')
                        text = page.locator('#worker-cards').inner_text()
                        require('Science: PASS' in text and 'Science: FAIL' in text, 'Scientific control states differ in browser')
                        require(page.locator('#worker-cards [data-refresh], #worker-cards [data-consumer]').count() == 0, 'Worker cards can invoke a legacy research gate')
                        geometry = page.locator('#worker-cards').evaluate('(node) => ({client:node.clientWidth,scroll:node.scrollWidth})')
                        require(geometry['scroll'] <= geometry['client'] + 1, 'Worker cards overflow horizontally')
                        page.locator('#project-workers').screenshot(path=str(output / ('workers-' + str(width) + '.png')))
                        require(not errors, 'Preview has JavaScript errors')
                        previews.append({'width': width, 'cards': cards.count(), 'geometry': geometry, 'javascript_errors': errors})
                        page.route('**/api/status', lambda route: route.abort())
                        page.reload(wait_until='domcontentloaded')
                        page.locator('#worker-cards').get_by_text('Worker observations unavailable.', exact=False).wait_for(timeout=10000)
                        require('Science: PASS' not in page.locator('#worker-cards').inner_text(), 'Network failure retained scientific acceptance')
                        page.close()
                finally:
                    browser.close()
            class BrokenObserver:
                def poll(self):
                    raise OSError('private failure marker')
            serve_site.refresh_worker_observations(BrokenObserver())
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(address, timeout=5) as response:
                html = response.read().decode('utf-8')
            section = html.partition('<!-- worker-observations:start -->')[2].partition('<!-- worker-observations:end -->')[0]
            require('Science: PASS' not in section and 'Science: STALE' in section, 'HTTP HTML restored stale scientific acceptance')
            with opener.open(address + '/api/status', timeout=5) as response:
                api = json.loads(response.read())
            require(all(row['scientific_status'] == 'STALE' for row in api['worker_observations']['projects']), 'HTTP API differs from HTML after failure')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            require(not thread.is_alive(), 'Owned preview server did not close')
        original_registration = registrations['b'].read_bytes()
        value = json.loads(original_registration)
        value['python'] = str(root / 'missing-worker/python.exe')
        registrations['b'].write_text(json.dumps(value), encoding='utf-8')
        failed = wait_for(observer, lambda value: any(row['project_id'] == projects['b']['id'] and row['monitor_status'] == 'UNAVAILABLE' for row in value['projects']))
        require(next(row for row in failed['projects'] if row['project_id'] == projects['a']['id'])['scientific_status'] == 'PASS', 'One unavailable worker withdrew the other project')
        (output / 'missing-worker-observations.json').write_text(json.dumps(failed, indent=2) + '\n', encoding='utf-8')
        registrations['b'].write_bytes(original_registration)
        input_file = projects['a']['root'] / 'data/input.json'
        input_file.write_text('{"version":2}', encoding='utf-8')
        changed = wait_for(observer, lambda value: any(row['project_id'] == projects['a']['id'] and row['scientific_status'] == 'STALE' for row in value['projects']))
        row = next(row for row in changed['projects'] if row['project_id'] == projects['a']['id'])
        require(row['run']['recorded_at'] == projects['a']['run']['recorded_at'], 'Observation regenerated the scientific timestamp')
        (output / 'changed-input-observations.json').write_text(json.dumps(changed, indent=2) + '\n', encoding='utf-8')
    for arm in ('a', 'b'):
        python = root / ('env-' + arm) / 'Scripts/python.exe'
        identity = json.loads(run(arm + '-identity-after', [python, '-I', identity_driver, '--wheel', wheel, '--expected-version', '0.5.0']))
        require(identity['status'] == 'PASS' and {key: identity[key] for key in identity_fields} == identities[arm], 'Installed identity changed')
    require(source_identity() == before and Path(__file__).read_bytes() == driver_before,
            'Source or driver changed during measurement')
    require(wheel.read_bytes() == wheel_before, 'Candidate wheel changed during measurement')
    require(fixture_source.read_bytes() == fixture_before and identity_driver.read_bytes() == identity_driver_before, 'Qualification input changed')
    record = {'status': 'PASS', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'wheel_sha256': sha(wheel_before), 'driver_sha256': sha(driver_before), 'source': before,
              'fixture_source_sha256': sha(fixture_before), 'identity_driver_sha256': sha(identity_driver_before),
              'commands': commands, 'previews': previews, 'preview_closed': True,
              'scope': 'Same-host native Windows normal-installed synthetic projects with different dependency sets and source-monitor HTTP/browser controls; no deployed8765 migration, new-machine, scientific discovery or RSI'}
    (output / 'record.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': record['status'], 'output': str(output), 'wheel_sha256': record['wheel_sha256']}))


if __name__ == '__main__':
    main()
