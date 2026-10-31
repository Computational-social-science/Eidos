"""Source-tool compatibility entry; implementation ships inside the SDK wheel."""
from pathlib import Path
import runpy

_implementation = runpy.run_path(str(Path(__file__).resolve().parents[1] / "framework/_process_tree.py"),
                                run_name="_eidos_tool_process_tree")
run_tree = _implementation["run_tree"]
