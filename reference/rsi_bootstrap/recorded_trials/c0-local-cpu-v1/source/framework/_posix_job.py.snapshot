"""POSIX scope guardian: owner-pipe EOF closes this group, including nested scopes."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading


def main() -> int:
    if len(sys.argv) < 4:
        return 2
    control, status = int(sys.argv[1]), int(sys.argv[2])
    owns_group = os.getpgrp() == os.getpid()
    if not owns_group:
        report = {"state": "containment_error", "message": "guardian is not its process-group leader"}
    else:
        def owner_lost():
            # Only the immediate calling process owns the pipe's write end. A
            # killed outer SDK caller thus closes its nested guardian's group.
            try:
                os.read(control, 1)
            finally:
                os.killpg(os.getpgrp(), signal.SIGKILL)
        threading.Thread(target=owner_lost, daemon=True).start()
        try:
            result = subprocess.run(sys.argv[3:], stdin=subprocess.DEVNULL,
                                    stdout=sys.stdout, stderr=sys.stderr, close_fds=True)
        except OSError as exc:
            report = {"state": "launch_error", "errno": exc.errno,
                      "message": str(exc), "filename": exc.filename}
        else:
            report = {"state": "complete", "returncode": result.returncode}
    with os.fdopen(status, "w", encoding="utf-8", closefd=False) as stream:
        json.dump(report, stream)
    if owns_group:
        # Do not hand cleanup back to a caller that can itself be killed. Publish
        # the worker result, then close the complete group (including this helper)
        # in one kernel operation. Parent return code -SIGKILL is transport-only.
        os.killpg(os.getpgrp(), signal.SIGKILL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
