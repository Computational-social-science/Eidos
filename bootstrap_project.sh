#!/usr/bin/env bash
# Compatibility entry point; the Python bootstrap owns validation and scaffolding.
# Usage: PYTHON=/path/to/python ./bootstrap_project.sh <project_name>
set -euo pipefail

for argument in "$@"; do
    if [[ "$argument" == "--force" ]]; then
        echo "Error: --force is refused; existing research must not be overwritten." >&2
        exit 2
    fi
done
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <project_name> (no overwrite or --force)" >&2
    exit 2
fi

FRAMEWORK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python}" "$FRAMEWORK_ROOT/tools/bootstrap_project.py" \
    --name "$1" --dest "$FRAMEWORK_ROOT/projects/$1"
