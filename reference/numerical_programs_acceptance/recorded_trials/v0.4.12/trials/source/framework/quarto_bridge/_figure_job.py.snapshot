"""Render one trusted Python/Matplotlib figure in a bounded SDK worker."""

from pathlib import Path
import runpy
import sys


def main() -> int:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    script, output, project = map(Path, sys.argv[1:])
    sys.path[:0] = [str(script.parent), str(project)]
    sys.argv = [str(script)]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        if exc.code is not None and not (isinstance(exc.code, int) and exc.code == 0):
            raise
    numbers = plt.get_fignums()
    if len(numbers) != 1:
        raise ValueError("figure script must leave exactly one open Matplotlib figure")
    figure = plt.figure(numbers[0])
    figure.savefig(output, format=output.suffix[1:], dpi=600)
    plt.close("all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
