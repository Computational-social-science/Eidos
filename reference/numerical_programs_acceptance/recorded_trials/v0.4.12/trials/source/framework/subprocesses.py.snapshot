"""Console policy for noninteractive background probes and scheduled checks."""
import os
import subprocess

from ._process_tree import ProcessContainmentError, run_tree, validate_timeout


def quiet_flags() -> int:
    """Hide a Windows console while keeping captured output and the process tree."""
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
