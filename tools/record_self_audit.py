"""Record the framework's own audit state as a machine-checkable artefact.

Gate S cannot read prose: it resolves a JSON pointer and compares values. So the
framework's claims about itself need a file that is *produced*, not written by hand --
otherwise the register would be asserting numbers a human typed, which is exactly the
failure mode the gate exists to catch.

This tool runs the chain audit and the test collection, and writes `docs/SELF_AUDIT.json`.
It is intentionally the only writer of that file.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "SELF_AUDIT.json"


def input_state() -> dict:
    """Bound source/metadata and installed distribution identities, not GPU health."""
    paths=[p for folder in ('framework','tools','tests') for p in (ROOT/folder).rglob('*.py')
           if '__pycache__' not in p.parts]
    paths += [ROOT/p for p in ('pyproject.toml','uv.lock','README.md','analysis/CLAIMS.yaml')]
    digest=hashlib.sha256()
    for path in sorted(paths):
        body=path.read_bytes().decode('utf-8-sig').replace('\r\n','\n').encode('utf-8')
        digest.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+hashlib.sha256(body).digest())
    packages=sorted((str(d.metadata.get('Name','')).lower(),d.version) for d in importlib.metadata.distributions())
    return {'source_sha256':digest.hexdigest(),
            'distribution_sha256':hashlib.sha256(json.dumps(packages).encode()).hexdigest()}


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def execute_tests(command: list[str]) -> tuple[subprocess.CompletedProcess, dict]:
    """Reconcile actual item reports, excluding module-level collection skips."""
    with tempfile.TemporaryDirectory(prefix='eidos-self-audit-') as directory:
        report=Path(directory)/'tests.xml'
        run=_run([*command,f'--junitxml={report}'],timeout=900)
        try:
            cases=list(ET.parse(report).getroot().iter('testcase'))
            collection_skips=0
            for case in cases:
                skipped=case.find('skipped')
                if (case.get('classname')=='' and skipped is not None
                        and skipped.get('message')=='collection skipped'):
                    collection_skips+=1
            return run,{'reported_items':len(cases)-collection_skips,'collection_level_skips':collection_skips}
        except (OSError,ET.ParseError) as exc:
            return run,{'reported_items':None,'error':type(exc).__name__}


def collect() -> dict:
    before=input_state()
    chains = _run([sys.executable, "tools/audit_chains.py", "--json", "--ci"])
    if chains.returncode not in (0, 1):
        raise SystemExit(f"chain audit failed to run: {chains.stderr[-400:]}")
    rows = json.loads(chains.stdout)
    counts = {"total": len(rows),
              "pass": sum(1 for r in rows if r["status"] == "PASS"),
              "skip": sum(1 for r in rows if r["status"] == "SKIP"),
              "fail": sum(1 for r in rows if r["status"] in ("FAIL", "ERROR"))}

    tests = _run([sys.executable, "-m", "pytest", "--collect-only", "-q"], timeout=300)
    m = re.search(r"(\d+)\s+tests? collected", tests.stdout + tests.stderr)
    collected = int(m.group(1)) if m else None

    # Coverage is measured, not asserted: the number is recorded so a drop becomes a
    # visible drift, and the gate only refuses a drop larger than one point.
    coverage_total = None
    if _run([sys.executable, "-m", "coverage", "--version"], timeout=120).returncode == 0:
        executed,execution = execute_tests([sys.executable, "-m", "coverage", "run", "--source=framework", "-m", "pytest", "-q", "-rs"])
        report = _run([sys.executable, "-m", "coverage", "report"], timeout=300)
        m2 = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", report.stdout)
        coverage_total = int(m2.group(1)) if m2 else None
    else:
        executed,execution = execute_tests([sys.executable, "-m", "pytest", "-q", "-rs"])
    test_output = executed.stdout + executed.stderr
    test_counts = {}
    for label in ("passed", "failed", "skipped", "errors"):
        pattern = "errors?" if label == "errors" else label
        count = re.search(rf"(\d+)\s+{pattern}\b", test_output)
        test_counts[label] = int(count.group(1)) if count else 0

    gate = _run([sys.executable, "tools/audit_validity.py",
                 "--project", "tests/fixtures/valid_project", "--json"])
    try:
        gate_status = json.loads(gate.stdout).get("status")
    except json.JSONDecodeError:
        gate_status = "UNREADABLE"

    # The framework's own register: this may be FAIL (open objections are recorded, not
    # hidden). What must not happen is the number creeping up unnoticed, so --check
    # compares this block against the committed record.
    self_run = _run([sys.executable, "tools/audit_validity.py",
                     "--project", ".", "--document", "README.md", "--json"])
    try:
        self_data = json.loads(self_run.stdout)
    except json.JSONDecodeError:
        self_data = {"status": "UNREADABLE", "findings": []}
    self_findings = self_data.get("findings", [])
    # Parse the number the gate reports rather than counting findings: one finding can
    # name five objections.
    open_objections = 0
    for finding in self_findings:
        m2 = re.search(r"(\d+)\s+referee objection", str(finding))
        if m2:
            open_objections = int(m2.group(1))

    recollected=_run([sys.executable,'-m','pytest','--collect-only','-q'],timeout=300)
    later=re.search(r'(\d+)\s+tests? collected',recollected.stdout+recollected.stderr)
    later_count=int(later[1]) if later else None
    node_ids=lambda run: sorted(line.strip() for line in run.stdout.splitlines() if line.startswith('tests/') and '::' in line)
    after=input_state()
    selected=node_ids(tests)
    deselection=any('deselected' in (run.stdout+run.stderr) for run in (tests,executed,recollected))
    stable=(before==after and type(collected) is int and collected>0
            and len(selected)==collected and len(set(selected))==collected
            and collected==later_count and selected==node_ids(recollected)
            and execution['reported_items']==collected and not deselection)

    diagnostics = {name: (run.stdout + run.stderr)[-12000:] for name, run in
                   (("tests", executed), ("test_collection", tests), ("test_collection_after",recollected), ("chains", chains),
                    ("gate_s", gate), ("self_gate_s", self_run)) if run.returncode != 0}
    return {"chains": counts, "tests_collected": collected, "tests": test_counts,
            "stability":{'stable':stable,'before':before,'after':after,'collection_after':later_count,
                         'execution':execution,'deselection_detected':deselection,
                         'collected_ids':len(selected),'unique_ids':len(set(selected)),
                         'recollected_ids':len(node_ids(recollected)),
                         'scope':'Framework/tools/tests Python sources, project version/lock/README/claims, installed distribution names+versions, collected test IDs'},
            "skip_reasons":[line for line in test_output.splitlines() if line.startswith('SKIPPED [')],
            "diagnostics": diagnostics,
            "coverage_total": coverage_total,
            "coverage_scope": "framework; unexecuted modules included; tests and tools excluded",
            "gate_s": {"fixture_status": gate_status},
            "self_gate_s": {"status": self_data.get("status"), "findings": self_findings,
                            "open_objections": open_objections},
            "exit_codes": {"chains": chains.returncode, "gate_s": gate.returncode,
                           "self_gate_s": self_run.returncode,
                           "test_collection": tests.returncode, "test_collection_after":recollected.returncode, "tests": executed.returncode}}


def measurement_failures(record: dict) -> list[str]:
    """A repeated failure is still a failure, even when the baseline contains it."""
    codes = record.get("exit_codes", {})
    failures = [f"{stage} exited {codes.get(stage)!r}"
                for stage in ("chains", "test_collection", "test_collection_after", "tests", "gate_s", "self_gate_s")
                if codes.get(stage) != 0]
    if record.get("chains", {}).get("fail", 0):
        failures.append("one or more chains failed")
    if record.get("gate_s", {}).get("fixture_status") != "PASS":
        failures.append("fixture Gate S did not pass")
    if record.get("self_gate_s", {}).get("status") != "PASS":
        failures.append("framework Gate S did not pass")
    if (record.get('stability') or {}).get('stable') is not True:
        failures.append('source, environment or collected tests changed during measurement')
    return failures


def publish_record(record: dict) -> None:
    from framework.artifacts import output_lock
    with output_lock(ROOT/'docs/status/self-audit-publication'):
        _publish_record(record)


def _publish_record(record: dict) -> None:
    """Publish measured JSON and headline documents; roll back if a write fails."""
    from framework.artifacts import atomic_output
    coverage=record.get('coverage_total')
    if type(coverage) is not int or not 0<=coverage<=100:
        raise ValueError('coverage was not measured as an integer percentage; prior records preserved')
    collected=record['tests_collected'];passed=record['tests']['passed']
    modules=record['stability']['execution']['collection_level_skips']
    item_skips=record['tests']['skipped']-modules
    if item_skips<0:raise ValueError('inconsistent item/module skip counts')
    chains=record['chains']
    health=ROOT/'docs/HEALTH.md'
    text=health.read_text(encoding='utf-8')
    replacements=[(r'\| unit tests \|[^\n]*',
                   f'| unit tests | **{collected} collected**, {passed} passed; {item_skips} item skips, {modules} collection-level optional-module skips (historical separate CUDA qualification: 16 passed) | ✅ |'),
                  (r'(\| coverage of `framework/` \| )\*\*\d+%\*\*',
                   rf"\g<1>**{coverage}%**"),
                  (r'(\| chain audit \| )\*\*[^\n]*?\*\*',
                   rf"\g<1>**{chains['total']} chains: {chains['pass']} PASS, {chains['skip']} SKIP, {chains['fail']} FAIL/ERROR**")]
    for pattern,replacement in replacements:
        text,count=re.subn(pattern,replacement,text,count=1)
        if count!=1:raise ValueError('health document has no measured headline marker')
    outputs={OUT:(json.dumps(record,indent=2)+'\n').encode(),health:text.encode('utf-8')}
    technical=ROOT/'Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'
    if technical.is_file():
        text=technical.read_text(encoding='utf-8')
        summary=(f'<!-- self-audit:start -->\n本轮验收：{passed} passed、{item_skips} 个用例 skipped、'
                 f'{modules} 个可选模块收集 skipped，框架源码覆盖率 {coverage}%，'
                 f"{chains['total']} 条链为 {chains['pass']} PASS/{chains['skip']} SKIP/{chains['fail']} FAIL/ERROR。\n<!-- self-audit:end -->")
        text,count=re.subn(r'<!-- self-audit:start -->.*?<!-- self-audit:end -->',lambda _:summary,text,count=1,flags=re.S)
        if count!=1:raise ValueError('technical framework has no current self-audit markers')
        outputs[technical]=text.encode('utf-8')
    originals={p:p.read_bytes() if p.is_file() else None for p in outputs}
    written=[]
    try:
        for path,body in outputs.items():
            with atomic_output(path) as temporary:temporary.write_bytes(body)
            written.append(path)
    except BaseException:
        for path in reversed(written):
            body=originals[path]
            if body is None:path.unlink(missing_ok=True)
            else:
                with atomic_output(path) as temporary:temporary.write_bytes(body)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="compare with the recorded file instead of writing it")
    args = ap.parse_args(argv)

    sys.path.insert(0,str(ROOT))
    from framework.artifacts import output_lock
    with output_lock(OUT.with_suffix('')):
        return measure(args)


def measure(args) -> int:

    new = collect()
    failures = measurement_failures(new)
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        for stage, output in new.get("diagnostics", {}).items():
            print(f"--- {stage} diagnostic ---\n{output}")
        print('Measurement stability: '+json.dumps(new.get('stability',{}),sort_keys=True))
        return 1
    if args.check:
        if not OUT.is_file():
            print(f"[FAIL] {OUT.name} has never been recorded")
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        # Only machine-independent fields are compared: how many chains PASS depends on
        # whether a service happens to be running, and a CI runner has none. Total, FAIL
        # count, the Gate S verdict and the open-objection count are stable everywhere.
        def pick(d):
            return {"chains.total": d.get("chains", {}).get("total"),
                    "chains.fail": d.get("chains", {}).get("fail"),
                    "gate_s.fixture_status": d.get("gate_s", {}).get("fixture_status"),
                    "self_gate_s.status": d.get("self_gate_s", {}).get("status"),
                    "self_gate_s.open_objections": d.get("self_gate_s", {}).get("open_objections")}
        def coverage(d):
            return {"coverage_total": d.get("coverage_total")}
        before, after = pick(old), pick(new)
        drift = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        old_cov, new_cov = coverage(old)["coverage_total"], coverage(new)["coverage_total"]
        if isinstance(old_cov, int) and isinstance(new_cov, int) and new_cov < old_cov - 1:
            drift["coverage_total"] = (old_cov, new_cov)
        if drift:
            for k, (before, after) in drift.items():
                print(f"DRIFT {k}: {before} -> {after}")
            return 1
        print("no drift in the self-audit record")
        return 0

    publish_record(new)
    print(f"wrote {OUT.relative_to(ROOT)}: {new['chains']} tests={new['tests_collected']} "
          f"gate_s={new['gate_s']['fixture_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
