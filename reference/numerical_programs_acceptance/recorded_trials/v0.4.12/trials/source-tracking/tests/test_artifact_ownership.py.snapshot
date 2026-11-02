"""Concurrent exports must not corrupt another writer's report bundle."""
import subprocess
import sys

import pytest
from framework.artifacts import output_lock, atomic_output


def test_second_process_cannot_enter_owned_export_directory(tmp_path):
    directory=tmp_path/'report'
    script=('from pathlib import Path\nfrom framework.artifacts import output_lock\n'
            f'with output_lock(Path({str(directory)!r}),timeout=.1):\n print("wrong owner")\n')
    with output_lock(directory):
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=5)
        assert result.returncode != 0 and 'TimeoutError' in result.stderr
    with output_lock(directory,timeout=.1):
        pass


def test_failed_file_export_keeps_previous_artifact(tmp_path):
    path=tmp_path/'bundle.zip';path.write_bytes(b'old complete bundle')
    with pytest.raises(ValueError):
        with atomic_output(path) as temporary:
            temporary.write_bytes(b'incomplete')
            raise ValueError('producer failed')
    assert path.read_bytes()==b'old complete bundle'


def test_nested_publication_owner_retains_exclusion(tmp_path):
    directory=tmp_path/'report'
    script=('from pathlib import Path\nfrom framework.artifacts import output_lock\n'
            f'with output_lock(Path({str(directory)!r}),timeout=.1):\n print("wrong owner")\n')
    with output_lock(directory):
        with output_lock(directory, timeout=.1):
            pass
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=5)
        assert result.returncode != 0 and 'TimeoutError' in result.stderr
