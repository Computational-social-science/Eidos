"""
Quarto Bridge Module
Handles multi-format manuscript rendering and package generation
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import subprocess
import yaml
import json
import os
import shutil
from datetime import datetime

class QuartoBridge:
    """
    Bridge between research pipeline and Quarto for multi-format rendering.
    Handles manuscript rendering, figure generation, and executable package creation.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.project_root = Path(self.config.get("project_root", ".")).resolve()
        self.manuscript_dir = self.project_root / self.config.get("manuscript_dir", "manuscript")
        self.output_dir = self.project_root / self.config.get("output_dir", "outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Quarto configuration
        self.quarto_config = self.config.get("quarto", {})
        
        # Check Quarto availability
        self.quarto_available = self._check_quarto()
    
    def _check_quarto(self) -> bool:
        """Locate Quarto once and remember the executable that answered.

        A bare `quarto` lookup is not enough on this host: Quarto ships inside a
        desktop toolchain and is not on PATH, while the project it serves renders
        fine. The first candidate that answers `--version` is stored, so a render
        call cannot disagree with the probe.
        """
        for candidate in self._quarto_candidates():
            try:
                from framework.subprocesses import quiet_flags
                result = subprocess.run([candidate, "--version"],
                                        capture_output=True, text=True, timeout=30, creationflags=quiet_flags())
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0:
                self.quarto_cmd = candidate
                return True
        self.quarto_cmd = None
        return False

    def _quarto_candidates(self):
        """Ordered candidates, all derived from environment or the home directory."""
        env = os.environ.get("QUARTO_BIN")
        if env:
            yield env
        found = shutil.which("quarto")
        if found:
            yield found
        home = Path.home()
        for rel in (".workbuddy-ai/binaries/quarto/bin/quarto.exe",
                    "AppData/Local/Programs/Quarto/bin/quarto.exe",
                    ".local/bin/quarto",
                    "opt/quarto/bin/quarto"):
            path = home / rel
            if path.is_file():
                yield str(path)
        program_files = os.environ.get("PROGRAMFILES")
        if program_files:
            path = Path(program_files) / "Quarto" / "bin" / "quarto.exe"
            if path.is_file():
                yield str(path)
    
    def render(self, format: str = "all", no_freeze: bool = False) -> Dict[str, Any]:
        """
        Render manuscript to specified format(s).
        
        Args:
            format: "pdf", "docx", "html", "all"
            no_freeze: Skip freeze (use cached computations)
        
        Returns:
            Dict with render results
        """
        if not self.quarto_available:
            return {"success": False, "error": "Quarto not installed"}
        
        manuscript_file = self.manuscript_dir / "index.qmd"
        if not manuscript_file.exists():
            return {"success": False, "error": f"Manuscript not found: {manuscript_file}"}
        
        formats = ["pdf", "docx", "html"] if format == "all" else [format]
        from framework.subprocesses import quiet_flags
        results = {}
        
        for fmt in formats:
            cmd = [self.quarto_cmd or "quarto", "render", "index.qmd", "--to", fmt]
            if no_freeze:
                cmd.append("--no-freeze")
            
            try:
                result = subprocess.run(
                    cmd, cwd=self.manuscript_dir,
                    capture_output=True, text=True, timeout=300, creationflags=quiet_flags()
                )
                results[fmt] = {
                    "success": result.returncode == 0,
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:]
                }
            except subprocess.TimeoutExpired:
                results[fmt] = {"success": False, "error": "Timeout"}
            except Exception as e:
                results[fmt] = {"success": False, "error": str(e)}
        
        return {
            "success": all(r.get("success", False) for r in results.values()),
            "formats": results,
            "output_dir": str(self.output_dir)
        }
    
    def render_figure(self, figure_script: Path, output_format: str = "pdf") -> Dict[str, Any]:
        """
        Render a single figure script via Quarto.
        
        Args:
            figure_script: Path to figure generation script
            output_format: "pdf", "svg", "png"
        
        Returns:
            Dict with render result
        """
        if not self.quarto_available:
            return {"success": False, "error": "Quarto not installed"}
        
        # Create temporary Quarto document for figure
        figure_dir = self.output_dir / "figures"
        figure_dir.mkdir(parents=True, exist_ok=True)
        
        temp_qmd = figure_dir / f"figure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.qmd"
        
        qmd_content = f"""---
title: "Figure"
format: 
  {figure_dir / 'output.pdf' if output_format == 'pdf' else 'output.svg'}:
    fig-width: 6
    fig-height: 4
execute:
  echo: false
---

```{{python}}
# Figure generation script
import sys
sys.path.insert(0, '{self.project_root}')
exec(open('{figure_script}').read())
```
"""
        
        temp_qmd.write_text(qmd_content)
        
        try:
            cmd = [self.quarto_cmd or "quarto", "render", str(temp_qmd)]
            from framework.subprocesses import quiet_flags
            result = subprocess.run(
                cmd, cwd=figure_dir, capture_output=True, text=True, timeout=120, creationflags=quiet_flags()
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def build_executable_package(self, output_name: str = None) -> Dict[str, Any]:
        """
        Build one-click executable package (Docker + Binder).
        
        Returns:
            Dict with build results
        """
        package_name = output_name or f"research_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        package_dir = self.output_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        
        results = {"package_dir": str(package_dir), "artifacts": []}
        
        # 1. Generate Dockerfile
        dockerfile = self._generate_dockerfile()
        dockerfile_path = package_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile)
        results["artifacts"].append("Dockerfile")
        
        # 2. Generate docker-compose.yml
        compose = self._generate_docker_compose()
        compose_path = package_dir / "docker-compose.yml"
        compose_path.write_text(compose)
        results["artifacts"].append("docker-compose.yml")
        
        # 3. Generate Binder config
        binder_dir = package_dir / "binder"
        binder_dir.mkdir(exist_ok=True)
        self._generate_binder_config(binder_dir)
        results["artifacts"].append("binder/")
        
        # 4. Generate README
        readme = self._generate_package_readme()
        readme_path = package_dir / "README.md"
        readme_path.write_text(readme)
        results["artifacts"].append("README.md")
        
        # 4. Copy project files
        self._copy_project_files(package_dir)
        results["artifacts"].append("project_files/")
        
        # 5. Build Docker image (optional)
        # This would be done by user after package is generated
        
        return {
            "success": True,
            "package_dir": str(package_dir),
            "artifacts": results["artifacts"],
            "instructions": self._get_package_instructions(package_dir)
        }
    
    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for executable package"""
        return f"""# Research Package Dockerfile
