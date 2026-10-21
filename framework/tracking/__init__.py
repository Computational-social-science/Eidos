"""
Tracking Module
MLflow + DVC integration for experiment tracking and data versioning
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import shutil
import subprocess
import os
import sys
from datetime import datetime

# Heavy dependencies are optional extras. The framework core must import with
# stdlib + pyyaml alone; a project that wants tracking pays for mlflow/dvc and
# gets a clear error only when it actually uses them.
#
# Annotated Any on purpose: static analysers otherwise narrow the guarded
# import to None and flag every attribute access below, even though
# _require_mlflow() raises before any of them can run.
mlflow: Any = None
MlflowClient: Any = None
MLFLOW_AVAILABLE = False
try:
    mlflow = __import__("mlflow")
    __import__("mlflow.tracking")
    MlflowClient = mlflow.tracking.MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the host
    pass

DVC_AVAILABLE = False
try:
    __import__("dvc.api")
    DVC_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the host
    pass


def _require_mlflow():
    if not MLFLOW_AVAILABLE:
        raise ImportError(
            "mlflow is not installed. Install the tracking extra: "
            "pip install -e '.[tracking]'"
        )


def _require_dvc():
    if not DVC_AVAILABLE:
        raise ImportError(
            "dvc is not installed. Install the tracking extra: "
            "pip install -e '.[tracking]'"
        )


def dvc_cmd() -> List[str]:
    """Resolve the DVC entry point.

    `dvc` is often not on PATH even when the package is installed (user-site
    scripts directory on Windows), and a bare name then raises FileNotFoundError
    from inside `ExperimentTracker.__init__`, which made the whole tracking chain
    unusable. Fall back to the module form of the running interpreter.
    """
    found = shutil.which("dvc")
    return [found] if found else [sys.executable, "-m", "dvc"]

@dataclass
class ExperimentRun:
    """Represents a single experiment run"""
    run_id: str
    experiment_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    status: str = "running"  # running, completed, failed
    git_commit: Optional[str] = None

class ExperimentTracker:
    """
    MLflow + DVC experiment tracking wrapper.
    Provides unified interface for experiment tracking and data versioning.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        _require_mlflow()
        self.config = config or {}
        self.project_root = Path(self.config.get("project_root", ".")).resolve()
        self.mlflow_uri = self.config.get("mlflow_uri", f"sqlite:///{self.project_root}/mlruns.db")
        self.experiment_name = self.config.get("experiment_name", "default")
        self.dvc_remote = self.config.get("dvc_remote", "storage")
        
        # Initialize MLflow
        mlflow.set_tracking_uri(self.mlflow_uri)
        self.client = MlflowClient(tracking_uri=self.mlflow_uri)
        
        # Create or get experiment
        self.experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if self.experiment is None:
            self.experiment_id = mlflow.create_experiment(self.experiment_name)
        else:
            self.experiment_id = self.experiment.experiment_id
        
        mlflow.set_experiment(self.experiment_name)
        
        # Initialize DVC if not already
        self._init_dvc()
    
    def _init_dvc(self):
        """Initialize DVC in project root if not already initialized.

        A failure here must not disable MLflow: the run log is the primary record,
        and data versioning is an add-on that may legitimately be unavailable
        (dvc absent, directory not a git repo, ...). `dvc_available` records the
        outcome instead of raising out of the constructor.
        """
        self.dvc_available = False
        if not DVC_AVAILABLE:
            return
        dvc_dir = self.project_root / ".dvc"
        if dvc_dir.exists():
            self.dvc_available = True
            return
        try:
            subprocess.run(dvc_cmd() + ["init", "--no-scm"], cwd=self.project_root,
                           check=True, capture_output=True)
            if self.config.get("dvc_remote_url"):
                subprocess.run(
                    dvc_cmd() + ["remote", "add", "-d", self.dvc_remote,
                                 self.config["dvc_remote_url"]],
                    cwd=self.project_root, check=True, capture_output=True,
                )
            self.dvc_available = True
        except (OSError, subprocess.CalledProcessError) as exc:
            # OSError covers "the executable vanished between which() and run()";
            # CalledProcessError covers `dvc init` refusing (not a git repo).
            print(f"Warning: DVC init failed ({type(exc).__name__}); "
                  f"data versioning is unavailable for this tracker")
    
    def start_run(self, run_name: str = None, tags: Dict[str, str] = None) -> ExperimentRun:
        """Start a new MLflow run"""
        mlflow_run = mlflow.start_run(
            run_name=run_name,
            experiment_id=self.experiment_id,
            tags=tags or {}
        )
        
        # Get git commit
        git_commit = None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root, capture_output=True, text=True
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except Exception:
            pass
        
        run = ExperimentRun(
            run_id=mlflow_run.info.run_id,
            experiment_name=self.experiment_name,
            tags=tags or {},
            git_commit=git_commit
        )
        return run
    
    def end_run(self, run: ExperimentRun, status: str = "completed"):
        """End an MLflow run"""
        run.end_time = datetime.now().isoformat()
        run.status = status
        mlflow.end_run(status="FINISHED" if status == "completed" else "FAILED")
    
    def log_params(self, run: ExperimentRun, params: Dict[str, Any]):
        """Log parameters to MLflow"""
        mlflow.log_params(params)
        run.params.update(params)
    
    def log_metrics(self, run: ExperimentRun, metrics: Dict[str, float], step: int = None):
        """Log metrics to MLflow"""
        for key, value in metrics.items():
            mlflow.log_metric(key, value, step=step)
        run.metrics.update(metrics)
    
    def log_artifact(self, run: ExperimentRun, local_path: Path, artifact_path: str = None):
        """Log artifact to MLflow"""
        mlflow.log_artifact(str(local_path), artifact_path)
        if str(local_path) not in run.artifacts:
            run.artifacts.append(str(local_path))
    
    def log_artifacts(self, run: ExperimentRun, local_dir: Path, artifact_path: str = None):
        """Log directory of artifacts"""
        mlflow.log_artifacts(str(local_dir), artifact_path)
        for f in Path(local_dir).rglob("*"):
            if f.is_file():
                run.artifacts.append(str(f))
    
    def log_model(self, run: ExperimentRun, model, artifact_path: str = "model", **kwargs):
        """Log MLflow model"""
        mlflow.sklearn.log_model(model, artifact_path, **kwargs)
        run.artifacts.append(f"{artifact_path}/model.pkl")
    
    def add_tags(self, run: ExperimentRun, tags: Dict[str, str]):
        """Add tags to current run"""
        mlflow.set_tags(tags)
        run.tags.update(tags)
    
    def get_run(self, run_id: str) -> ExperimentRun:
        """Get run by ID"""
        mlflow_run = self.client.get_run(run_id)
        return ExperimentRun(
            run_id=mlflow_run.info.run_id,
            experiment_name=self.experiment_name,
            params=mlflow_run.data.params,
            metrics=mlflow_run.data.metrics,
            tags=mlflow_run.data.tags,
            start_time=datetime.fromtimestamp(mlflow_run.info.start_time / 1000).isoformat(),
            end_time=datetime.fromtimestamp(mlflow_run.info.end_time / 1000).isoformat() if mlflow_run.info.end_time else None,
            status=mlflow_run.info.status
        )
    
    def search_runs(self, filter_string: str = "", max_results: int = 100) -> List[ExperimentRun]:
        """Search runs with filter"""
        runs = self.client.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=filter_string,
            max_results=max_results
        )
        return [ExperimentRun(
            run_id=r.info.run_id,
            experiment_name=self.experiment_name,
            params=r.data.params,
            metrics=r.data.metrics,
            tags=r.data.tags,
            start_time=datetime.fromtimestamp(r.info.start_time / 1000).isoformat(),
            end_time=datetime.fromtimestamp(r.info.end_time / 1000).isoformat() if r.info.end_time else None,
            status=r.info.status
        ) for r in runs]
    
    def log_dataset(self, run: ExperimentRun, data_path: Path, name: str = "dataset"):
        """Log dataset with DVC tracking"""
        # Add to DVC
        rel_path = Path(data_path).relative_to(self.project_root)
        subprocess.run(dvc_cmd() + ["add", str(rel_path)], cwd=self.project_root, check=True)
        
        # Log to MLflow
        mlflow.log_artifact(str(data_path), f"datasets/{name}")
        run.artifacts.append(f"datasets/{name}/{rel_path.name}")
        
        # Also log DVC file
        dvc_file = Path(str(data_path) + ".dvc")
        if dvc_file.exists():
            mlflow.log_artifact(str(dvc_file), f"datasets/{name}")
    
    def push_data(self):
        """Push DVC data to remote"""
        subprocess.run(dvc_cmd() + ["push"], cwd=self.project_root, check=True)
    
    def pull_data(self):
        """Pull DVC data from remote"""
        subprocess.run(dvc_cmd() + ["pull"], cwd=self.project_root, check=True)
    
    def get_data_url(self, data_path: Path) -> str:
        """Get DVC remote URL for data file"""
        rel_path = Path(data_path).relative_to(self.project_root)
        result = subprocess.run(
            dvc_cmd() + ["remote", "get-url", self.dvc_remote],
            cwd=self.project_root, capture_output=True, text=True, check=True
        )
        remote_url = result.stdout.strip()
        return f"{remote_url}/{rel_path}"

