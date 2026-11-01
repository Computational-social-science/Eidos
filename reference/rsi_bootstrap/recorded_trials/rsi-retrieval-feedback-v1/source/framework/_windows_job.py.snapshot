"""Internal stdlib helper: acquire a kill-on-close Job before starting a worker.

Status is separate from scientific stdout; worker exit codes remain unchanged.
https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys


def own_job() -> int:
    class BasicLimits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t),
                    ("max_ws", ctypes.c_size_t), ("active", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]

    class Limits(ctypes.Structure):
        _fields_ = [("basic", BasicLimits), ("io", ctypes.c_uint64 * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Limits()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    return handle  # Retained until process exit; never inherited by the worker.


def main() -> int:
    if len(sys.argv) < 3:
        return 2
    status = Path(sys.argv[1])
    try:
        handle = own_job()
    except OSError as exc:
        report = {"state": "containment_error", "message": "containment setup failed: " + str(exc)}
    else:
        try:
            result = subprocess.run(sys.argv[2:], stdin=subprocess.DEVNULL,
                                    stdout=sys.stdout, stderr=sys.stderr,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            report = {"state": "launch_error", "message": str(exc), "errno": exc.errno,
                      "filename": exc.filename}
        else:
            report = {"state": "complete", "returncode": result.returncode}
        assert handle
    with status.open("x", encoding="utf-8") as stream:
        json.dump(report, stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
