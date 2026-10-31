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
        """Export an explicitly declared delivery; generation does not verify execution."""
        from framework.executable_package import build
        name = output_name or f"research_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return build(self.project_root, self.output_dir, name, self.config.get('executable_package'))


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