class DVCDataVersioner:
    """DVC data versioning wrapper"""
    
    def __init__(self, project_root: Path = None, remote: str = "storage"):
        self.project_root = Path(project_root or ".").resolve()
        self.remote = remote
    
    def add(self, path: Path) -> Path:
        """Add file/directory to DVC tracking"""
        rel_path = path.relative_to(self.project_root)
        subprocess.run(dvc_cmd() + ["add", str(rel_path)], cwd=self.project_root, check=True)
        return self.project_root / f"{rel_path}.dvc"
    
    def remove(self, path: Path) -> None:
        """Remove file/directory from DVC tracking"""
        rel_path = path.relative_to(self.project_root)
        subprocess.run(dvc_cmd() + ["remove", str(rel_path)], cwd=self.project_root, check=True)
        # Remove .dvc file
        dvc_file = self.project_root / f"{path}.dvc"
        if dvc_file.exists():
            dvc_file.unlink()
    
    def push(self) -> None:
        """Push all tracked data to remote"""
        subprocess.run(dvc_cmd() + ["push"], cwd=self.project_root, check=True)
    
    def pull(self) -> None:
        """Pull all data from remote"""
        subprocess.run(dvc_cmd() + ["pull"], cwd=self.project_root, check=True)
    
    def status(self) -> List[str]:
        """Get DVC status"""
        result = subprocess.run(
            dvc_cmd() + ["status"], cwd=self.project_root, 
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    
    def get_file_hash(self, path: Path) -> str:
        """Get DVC hash for a file"""
        rel_path = path.relative_to(self.project_root)
        result = subprocess.run(
            dvc_cmd() + ["status", "-c", str(rel_path)],
            cwd=self.project_root, capture_output=True, text=True, check=True
        )
        # Parse hash from output
        for line in result.stdout.split('\n'):
            if 'changed' in line.lower() or 'not in cache' in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
        return ""
    
    def get_pipeline_stages(self) -> List[Dict]:
        """Get DVC pipeline stages"""
        dvc_file = self.project_root / "dvc.yaml"
        if not dvc_file.exists():
            return []
        import yaml
        with open(dvc_file) as f:
            data = yaml.safe_load(f)
        return data.get("stages", [])

class ExperimentRegistry:
    """Registry of experiment templates for reproducible runs"""
    
    def __init__(self, tracker: ExperimentTracker):
        self.tracker = tracker
        self.templates: Dict[str, Dict] = {}
    
    def register_template(self, name: str, config: Dict):
        """Register an experiment template"""
        self.templates[name] = config
    
    def run_from_template(self, template_name: str, overrides: Dict = None) -> ExperimentRun:
        """Run experiment from template"""
        if template_name not in self.templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        config = self.templates[template_name].copy()
        if overrides:
            config.update(overrides)
        
        # Start run with template config
        run = self.tracker.start_run(
            run_name=f"{template_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags={"template": template_name}
        )
        
        # Log template parameters
        self.tracker.log_params(run, config.get("params", {}))
        
        return run
    
    def save_template(self, name: str, path: Path):
        """Save template to file"""
        if name in self.templates:
            path.write_text(json.dumps(self.templates[name], indent=2))
    
    def load_template(self, name: str, path: Path):
        """Load template from file"""
        self.templates[name] = json.loads(path.read_text())

# Convenience functions
def start_experiment(experiment_name: str = "default", run_name: str = None, 
                     config: Dict = None) -> ExperimentRun:
    """Quick start an experiment"""
    tracker = ExperimentTracker(config or {"experiment_name": experiment_name})
    return tracker.start_run(run_name)

def log_params(run: ExperimentRun, params: Dict):
    tracker = ExperimentTracker()
    tracker.log_params(run, params)

def log_metrics(run: ExperimentRun, metrics: Dict[str, float], step: int = None):
    tracker = ExperimentTracker()
    tracker.log_metrics(run, metrics, step)

def end_experiment(run: ExperimentRun, status: str = "completed"):
    tracker = ExperimentTracker()
    tracker.end_run(run, status)