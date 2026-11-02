"""Compatibility entry for the SDK's stdlib Windows ownership helper."""
from pathlib import Path
import runpy
import json
import sys
import tempfile

_implementation = runpy.run_path(str(Path(__file__).resolve().parents[1] / "framework/_windows_job.py"),
                                run_name="_eidos_tool_windows_job")
own_job = _implementation["own_job"]


def main() -> int:
    """Keep the former `tools/windows_job.py COMMAND ...` internal CLI usable."""
    if len(sys.argv) < 2:
        return 2
    with tempfile.TemporaryDirectory(prefix="eidos-legacy-job-") as temporary:
        status = Path(temporary) / "status.json"
        original = sys.argv
        sys.argv = [original[0], str(status), *original[1:]]
        try:
            code = _implementation["main"]()
        finally:
            sys.argv = original
        if code:
            return code
        report = json.loads(status.read_text(encoding="utf-8"))
        if report.get("state") == "complete":
            return report["returncode"]
        print(report.get("message", "execution helper failed"), file=sys.stderr)
        return 127 if report.get("state") == "launch_error" else 125

if __name__ == "__main__":
    raise SystemExit(main())
