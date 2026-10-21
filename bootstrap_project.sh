#!/usr/bin/env bash
# bootstrap_project.sh - Create a new research project from the global framework
# Usage: ./bootstrap_project.sh <project_name> [--force]

set -euo pipefail

FRAMEWORK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="${1:-}"
FORCE="${2:-}"

if [[ -z "$PROJECT_NAME" ]]; then
    echo "Usage: $0 <project_name> [--force]"
    echo "Example: $0 nlp_discovery_001"
    exit 1
fi

PROJECT_DIR="$FRAMEWORK_ROOT/projects/$PROJECT_NAME"

if [[ -d "$PROJECT_DIR" && "$FORCE" != "--force" ]]; then
    echo "Error: Project '$PROJECT_NAME' already exists. Use --force to overwrite."
    exit 1
fi

echo "🚀 Bootstrapping project: $PROJECT_NAME"
echo "   Framework root: $FRAMEWORK_ROOT"
echo "   Project dir:    $PROJECT_DIR"

# Create project structure
mkdir -p "$PROJECT_DIR"/{configs,data,manuscript,experiments,outputs,scripts,docs}

# Copy project skeleton template (tolerate an empty skeleton: the script
# creates every required directory itself below).
if [[ -d "$FRAMEWORK_ROOT/templates/project_skeleton" ]] && \
   compgen -G "$FRAMEWORK_ROOT/templates/project_skeleton/*" > /dev/null; then
    cp -r "$FRAMEWORK_ROOT/templates/project_skeleton/"* "$PROJECT_DIR/"
    echo "✅ Copied project skeleton"
else
    echo "ℹ️  Project skeleton is empty or absent; using the built-in structure"
fi

# Create project-specific config from global template
FRAMEWORK_CONFIG="$FRAMEWORK_ROOT/configs/global/framework.yaml"
PROJECT_CONFIG="$PROJECT_DIR/configs/project.yaml"

if [[ -f "$FRAMEWORK_CONFIG" ]]; then
    # Create project config with placeholders
    cat > "$PROJECT_CONFIG" << EOF
# Project-specific configuration for $PROJECT_NAME
# Inherits from global framework.yaml - only override what's needed

project:
  name: "$PROJECT_NAME"
  description: "TODO: Add project description"
  created: "$(date -Iseconds)"
  framework_version: "4.0"

# Override these as needed:
# quality_gates:
#   quantitative:
#     protocols:
#       - acceptance-gate
#       - planted-truth
#       - independence-bookkeeping
#   semantic:
#     tools:
#       - inspect
#       - deepeval
#       - promptfoo
#       - ragas

# human_gates:
#   mandatory:
#     - hypothesis_confirmation
#     - critical_experiment_design
#     - final_manuscript_submission

# inference:
#   max_concurrent: 1

# Override paths if needed:
paths:
  data: "data"
  manuscript: "manuscript"
  experiments: "experiments"
  outputs: "outputs"
  scripts: "scripts"

# Project-specific gates (add or disable)
gates:
  enable_all: true
  disable: []
EOF
    echo "✅ Created project config: $PROJECT_CONFIG"
fi

# Create default Quarto manuscript
MANUSCRIPT_DIR="$PROJECT_DIR/manuscript"
mkdir -p "$MANUSCRIPT_DIR"
if [[ ! -f "$MANUSCRIPT_DIR/_quarto.yml" ]]; then
    cat > "$MANUSCRIPT_DIR/_quarto.yml" << EOF
project:
  type: manuscript
  title: "$PROJECT_NAME"
  author: "TODO: Add authors"
  date: "$(date +%Y-%m-%d)"

format:
  pdf:
    documentclass: article
    number-sections: true
    geometry: margin=1in
  docx: default
  html:
    theme: cosmo
    toc: true
    code-fold: true

execute:
  freeze: auto
  cache: true
  echo: false
  warning: false

bibliography: references.bib
csl: apa.csl
EOF
    echo "✅ Created Quarto manuscript config"
fi

# Create minimal manuscript content
if [[ ! -f "$MANUSCRIPT_DIR/index.qmd" ]]; then
    cat > "$MANUSCRIPT_DIR/index.qmd" << EOF
---
title: "$PROJECT_NAME"
author: "TODO"
date: "$(date +%Y-%m-%d)"
abstract: |
  TODO: Write abstract
---

# Introduction

TODO: Write introduction

# Methods

TODO: Describe methods

# Results

TODO: Present results

# Discussion

TODO: Discuss findings

# References

