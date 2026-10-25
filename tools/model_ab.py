"""CLI for the decision-model A/B. See framework/model_ab.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.model_ab import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
