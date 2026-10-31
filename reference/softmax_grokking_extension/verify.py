"""Extension acceptance reuses the independent parent validator."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from reference.softmax_grokking.verify import validate as _validate, main as _main


def validate(report, protocol, *, check_files=True):
    return _validate(report, protocol, check_files=check_files, base=HERE, extension=True)


if __name__ == "__main__": raise SystemExit(_main(HERE, extension=True))
