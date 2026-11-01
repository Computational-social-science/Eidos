"""Bounded single-writer ownership for report directories and atomic file publication."""
from __future__ import annotations
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import threading
import time

_thread_locks = {}
_thread_locks_guard = threading.Lock()
_owned = threading.local()


@contextmanager
def output_lock(directory: Path, timeout: float = 120):
    directory = Path(directory).resolve()
    with _thread_locks_guard:
        thread_lock = _thread_locks.setdefault(directory, threading.RLock())
    if not thread_lock.acquire(timeout=timeout):
        raise TimeoutError('another report export owns '+str(directory))
    try:
        owned = getattr(_owned, 'directories', None)
        if owned is None:
            owned = _owned.directories = set()
        if directory in owned:
            yield
            return
        with _file_lock(directory, timeout):
            owned.add(directory)
            try:
                yield
            finally:
                owned.remove(directory)
    finally:
        thread_lock.release()


@contextmanager
def _file_lock(directory: Path, timeout: float):
    directory.parent.mkdir(parents=True, exist_ok=True)
    path = directory.parent / ('.eidos-export-'+directory.name+'.lock')
    # The lock path persists: deleting it creates an inode race between waiters.
    with path.open('a+b') as handle:
        deadline = time.monotonic()+timeout
        while True:
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError('another report export owns '+str(directory))
                time.sleep(.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


@contextmanager
def atomic_output(path: Path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, name=tempfile.mkstemp(prefix='.'+path.stem+'-',suffix=path.suffix,dir=path.parent)
    os.close(fd)
    temporary=Path(name)
    try:
        yield temporary
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
