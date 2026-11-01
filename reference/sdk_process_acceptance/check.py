"""Qualify an installed SDK from outside its checkout; only finite fixture workers."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distributions, version
import json
from pathlib import Path
import sys
import tempfile
import time

import framework.project as sdk
from framework.subprocesses import run_tree


def fixture(root: Path, *, normal=False, nested=False) -> sdk.ProjectSpec:
    root.mkdir()
    (root / "leaf.py").write_text(
        "from pathlib import Path\nimport os,time\n"
        "Path('ready').write_text(str(os.getpid()))\n"
        + ("time.sleep(1.2)\n" if normal else "time.sleep(5)\n")
        + "Path('late').write_text('escaped lifecycle')\ntime.sleep(1)\n", encoding="utf-8")
    if nested:
        body = ("from pathlib import Path\nimport sys\nfrom framework.subprocesses import run_tree\n"
                "run_tree([sys.executable,'-X','utf8','leaf.py'],cwd=Path.cwd(),timeout=20)\n")
    else:
        body = ("import subprocess,sys,time\nfrom pathlib import Path\n"
                "print('进程 progress',flush=True)\nprint('诊断 diagnostic',file=sys.stderr,flush=True)\n"
                "subprocess.Popen([sys.executable,'-X','utf8','leaf.py'])\n"
                "while not Path('ready').exists():time.sleep(.01)\n"
                + ("" if normal else "time.sleep(30)\n"))
    (root / "worker.py").write_text(body, encoding="utf-8")
    return sdk.ProjectSpec("wheel_lifecycle", root, [sys.executable, "-X", "utf8", "worker.py"])


def main() -> int:
    if sys.flags.optimize:
        raise SystemExit("Qualification requires active assertions; omit -O/-OO.")
    parser = argparse.ArgumentParser(description=__doc__)
    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--expect-nested-leak", action="store_true", help="negative-control candidate only")
    controls.add_argument("--expect-handoff-leak", action="store_true", help="pre-cleanup-handoff candidate only")
    args = parser.parse_args()
    installed = Path(sdk.__file__).resolve()
    assert installed.is_relative_to(Path(sys.prefix).resolve()), installed
    modules = {}
    for name in ("_process_tree.py", "_windows_job.py"):
        path = installed.parent / name
        modules[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if (installed.parent / "_posix_job.py").exists():
        modules["_posix_job.py"] = hashlib.sha256((installed.parent / "_posix_job.py").read_bytes()).hexdigest()
    results = []
    with tempfile.TemporaryDirectory(prefix="eidos-wheel 科研 ") as directory:
        base = Path(directory)
        if not args.expect_nested_leak and not args.expect_handoff_leak:
            spec = fixture(base / "timeout with spaces")
            started = time.monotonic()
            result = sdk.run_command(spec, timeout=3)
            assert result.status == "ERROR" and result.exit_code == 124, result.as_dict()
            assert time.monotonic() - started < 4.5
            assert (spec.root / "ready").exists()
            time.sleep(2.5)
            assert not (spec.root / "late").exists()
            assert "进程 progress" in result.stdout_tail and "诊断 diagnostic" in result.stderr_tail
            results.append({"case": "timeout kills inherited descendants", "accepted": True})
            spec = fixture(base / "normal", normal=True)
            result = sdk.run_command(spec, timeout=3)
            assert result.status == "PASS", result.as_dict()
            time.sleep(1.5)
            assert not (spec.root / "late").exists()
            results.append({"case": "normal exit closes inherited-output descendants", "accepted": True})
        spec = fixture(base / "nested", nested=True)
        if args.expect_handoff_leak:
            spec = handoff_fixture(base / "handoff")
        result = sdk.run_command(spec, timeout=3)
        assert result.status == "ERROR" and result.exit_code == 124, result.as_dict()
        assert (spec.root / "ready").exists(), "nested worker must actually start"
        time.sleep(2.5)
        leaked = (spec.root / "late").exists()
        expected_leak = args.expect_nested_leak or args.expect_handoff_leak
        assert leaked is expected_leak, (leaked, expected_leak)
        results.append({"case": "normal-root cleanup handoff" if args.expect_handoff_leak else "nested SDK scopes", "leaked": leaked,
                        "negative_control": expected_leak, "expected_outcome": True})
        if args.expect_handoff_leak:
            assert (spec.root / "cleanup-wait").exists(), "handoff window must be reached"
        if not expected_leak:
            if sys.platform != "win32":
                handoff = handoff_fixture(base / "handoff")
                h = sdk.run_command(handoff, timeout=3)
                assert h.status == "ERROR" and h.exit_code == 124
                assert (handoff.root / "cleanup-wait").exists()
                time.sleep(2.5)
                assert not (handoff.root / "late").exists()
                results.append({"case": "normal-root handoff survives caller cleanup delay", "accepted": True})
            result = sdk.run_command(sdk.ProjectSpec("business_exit", base,
                [sys.executable, "-c", "raise SystemExit(125)"], exit_statuses={125: "OPEN"}))
            assert result.status == "OPEN" and result.exit_code == 125
            results.append({"case": "worker code 125 remains research OPEN", "accepted": True})
            result = sdk.run_command(sdk.ProjectSpec("missing", base, [str(base / "no-such-executable")]))
            assert result.status == "SKIP" and result.exit_code == 127
            results.append({"case": "missing executable remains SKIP", "accepted": True})
            if sys.platform == "win32":
                command = [sys.executable, "-c", "import ctypes;f=ctypes.windll.kernel32.GetConsoleWindow;f.restype=ctypes.c_void_p;print(int(f() or 0))"]
                result = run_tree(command, cwd=base, timeout=10)
                assert result.returncode == 0 and result.stdout.strip() == "0"
                results.append({"case": "Windows worker has no console window", "console_window": 0, "accepted": True})
    print(json.dumps({"generated": datetime.now(timezone.utc).isoformat(), "platform": sys.platform,
                      "python": sys.version, "executable": sys.executable, "installed_module": str(installed),
                      "sdk_version": version("eidos"),
        "optimization_level": sys.flags.optimize, "module_sha256": modules, "cases": results,
                      "dependencies": sorted(set((d.metadata.get("Name"), d.version) for d in distributions())),
                      "scope": "Installed wheel lifecycle only; no GPU, network service migration, clean-24h or arbitrary escaped-process sandbox qualification."}, ensure_ascii=False))
    return 0


def handoff_fixture(root: Path) -> sdk.ProjectSpec:
    spec = fixture(root, normal=True)
    # Keep the descendant alive past the outer deadline, while its direct root
    # exits normally and the inner calling process is deliberately slow to clean.
    leaf = root / "leaf.py"
    leaf.write_text(leaf.read_text(encoding="utf-8").replace("time.sleep(1.2)", "time.sleep(5)"), encoding="utf-8")
    (root / "normal.py").write_text((root / "worker.py").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "worker.py").write_text(
        "from pathlib import Path\nimport sys,time\nfrom framework import _process_tree as r\n"
        "original=r.os.killpg\n"
        "def slow(group,sig):\n Path('cleanup-wait').touch()\n time.sleep(8)\n original(group,sig)\n"
        "r.os.killpg=slow\n"
        "r.run_tree([sys.executable,'-X','utf8','normal.py'],cwd=Path.cwd(),timeout=20)\n", encoding="utf-8")
    return spec


if __name__ == "__main__":
    raise SystemExit(main())