::: {#refs}
:::
EOF
    echo "✅ Created manuscript template"
fi

# Create references.bib
if [[ ! -f "$MANUSCRIPT_DIR/references.bib" ]]; then
    cat > "$MANUSCRIPT_DIR/references.bib" << EOF
% Bibliography for $PROJECT_NAME
% Add entries in BibTeX format

@article{example2024,
  title={Example Paper Title},
  author={Author, A. and Author, B.},
  journal={Journal Name},
  volume={1},
  number={1},
  pages={1--10},
  year={2024}
}
EOF
    echo "✅ Created bibliography template"
fi

# Create project scripts
SCRIPTS_DIR="$PROJECT_DIR/scripts"
mkdir -p "$SCRIPTS_DIR"

# Create experiment runner
cat > "$SCRIPTS_DIR/run_experiment.py" << 'EOF'
#!/usr/bin/env python3
"""
Experiment runner for PROJECT_NAME
Inherits from global framework's experiment orchestration
"""
import argparse
import yaml
from pathlib import Path

def load_config():
    project_root = Path(__file__).parent.parent
    with open(project_root / "configs" / "project.yaml") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Run experiment for PROJECT_NAME")
    parser.add_argument("--config", help="Experiment config file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    config = load_config()
    print(f"Running experiment for {config.get('project', {}).get('name', 'UNKNOWN')}")
    print(f"Config: {args.config}")
    print(f"Dry run: {args.dry_run}")
    
    # TODO: Implement experiment logic
    # This inherits from global framework's orchestration layer
    
if __name__ == "__main__":
    main()
EOF
chmod +x "$SCRIPTS_DIR/run_experiment.py"

# Create evaluation runner
cat > "$SCRIPTS_DIR/run_evaluation.py" << 'EOF'
#!/usr/bin/env python3
"""
Evaluation runner - runs both BootLoops (quantitative) and semantic gates
"""
import argparse
import yaml
from pathlib import Path

def load_config():
    project_root = Path(__file__).parent.parent
    with open(project_root / "configs" / "project.yaml") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Run evaluation gates")
    parser.add_argument("--quantitative-only", action="store_true")
    parser.add_argument("--semantic-only", action="store_true")
    parser.add_argument("--gate", choices=["acceptance", "planted-truth", "inspect", "deepeval", "promptfoo", "ragas"])
    args = parser.parse_args()
    
    config = load_config()
    print(f"Running evaluation for {config.get('project', {}).get('name', 'UNKNOWN')}")
    
    # TODO: Implement gate execution
    # This runs both BootLoops and semantic gates
    
if __name__ == "__main__":
    main()
EOF
chmod +x "$SCRIPTS_DIR/run_evaluation.py"

# Create manuscript builder
cat > "$SCRIPTS_DIR/build_manuscript.py" << 'EOF'
#!/usr/bin/env python3
"""
Build manuscript in all formats via Quarto
"""
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Build manuscript via Quarto")
    parser.add_argument("--format", choices=["pdf", "docx", "html", "all"], default="all")
    parser.add_argument("--no-freeze", action="store_true")
    args = parser.parse_args()
    
    manuscript_dir = Path(__file__).parent.parent / "manuscript"
    
    cmd = ["quarto", "render", "index.qmd"]
    if args.format != "all":
        cmd.extend(["--to", args.format])
    if args.no_freeze:
        cmd.append("--no-freeze")
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=manuscript_dir)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
EOF
chmod +x "$SCRIPTS_DIR/build_manuscript.py"

# Create executable package builder
cat > "$SCRIPTS_DIR/build_package.py" << 'EOF'
#!/usr/bin/env python3
"""
Build one-click executable package (Docker + Binder)
"""
import subprocess
import yaml
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Build executable package")
    parser.add_argument("--docker", action="store_true", help="Build Docker image")
    parser.add_argument("--binder", action="store_true", help="Generate Binder config")
    parser.add_argument("--tag", default="latest", help="Docker tag")
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    
    if args.docker:
        print(f"Building Docker image: {args.tag}")
        subprocess.run([
            "docker", "build", 
            "-t", f"{args.tag}",
            "-f", "Dockerfile",
            "."
        ], cwd=project_root, check=True)
    
    if args.binder:
        print("Generating Binder configuration...")
        # Generate binder/apt.txt, binder/requirements.txt, binder/postBuild
        binder_dir = project_root / "binder"
        binder_dir.mkdir(exist_ok=True)
        
        # Generate requirements.txt from project
        subprocess.run([
            "pip", "freeze"
        ], cwd=project_root, 
        stdout=open(binder_dir / "requirements.txt", "w"),
        check=True)
        
        # Generate apt.txt
        (binder_dir / "apt.txt").write_text("# System packages\n")
        
        # Generate postBuild
        (binder_dir / "postBuild").write_text("""#!/bin/bash
# Post-build setup for Binder
pip install -e .
""")
        (binder_dir / "postBuild").chmod(0o755)
    
    print("✅ Package build complete")

if __name__ == "__main__":
    main()
EOF
chmod +x "$SCRIPTS_DIR/build_package.py"

# Create gitignore
cat > "$PROJECT_DIR/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*.so
.env
.venv
venv/

# Data
data/raw/
data/processed/
*.parquet
*.pkl

# Outputs
outputs/
*.log

# Quarto
manuscript/_freeze/
manuscript/_extensions/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Docker
.docker/

# Binder
binder/
EOF