# Generated by Quarto Bridge on {datetime.now().isoformat()}

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    build-essential \\
    libglib2.0-0 \\
    libsm6 \\
    libxext6 \\
    libxrender-dev \\
    libgl1-mesa-glx \\
    && rm -rf /var/lib/apt/lists/*

# Install Quarto
ARG QUARTO_VERSION=1.4.550
RUN curl -L -o quarto.deb https://github.com/quarto-dev/quarto-cli/releases/download/v${{QUARTO_VERSION}}/quarto-${{QUARTO_VERSION}}-linux-amd64.deb && \\
    dpkg -i quarto.deb && \\
    rm quarto.deb

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy project files
COPY . /workspace
WORKDIR /workspace

# Set environment
ENV PYTHONPATH=/workspace
ENV QUARTO_PROJECT_DIR=/workspace

# Default command
CMD ["bash"]
"""
    
    def _generate_docker_compose(self) -> str:
        """Generate docker-compose.yml"""
        return f"""version: '3.8'

services:
  research:
    build: .
    volumes:
      - ./outputs:/workspace/outputs
      - ./manuscript:/workspace/manuscript
      - ./data:/workspace/data
    environment:
      - PYTHONPATH=/workspace
    command: bash

  jupyter:
    build: .
    ports:
      - "8888:8888"
    volumes:
      - ./:/workspace
    command: jupyter lab --ip=0.0.0.0 --no-browser --allow-root
"""
    
    def _generate_binder_config(self, binder_dir: Path):
        """Generate Binder configuration files"""
        # apt.txt
        (binder_dir / "apt.txt").write_text("""# System packages for Binder
git
curl
""")
        
        # requirements.txt
        (binder_dir / "requirements.txt").write_text("""# Python dependencies for Binder
quarto-python
""")
        
        # postBuild
        (binder_dir / "postBuild").write_text("""#!/bin/bash
# Post-build setup for Binder
pip install -e .
""")
        (binder_dir / "postBuild").chmod(0o755)
    
    def _generate_package_readme(self) -> str:
        return f"""# Research Package: {self.config.get('project_name', 'Research Project')}

Generated on {datetime.now().isoformat()}

## Quick Start

### Docker
```bash
docker build -t research-package .
docker run -it --rm -v $(pwd)/outputs:/workspace/outputs research-package
```

### Docker Compose
```bash
docker-compose up research
# or for Jupyter:
docker-compose up jupyter
```

### Binder
Click the badge above or visit: https://mybinder.org/v2/gh/your-repo/main

## Structure

- `Dockerfile` - Container definition
- `docker-compose.yml` - Multi-service orchestration
- `binder/` - BinderHub configuration
- `manuscript/` - Quarto manuscript source
- `data/` - Research data (tracked with DVC)
- `scripts/` - Experiment and analysis scripts

## Commands

```bash
# Build manuscript
quarto render manuscript/index.qmd

# Run experiments
python scripts/run_experiment.py

# Run evaluation
python scripts/run_evaluation.py

# Build package
python scripts/build_package.py
```
"""
    
    def _copy_project_files(self, package_dir: Path):
        """Copy project files to package directory"""
        dirs_to_copy = ["manuscript", "data", "scripts", "configs", "docs"]
        for d in dirs_to_copy:
            src = self.project_root / d
            if src.exists():
                dst = package_dir / d
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    
    def _get_package_instructions(self, package_dir: Path) -> str:
        return f"""
## Package Generated: {package_dir.name}

### Quick Start
```bash
cd {package_dir}
docker build -t research-package .
docker run -it --rm -v $(pwd)/outputs:/workspace/outputs research-package
```

### For Development
```bash
docker-compose up research
# or for Jupyter Lab:
docker-compose up jupyter
```

### Binder
Push to GitHub and enable Binder, or use the binder/ directory directly.

### Local (without Docker)
```bash
pip install -r binder/requirements.txt
quarto render manuscript/index.qmd
```
"""

class QuartoManuscriptBuilder:
    """Helper for programmatic manuscript construction"""
    
    def __init__(self, manuscript_dir: Path):
        self.manuscript_dir = Path(manuscript_dir)
        self.sections = []
        self.metadata = {}
    
    def set_metadata(self, **kwargs):
        """Set manuscript metadata"""
        self.metadata.update(kwargs)
    
    def add_section(self, title: str, content: str, level: int = 1):
        """Add a section to the manuscript"""
        header = "#" * level + " " + title
        self.sections.append(f"{header}\n\n{content}\n")
    
    def add_figure(self, caption: str, path: str, label: str = None):
        """Add a figure reference"""
        label_str = f" {{#{label}}}" if label else ""
        self.sections.append(f"![{caption}]({path}){label_str}\n")
    
    def add_table(self, caption: str, data: List[List], headers: List = None, label: str = None):
        """Add a table"""
        if not data:
            return
        
        if headers:
            header_row = "| " + " | ".join(headers) + " |"
            sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        else:
            header_row = ""
            sep_row = ""
        
        rows = []
        for row in data:
            rows.append("| " + " | ".join(str(c) for c in row) + " |")
        
        label_str = f" {{#{label}}}" if label else ""
        table = f"\n{header_row}\n{sep_row}\n" + "\n".join(rows) + f"\n{label_str}\n"
        self.sections.append(table)
    
    def add_citation(self, key: str):
        """Add citation reference"""
        self.sections.append(f"[@{key}]")
    
    def build(self, output_path: Path = None) -> Path:
        """Build the complete manuscript QMD file"""
        if output_path is None:
            output_path = self.manuscript_dir / "index.qmd"
        
        # Build front matter
        front_matter = "---\n"
        for key, value in self.metadata.items():
            if isinstance(value, list):
                front_matter += f"{key}: {json.dumps(value)}\n"
            else:
                front_matter += f"{key}: {value}\n"
        front_matter += "---\n\n"
        
        # Build body
        body = "\n\n".join(self.sections)
        
        # Add references section
        body += "\n\n# References\n\n::: {{#refs}}\n:::\n"
        
        content = front_matter + "\n" + body
        Path(output_path).write_text(content)
        return output_path
    
    def render(self, format: str = "pdf", **kwargs) -> Dict[str, Any]:
        """Render manuscript via Quarto"""
        qmd_path = self.build()
        bridge = QuartoBridge({"project_root": str(self.manuscript_dir.parent)})
        return bridge.render(format=format, **kwargs)
