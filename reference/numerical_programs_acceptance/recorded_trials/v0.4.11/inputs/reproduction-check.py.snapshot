"""Installed-wheel reproduction controls; benign deterministic stubs, no paper MATCH."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
from importlib.metadata import version, distribution
import inspect
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import time

from framework import reproduction as r
from framework.validity import ScientificValidityGate


def main() -> int:
    if sys.flags.optimize:
        raise SystemExit("Qualification requires active assertions; omit -O/-OO.")
    installed = Path(r.__file__).resolve()
    assert installed.is_relative_to(Path(sys.prefix).resolve()), installed
    assert {"site-packages", "dist-packages"}.intersection(installed.parts), installed
    package = distribution("eidos")
    assert (
        installed
        == Path(package.locate_file("framework/reproduction/__init__.py")).resolve()
    )
    assert (
        Path(inspect.getfile(ScientificValidityGate)).resolve()
        == Path(package.locate_file("framework/validity/__init__.py")).resolve()
    )
    cases = []

    def accepted(name):
        cases.append({"case": name, "accepted": True})

    values = [
        0,
        1,
        -1,
        2**53,
        2**53 + 1,
        10**100,
        10**4000,
        math.ulp(0),
        -math.ulp(0),
        1e-300,
        1e300,
        sys.float_info.max,
        math.nextafter(1.0, 2.0),
    ]
    rng = random.Random(20261101)
    values += [rng.uniform(-100, 100) for _ in range(20)]
    with localcontext() as context:
        context.prec = 20000
        for _ in range(512):
            expected, observed = rng.choices(values, k=2)
            tolerance = rng.choice([0, 1e-300, 1e-3, 1, 2, 10**4000])
            relative = bool(rng.getrandbits(1))
            distance = abs(Decimal(observed) - Decimal(expected))
            limit = Decimal(tolerance) * (abs(Decimal(expected)) if relative else 1)
            assert r.compare(expected, observed, tolerance, relative)[0] == (
                r.MATCH if distance <= limit else r.MISMATCH
            )
    accepted("512 comparisons against independent Decimal arithmetic")
    for args in [
        (math.inf, 1, 0.001, True),
        (1, 100, math.inf, False),
        (True, 1, 0, False),
        (1, True, 0, False),
        (1, 1, -1, False),
        (1, 1, 0, "false"),
        (1, math.nan, 0, False),
    ]:
        try:
            r.compare(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid numeric domain accepted")
    accepted("nonfinite and mistyped domains refused")
    assert r.compare(2**53, 2**53 + 1, 0)[0] == r.MISMATCH
    accepted("one-unit integer error above binary64 exact range rejected")

    with tempfile.TemporaryDirectory(prefix="eidos-reproduction 科研 ") as directory:
        base = Path(directory)

        def fixture(name, output='{"value":1}', body=None):
            root = base / name
            root.mkdir()
            (root / "worker.py").write_text(
                body if body is not None else "print(" + repr(output) + ")\n",
                encoding="utf-8",
            )
            (root / "data.txt").write_text("original", encoding="utf-8")
            spec = {
                "paper": "controlled-paper",
                "tool": "deterministic scalar stub",
                "command": [sys.executable, "-I", "-X", "utf8", "worker.py"],
                "expected": 1,
                "tolerance": 0,
                "inputs": ["data.txt"],
                "registered_at": "2020-01-01T00:00:00+00:00",
                "seed": None,
                "seed_reason": "deterministic represented inputs",
                "data_version": "benign-stub-v1",
                "config_version": "receipt-schema-2",
            }
            source = root / "spec.json"
            source.write_text(json.dumps(spec), encoding="utf-8")
            return root, spec, source

        root, spec, source = fixture("positive with spaces")
        record = r.run_spec(spec, cwd=root, source_file=source)
        assert record["verdict"] == r.MATCH, record
        assert not r.validate_record(record, root, spec["paper"], require_source=True)
        r.write(record, root / "artifacts/reproduction")
        findings, blocked = ScientificValidityGate(root)._reproduction_verdict(
            "C", spec["paper"]
        )
        assert not findings and not blocked, (findings, blocked)
        accepted("executed source-bound MATCH and S12 positive control")
        (root / "data.txt").write_text("changed", encoding="utf-8")
        assert r.validate_record(record, root, spec["paper"], require_source=True)
        accepted("declared data changes invalidate an existing MATCH")

        for name, output in [
            ("duplicate", '{"value":1,"value":2}'),
            ("nan", '{"value":NaN}'),
            ("overflow", '{"value":1,"other":1e999}'),
            ("boolean", '{"value":true}'),
            ("multiple", '{"value":2}\n{"value":1}'),
            ("multiline-prefix", '{"value":2,\n"other":0}\n{"value":1}'),
        ]:
            root, spec, source = fixture(name, output)
            record = r.run_spec(spec, cwd=root, source_file=source)
            assert record["verdict"] == r.UNRUN, record
            accepted("reject " + name + " output")

        root, spec, source = fixture(
            "invalid preflight", body="from pathlib import Path;Path('started').touch()"
        )
        spec["relative"] = "false"
        source.write_text(json.dumps(spec), encoding="utf-8")
        try:
            r.run_spec(spec, cwd=root, source_file=source)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid spec launched")
        assert not (root / "started").exists()
        accepted("invalid spec refused before launch")

        root, spec, source = fixture("bundle")
        bundle = {
            "paper": spec["paper"],
            "registered_at": spec["registered_at"],
            "specs": [spec, {**spec, "expected": 2}],
        }
        source.write_text(json.dumps(bundle), encoding="utf-8")
        record = r.run_set(bundle, cwd=root, source_file=source)
        assert record["verdict"] == r.MISMATCH
        assert not r.validate_record(record, root, spec["paper"], require_source=True)
        accepted("complete bundle preserves the mismatching result")
        r.write(record["specs"][0], root / "artifacts/reproduction")
        findings, blocked = ScientificValidityGate(root)._reproduction_verdict(
            "C", spec["paper"]
        )
        assert not findings and blocked
        accepted("successful child cannot qualify the complete paper")
        record["specs"].pop()
        record["spec_inventory"].pop()
        record["spec_count"] = 1
        record["counts"] = {r.MATCH: 1, r.MISMATCH: 0, r.UNRUN: 0}
        record["verdict"] = r.MATCH
        r._seal(
            record
        )  # Local checksum is deliberately not an authentication boundary.
        assert r.validate_record(record, root, spec["paper"], require_source=True)
        accepted("trimmed and resealed bundle rejected against original inventory")

        root, spec, source = fixture(
            "mutation",
            body="from pathlib import Path;Path('data.txt').write_text('changed');print('{\"value\":1}')",
        )
        assert r.run_spec(spec, cwd=root, source_file=source)["verdict"] == r.UNRUN
        accepted("input mutation during execution is UNRUN")
        leaf = "from pathlib import Path;import time;Path('ready').touch();time.sleep(3);Path('late').touch()"
        body = (
            "import subprocess,sys,time\nfrom pathlib import Path\n"
            "subprocess.Popen([sys.executable,'-c'," + repr(leaf) + "])\n"
            "while not Path('ready').exists():time.sleep(.01)\n"
            "print('stdout-ready',flush=True)\nprint('stderr-ready',file=sys.stderr,flush=True)\ntime.sleep(20)\n"
        )
        root, spec, source = fixture("timeout", body=body)
        record = r.run_spec(spec, cwd=root, source_file=source, timeout=1.2)
        assert record["verdict"] == r.UNRUN and record["exit_code"] == 124, record
        assert "stdout-ready" in record["stdout"] and "stderr-ready" in record["stderr"]
        assert (root / "ready").exists()
        time.sleep(3.2)
        assert not (root / "late").exists()
        accepted("owned timeout closes descendants and retains both streams")
        for paper in ["a/b", "a?b", "CON.foo", "NUL.txt", "Foo", "foo"]:
            value = {"paper": paper, "verdict": r.UNRUN}
            r.write(value, root / "names")
            assert r.load(paper, root / "names") == value
        assert len(list((root / "names").glob("*.json"))) == 6
        accepted("portable paper identities round trip without overwriting")

    base = installed.parents[1]
    modules = {
        p.relative_to(base.parent)
        .as_posix(): hashlib.sha256(
            p.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").encode()
        )
        .hexdigest()
        for p in sorted(base.rglob("*.py"))
    }
    print(
        json.dumps(
            {
                "generated": datetime.now(timezone.utc).isoformat(),
                "platform": sys.platform,
                "sdk_version": version("eidos"),
                "optimization_level": sys.flags.optimize,
                "python": sys.version,
                "executable": sys.executable,
                "installed_module": str(installed),
                "source_sha256_canonical_lf": modules,
                "cases": cases,
                "oracle_comparisons": 512,
                "seed": 20261101,
                "scope": "Installed SDK numeric and receipt boundary with benign stubs; not paper training, signed attestation, service migration or new-machine qualification.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
