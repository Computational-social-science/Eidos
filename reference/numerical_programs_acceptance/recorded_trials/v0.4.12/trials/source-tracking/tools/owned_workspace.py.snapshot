"""Temporary research workspaces with explicit cleanup ownership."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile


@contextmanager
def owned_workspace(parent: Path, *, prefix: str, keep: bool = False):
    parent=parent.resolve()
    parent.mkdir(parents=True,exist_ok=True)
    workspace=Path(tempfile.mkdtemp(prefix=prefix,dir=parent)).resolve()
    original=workspace.stat()
    identity=(original.st_dev,original.st_ino)
    if not original.st_ino:
        raise RuntimeError(f'filesystem cannot identify owned workspace; retained: {workspace}')
    try:
        yield workspace
    finally:
        if keep:
            print(f'Rehearsal workspace retained: {workspace}')
        else:
            current=workspace.lstat()
            if (workspace.resolve()!=workspace or workspace.parent!=parent or
                    (current.st_dev,current.st_ino)!=identity):
                raise RuntimeError(f'refusing cleanup of a replaced rehearsal workspace: {workspace}')
            shutil.rmtree(workspace)
