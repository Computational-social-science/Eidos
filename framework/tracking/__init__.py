"""
Tracking Module
MLflow + DVC integration for experiment tracking and data versioning
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, ClassVar
from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path
import copy
import hashlib
import json
import math
from numbers import Integral, Real
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote, urlsplit
from datetime import datetime

from framework.artifacts import atomic_output, output_lock
from framework.subprocesses import run_tree, validate_timeout

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
    tracking_uri: Optional[str] = None
    experiment_id: Optional[str] = None
    _owner: ClassVar[Any] = None

    def __getstate__(self):
        return {key: value for key, value in self.__dict__.items() if key != "_owner"}

    def __setstate__(self, state):
        self.__dict__.update(state)


class TrackingOperationError(RuntimeError):
    """An external operation failed; captured streams remain available for diagnosis."""

    def __init__(self, operation, returncode, stdout="", stderr=""):
        super().__init__(f"{operation} failed with exit code {returncode}")
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate tracking response field")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite tracking response")

    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def _load_yaml(body):
    import yaml

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                raise ValueError("duplicate YAML field")
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    UniqueLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping
    )
    return yaml.load(body, Loader=UniqueLoader)


def _project_path(root, path):
    target = Path(path)
    target = (root / target if not target.is_absolute() else target).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("data path must stay inside the project") from exc
    if relative == Path("."):
        raise ValueError("the project root is not a data target")
    return target, relative


def _store_uri(value, root):
    """Resolve local locators once so callers and workers open the same store."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("tracking and registry URIs must be nonempty strings")
    if value in {"databricks", "databricks-uc"}:
        return value
    if urlsplit(value).scheme.split("+", 1)[0] == "sqlite":
        from sqlalchemy.engine import make_url

        url = make_url(value)
        if url.database in (None, "", ":memory:"):
            raise ValueError("tracking requires a shareable on-disk SQLite database")
        if url.database not in (None, "", ":memory:"):
            if url.database.startswith("file:"):
                raise ValueError(
                    "SQLite file: query URIs are unsupported; use an ordinary database path"
                )
            database = Path(url.database)
            if not database.is_absolute():
                database = root / database
            url = url.set(database=database.resolve().as_posix())
        return url.render_as_string(hide_password=False)
    parsed = urlsplit(value)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc != "localhost":
            path = Path("//" + parsed.netloc + unquote(parsed.path))
        else:
            raw = unquote(parsed.path)
            if os.name == "nt" and len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
                raw = raw[1:]
            path = Path(raw)
        return (path if path.is_absolute() else root / path).resolve().as_uri()
    if not parsed.scheme or Path(value).is_absolute():
        path = Path(value)
        return (path if path.is_absolute() else root / path).resolve().as_uri()
    return value


def _run_lock_path(uri, run_id):
    if urlsplit(uri).scheme.split("+", 1)[0] == "sqlite":
        from sqlalchemy.engine import make_url

        identity = "sqlite:" + os.path.normcase(make_url(uri).database or ":memory:")
    else:
        identity = uri
    digest = hashlib.sha256((identity + "\0" + run_id).encode("utf-8")).hexdigest()
    return Path.home() / ".cache/eidos-tracking-locks" / digest


def _code_fingerprints():
    return {
        path.name: hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
        for path in (Path(__file__), Path(__file__).with_name("_worker.py"))
    }


def _operation(root, operation, timeout, **arguments):
    """Run dependency-specific work without changing the caller's global state."""
    before = _code_fingerprints()
    with tempfile.TemporaryDirectory(prefix="eidos-tracking-operation-") as temporary:
        directory = Path(temporary)
        request = directory / "request.json"
        response = directory / "response.json"
        payload = {"operation": operation, "project_root": str(root), **arguments}
        request.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
        worker = Path(__file__).with_name("_worker.py")
        result = run_tree(
            [
                sys.executable,
                "-I",
                "-X",
                "utf8",
                str(worker),
                str(request),
                str(response),
            ],
            cwd=root,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise TrackingOperationError(
                operation, result.returncode, result.stdout, result.stderr
            )
        if _code_fingerprints() != before:
            raise ValueError("tracking source changed during the operation")
        record = _strict_json(response.read_text(encoding="utf-8"))
        if (
            not isinstance(record, dict)
            or set(record) != {"kind", "operation", "result"}
            or record["kind"] != "eidos.tracking.operation"
            or record["operation"] != operation
        ):
            raise ValueError("invalid tracking operation response")
        return record["result"]


class ExperimentTracker:
    """MLflow operations bound to one store, experiment and explicit run identity.

    This wrapper never changes the caller's fluent tracking URI or active run.
    DVC and model operations own bounded, quiet subprocesses. Optional DVC init
    preserves MLflow availability; an attempted data operation still fails clearly
    if DVC initialization did not succeed.
    """

    def __init__(self, config: Dict[str, Any] = None):
        _require_mlflow()
        self.config = copy.deepcopy(config or {})
        self.project_root = Path(self.config.get("project_root", ".")).resolve()
        if not self.project_root.is_dir():
            raise ValueError("project_root must be an existing directory")
        self.mlflow_uri = _store_uri(
            self.config.get(
                "mlflow_uri",
                f'sqlite:///{(self.project_root / "mlruns.db").as_posix()}',
            ),
            self.project_root,
        )
        self.registry_uri = _store_uri(
            self.config.get("registry_uri", self.mlflow_uri), self.project_root
        )
        self.experiment_name = self.config.get("experiment_name", "default")
        if (
            not isinstance(self.experiment_name, str)
            or not self.experiment_name.strip()
        ):
            raise ValueError("experiment_name must be a nonempty string")
        self.dvc_remote = self.config.get("dvc_remote", "storage")
        self.dvc_timeout = self.config.get("dvc_timeout_s", 120)
        self.model_timeout = self.config.get("model_timeout_s", 300)
        self.git_timeout = self.config.get("git_timeout_s", 10)
        self.lock_timeout = self.config.get("tracking_lock_timeout_s", 120)
        for timeout in (
            self.dvc_timeout,
            self.model_timeout,
            self.git_timeout,
            self.lock_timeout,
        ):
            validate_timeout(timeout)
        if type(self.config.get("enable_dvc", True)) is not bool:
            raise ValueError("enable_dvc must be boolean")
        self._lock = threading.RLock()
        self.client = MlflowClient(
            tracking_uri=self.mlflow_uri, registry_uri=self.registry_uri
        )
        self.experiment = self.client.get_experiment_by_name(self.experiment_name)
        if self.experiment is None:
            from mlflow.exceptions import MlflowException

            try:
                self.experiment_id = self.client.create_experiment(
                    self.experiment_name,
                    artifact_location=self.config.get(
                        "artifact_location",
                        (self.project_root / "mlartifacts").as_uri(),
                    ),
                )
            except MlflowException as exc:
                if exc.error_code != "RESOURCE_ALREADY_EXISTS":
                    raise
                self.experiment = self.client.get_experiment_by_name(
                    self.experiment_name
                )
                if self.experiment is None:
                    raise
                self.experiment_id = self.experiment.experiment_id
        else:
            self.experiment_id = self.experiment.experiment_id
        self._init_dvc()

    def _versioner(self):
        return DVCDataVersioner(
            self.project_root, self.dvc_remote, timeout_s=self.dvc_timeout
        )

    def _init_dvc(self):
        self.dvc_available = False
        self.dvc_error = None
        enabled = self.config.get("enable_dvc", True)
        if type(enabled) is not bool:
            raise ValueError("enable_dvc must be boolean")
        if not enabled or not DVC_AVAILABLE:
            return
        try:
            versioner = self._versioner()
            if not (self.project_root / ".dvc").is_dir():
                versioner._command("init", "--no-scm")
            if self.config.get("dvc_remote_url"):
                versioner._command(
                    "remote",
                    "add",
                    "-f",
                    "-d",
                    self.dvc_remote,
                    self.config["dvc_remote_url"],
                )
            self.dvc_available = True
        except (OSError, TrackingOperationError, subprocess.TimeoutExpired) as exc:
            self.dvc_error = type(exc).__name__
            print(
                "Warning: DVC initialization failed; MLflow remains available. "
                "Inspect tracker.dvc_error before requesting data operations."
            )

    def _data_versioner(self):
        if not self.dvc_available:
            raise RuntimeError("DVC is unavailable or disabled for this tracker")
        return self._versioner()

    def _bound(self, run):
        if not isinstance(run, ExperimentRun) or not run.run_id:
            raise ValueError("an explicit ExperimentRun is required")
        if run.tracking_uri is not None and run.tracking_uri != self.mlflow_uri:
            raise ValueError("run belongs to another tracking store")
        if run.experiment_id is not None and run.experiment_id != self.experiment_id:
            raise ValueError("run belongs to another experiment")
        record = self.client.get_run(run.run_id)
        if record.info.experiment_id != self.experiment_id:
            raise ValueError("run belongs to another experiment")
        return record

    @contextmanager
    def _ownership(self, run):
        if (
            not isinstance(run, ExperimentRun)
            or not isinstance(run.run_id, str)
            or not run.run_id
        ):
            raise ValueError("an explicit ExperimentRun is required")
        with (
            output_lock(
                _run_lock_path(self.mlflow_uri, run.run_id), timeout=self.lock_timeout
            ),
            self._lock,
        ):
            yield

    @contextmanager
    def _writing(self, run):
        with self._ownership(run):
            record = self._bound(run)
            if record.info.status != "RUNNING":
                raise ValueError("run is terminal; writes require a running run")
            yield record

    def _from_record(self, record):
        statuses = {
            "RUNNING": "running",
            "FINISHED": "completed",
            "FAILED": "failed",
            "KILLED": "killed",
            "SCHEDULED": "scheduled",
        }
        info, data = record.info, record.data
        run = ExperimentRun(
            run_id=info.run_id,
            experiment_name=self.experiment_name,
            params=dict(data.params),
            metrics=dict(data.metrics),
            tags=dict(data.tags),
            start_time=datetime.fromtimestamp(info.start_time / 1000).isoformat(),
            end_time=(
                datetime.fromtimestamp(info.end_time / 1000).isoformat()
                if info.end_time is not None
                else None
            ),
            status=statuses.get(info.status, info.status.lower()),
            git_commit=data.tags.get("eidos.git_commit"),
            tracking_uri=self.mlflow_uri,
            experiment_id=self.experiment_id,
        )
        run._owner = self
        return run

    def start_run(
        self, run_name: str = None, tags: Dict[str, str] = None
    ) -> ExperimentRun:
        values = dict(tags or {})
        # Git failure is explicit missing provenance, not a reason to borrow ambient state.
        try:
            result = run_tree(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                timeout=self.git_timeout,
            )
            commit = result.stdout.strip()
            if (
                result.returncode == 0
                and len(commit) in (40, 64)
                and all(character in "0123456789abcdef" for character in commit)
            ):
                values["eidos.git_commit"] = commit
            else:
                values.pop("eidos.git_commit", None)
        except (OSError, subprocess.TimeoutExpired):
            values.pop("eidos.git_commit", None)
        record = self.client.create_run(
            self.experiment_id, run_name=run_name, tags=values
        )
        return self._from_record(record)

    def end_run(self, run: ExperimentRun, status: str = "completed"):
        statuses = {"completed": "FINISHED", "failed": "FAILED", "killed": "KILLED"}
        if status not in statuses:
            raise ValueError("status must be completed, failed or killed")
        with self._ownership(run):
            record = self._bound(run)
            target = statuses[status]
            if record.info.status == "RUNNING":
                self.client.set_terminated(run.run_id, status=target)
                record = self.client.get_run(run.run_id)
            elif record.info.status != target:
                raise ValueError("terminal run status cannot be replaced")
            run.status = status
            run.end_time = datetime.fromtimestamp(
                record.info.end_time / 1000
            ).isoformat()

    def log_params(self, run: ExperimentRun, params: Dict[str, Any]):
        from mlflow.entities import Param

        entities = [Param(key, str(value)) for key, value in params.items()]
        with self._writing(run):
            self.client.log_batch(run.run_id, params=entities, synchronous=True)
            run.params.update(params)

    def log_metrics(
        self, run: ExperimentRun, metrics: Dict[str, float], step: int = None
    ):
        from mlflow.entities import Metric

        if step is not None and (
            isinstance(step, bool) or not isinstance(step, Integral) or step < 0
        ):
            raise ValueError("metric step must be a nonnegative integer")
        values = {}
        for key, value in metrics.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
            ):
                raise ValueError("metrics must contain finite real numbers")
            values[key] = float(value)
        timestamp = int(time.time() * 1000)
        entities = [
            Metric(key, value, timestamp, int(step or 0))
            for key, value in values.items()
        ]
        with self._writing(run):
            self.client.log_batch(run.run_id, metrics=entities, synchronous=True)
            run.metrics.update(values)

    def log_artifact(
        self, run: ExperimentRun, local_path: Path, artifact_path: str = None
    ):
        target = Path(local_path).resolve()
        if not target.is_file():
            raise ValueError("artifact must be an existing file")
        with self._writing(run):
            self.client.log_artifact(run.run_id, str(target), artifact_path)
            if str(target) not in run.artifacts:
                run.artifacts.append(str(target))

    def log_artifacts(
        self, run: ExperimentRun, local_dir: Path, artifact_path: str = None
    ):
        target = Path(local_dir).resolve()
        if not target.is_dir():
            raise ValueError("artifact directory must exist")
        with self._writing(run):
            self.client.log_artifacts(run.run_id, str(target), artifact_path)
            run.artifacts.extend(
                str(path)
                for path in target.rglob("*")
                if path.is_file() and str(path) not in run.artifacts
            )

    def log_model(
        self, run: ExperimentRun, model, artifact_path: str = "model", **kwargs
    ):
        """Log a loadable sklearn model in an isolated MLflow context; return its locator."""
        if "run_id" in kwargs:
            raise ValueError("log_model run_id comes from the explicit run")
        import cloudpickle

        with (
            self._writing(run),
            tempfile.TemporaryDirectory(prefix="eidos-model-input-") as temporary,
        ):
            payload = Path(temporary) / "model.pkl"
            with payload.open("wb") as handle:
                cloudpickle.dump({"model": model, "kwargs": kwargs}, handle)
            result = _operation(
                self.project_root,
                "model",
                self.model_timeout,
                tracking_uri=self.mlflow_uri,
                registry_uri=self.registry_uri,
                experiment_id=self.experiment_id,
                run_id=run.run_id,
                artifact_path=(
                    None
                    if "name" in kwargs and artifact_path == "model"
                    else artifact_path
                ),
                module_paths=[
                    str((self.project_root / Path(path)).resolve())
                    for path in (kwargs.get("code_paths") or [])
                ],
                payload=str(payload),
            )
            if (
                not isinstance(result, dict)
                or result.get("run_id") != run.run_id
                or result.get("tracking_uri") != self.mlflow_uri
                or not isinstance(result.get("model_uri"), str)
                or not result["model_uri"]
            ):
                raise ValueError("model receipt does not match the requested run")
            run.artifacts.append(result["model_uri"])
            return result

    def download_model(
        self, run: ExperimentRun, model_id: str, destination: Path
    ) -> Path:
        """Download a model through its originating store without changing fluent state.

        Completed runs are readable. The destination must be empty; failed
        downloads remain incomplete and are never returned as a qualified model.
        """
        target = Path(destination).resolve()
        with self._ownership(run):
            self._bound(run)
            model = self.client.get_logged_model(model_id)
            if (
                model.source_run_id != run.run_id
                or model.experiment_id != self.experiment_id
            ):
                raise ValueError("model belongs to another run or experiment")
            with self._download_target(target, model.artifact_location):
                return self._download_into(run, model_id, target)

    @contextmanager
    def _download_target(self, target, artifact_uri):
        from mlflow.utils.uri import is_local_uri
        from mlflow.utils.file_utils import local_file_uri_to_path

        if is_local_uri(artifact_uri):
            source = Path(local_file_uri_to_path(artifact_uri)).resolve()
            if target.is_relative_to(source) or source.is_relative_to(target):
                raise ValueError(
                    "download destination overlaps the source model artifacts"
                )
        with output_lock(target, timeout=self.lock_timeout):
            if target.exists() and (not target.is_dir() or any(target.iterdir())):
                raise ValueError(
                    "model download destination must be an empty directory"
                )
            target.mkdir(parents=True, exist_ok=True)
            yield

    def _download_into(self, run, model_id, target):
        result = _operation(
            self.project_root,
            "model_download",
            self.model_timeout,
            tracking_uri=self.mlflow_uri,
            registry_uri=self.registry_uri,
            experiment_id=self.experiment_id,
            run_id=run.run_id,
            model_id=model_id,
            destination=str(target),
        )
        if (
            not isinstance(result, dict)
            or result.get("run_id") != run.run_id
            or result.get("model_id") != model_id
            or not isinstance(result.get("path"), str)
        ):
            raise ValueError("download receipt does not match the requested model")
        downloaded = Path(result["path"]).resolve()
        if (
            not downloaded.is_relative_to(target)
            or not (downloaded / "MLmodel").is_file()
        ):
            raise ValueError(
                "model download did not produce the declared model directory"
            )
        return downloaded

    def add_tags(self, run: ExperimentRun, tags: Dict[str, str]):
        from mlflow.entities import RunTag

        values = {key: str(value) for key, value in tags.items()}
        if "eidos.git_commit" in values:
            raise ValueError("git provenance is recorded at run creation")
        with self._writing(run):
            self.client.log_batch(
                run.run_id,
                tags=[RunTag(key, value) for key, value in values.items()],
                synchronous=True,
            )
            run.tags.update(values)

    def get_run(self, run_id: str) -> ExperimentRun:
        run = self._from_record(self.client.get_run(run_id))
        self._bound(run)
        return run

    def search_runs(
        self, filter_string: str = "", max_results: int = 100
    ) -> List[ExperimentRun]:
        return [
            self._from_record(record)
            for record in self.client.search_runs(
                experiment_ids=[self.experiment_id],
                filter_string=filter_string,
                max_results=max_results,
            )
        ]

    def log_dataset(self, run: ExperimentRun, data_path: Path, name: str = "dataset"):
        """Track a file and upload the exact bytes whose DVC checksum was verified."""
        source, relative = _project_path(self.project_root, data_path)
        if (
            not isinstance(name, str)
            or not name
            or "\\" in name
            or "\0" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
        ):
            raise ValueError("dataset name must be a relative artifact name")
        if not source.is_file():
            raise ValueError(
                "log_dataset requires an existing file; use DVCDataVersioner for directories"
            )
        with (
            self._writing(run),
            tempfile.TemporaryDirectory(prefix="eidos-dataset-input-") as temporary,
        ):
            versioner = self._data_versioner()
            metadata = versioner.add(source)
            tracked_hash = versioner.get_file_hash(source)
            staged = Path(temporary) / source.name
            shutil.copyfile(source, staged)
            with staged.open("rb") as handle:
                actual_hash = hashlib.file_digest(handle, "md5").hexdigest()
            if actual_hash != tracked_hash:
                raise ValueError(
                    "data changed between DVC tracking and artifact staging"
                )
            staged_metadata = Path(temporary) / metadata.name
            _project_path(self.project_root, metadata)
            shutil.copyfile(metadata, staged_metadata)
            document = _load_yaml(staged_metadata.read_text(encoding="utf-8"))
            outputs = document.get("outs") if isinstance(document, dict) else None
            if (
                not isinstance(outputs, list)
                or len(outputs) != 1
                or not isinstance(outputs[0], dict)
            ):
                raise ValueError(
                    "DVC metadata must describe exactly the staged dataset"
                )
            output = outputs[0]
            if (
                output.get("md5") != tracked_hash
                or output.get("hash", "md5") != "md5"
                or type(output.get("size")) is not int
                or output["size"] != staged.stat().st_size
                or not isinstance(output.get("path"), str)
                or (metadata.parent / output["path"]).resolve() != source
            ):
                raise ValueError(
                    "staged DVC metadata does not match the staged dataset"
                )
            with staged.open("rb") as handle:
                content_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
            metadata_sha256 = hashlib.sha256(staged_metadata.read_bytes()).hexdigest()
            self.client.log_artifact(run.run_id, str(staged), f"datasets/{name}")
            self.client.log_artifact(
                run.run_id, str(staged_metadata), f"datasets/{name}"
            )
            location = f"datasets/{name}/{relative.name}"
            receipt = {
                "artifact": location,
                "dvc_md5": tracked_hash,
                "data_sha256": content_sha256,
                "dvc_file_sha256": metadata_sha256,
                "run_id": run.run_id,
                "experiment_id": self.experiment_id,
                "source_path": relative.as_posix(),
            }
            receipt_path = f"eidos-data-provenance/{name}.json"
            self.client.log_dict(run.run_id, receipt, receipt_path)
            run.artifacts.append(location)
            run.artifacts.append(receipt_path)
            return {**receipt, "receipt_artifact": receipt_path}

    def push_data(self):
        self._data_versioner().push()

    def pull_data(self):
        self._data_versioner().pull()

    def get_data_url(self, data_path: Path) -> str:
        return self._data_versioner().get_data_url(data_path)


class DVCDataVersioner:
    """Project-relative, bounded DVC operations; hashes describe registered data."""

    def __init__(
        self, project_root: Path = None, remote: str = "storage", *, timeout_s=120
    ):
        self.project_root = Path(project_root or ".").resolve()
        self.remote = remote
        validate_timeout(timeout_s)
        self.timeout = timeout_s
        if not self.project_root.is_dir():
            raise ValueError("project_root must be an existing directory")

    def _command(self, *arguments):
        result = run_tree(
            [*dvc_cmd(), *arguments], cwd=self.project_root, timeout=self.timeout
        )
        if result.returncode != 0:
            raise TrackingOperationError(
                "DVC " + arguments[0], result.returncode, result.stdout, result.stderr
            )
        return result

    def add(self, path: Path) -> Path:
        target, relative = _project_path(self.project_root, path)
        self._command("add", "--", str(relative))
        metadata = Path(str(target) + ".dvc")
        if not metadata.is_file():
            raise ValueError("DVC add did not produce the declared tracking file")
        return metadata

    def remove(self, path: Path) -> None:
        target, relative = _project_path(self.project_root, path)
        metadata = (
            relative if relative.suffix == ".dvc" else Path(str(relative) + ".dvc")
        )
        self._command("remove", "--", str(metadata))

    def push(self) -> None:
        self._command("push", "--remote=" + self.remote)

    def pull(self) -> None:
        self._command("pull", "--remote=" + self.remote)

    def status(self) -> List[str]:
        return self._command("status").stdout.strip().splitlines()

    def get_file_hash(self, path: Path, *, require_clean: bool = True) -> str:
        """Return the registered DVC MD5; refuse changed workspace data by default.

        A file is independently hashed. Directory checks use DVC's workspace
        status and ignore semantics; this is not an adversarial filesystem snapshot.
        Setting require_clean=False explicitly requests the recorded version.
        """
        _require_dvc()
        if type(require_clean) is not bool:
            raise ValueError("require_clean must be boolean")
        _, relative = _project_path(self.project_root, path)
        if require_clean:
            status = _strict_json(
                self._command(
                    "status", "--json", "--no-updates", "--", str(relative)
                ).stdout
            )
            if not isinstance(status, dict) or status:
                raise ValueError("DVC data is changed or its cache is unavailable")
        value = _operation(
            self.project_root,
            "dvc_hash",
            self.timeout,
            path=relative.as_posix(),
            require_clean=require_clean,
        )
        import re

        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9a-f]{32}(?:\.dir)?", value
        ):
            raise ValueError("DVC did not return a registered MD5 checksum")
        return value

    def get_data_url(self, path: Path) -> str:
        """Return DVC's content-addressed locator; this does not prove remote existence."""
        _require_dvc()
        _, relative = _project_path(self.project_root, path)
        value = _operation(
            self.project_root,
            "dvc_url",
            self.timeout,
            path=relative.as_posix(),
            remote=self.remote,
        )
        if not isinstance(value, str) or not value.strip():
            raise ValueError("DVC did not return a data locator")
        return value

    def get_pipeline_stages(self) -> List[Dict]:
        path = self.project_root / "dvc.yaml"
        if not path.exists():
            return []
        data = _load_yaml(path.read_text(encoding="utf-8"))
        if data is None:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("stages", {}), dict):
            raise ValueError("dvc.yaml stages must be a mapping")
        result = []
        for name, specification in data.get("stages", {}).items():
            if not isinstance(name, str) or not isinstance(specification, dict):
                raise ValueError("each DVC stage must have a name and mapping")
            result.append({**specification, "name": name})
        return result


class ExperimentRegistry:
    """Registry of experiment templates for reproducible runs"""

    def __init__(self, tracker: ExperimentTracker):
        self.tracker = tracker
        self.templates: Dict[str, Dict] = {}

    def register_template(self, name: str, config: Dict):
        """Register an experiment template"""
        self.templates[name] = copy.deepcopy(config)

    def run_from_template(
        self, template_name: str, overrides: Dict = None
    ) -> ExperimentRun:
        """Run experiment from template"""
        if template_name not in self.templates:
            raise ValueError(f"Unknown template: {template_name}")

        config = copy.deepcopy(self.templates[template_name])
        if overrides:
            config.update(copy.deepcopy(overrides))

        # Start run with template config
        run = self.tracker.start_run(
            run_name=f"{template_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags={"template": template_name},
        )

        # Log template parameters
        self.tracker.log_params(run, config.get("params", {}))

        return run

    def save_template(self, name: str, path: Path):
        """Save template to file"""
        if name not in self.templates:
            raise ValueError(f"Unknown template: {name}")
        with atomic_output(Path(path)) as temporary:
            temporary.write_text(
                json.dumps(self.templates[name], indent=2, allow_nan=False),
                encoding="utf-8",
            )

    def load_template(self, name: str, path: Path):
        """Load template from file"""
        value = _strict_json(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("experiment template must be a mapping")
        self.templates[name] = value


# Convenience functions
def start_experiment(
    experiment_name: str = "default", run_name: str = None, config: Dict = None
) -> ExperimentRun:
    """Quick start an experiment"""
    settings = dict(config or {})
    settings.setdefault("experiment_name", experiment_name)
    tracker = ExperimentTracker(settings)
    return tracker.start_run(run_name)


def _origin(run):
    if not isinstance(run, ExperimentRun) or not isinstance(
        run._owner, ExperimentTracker
    ):
        raise ValueError(
            "run has no originating tracker; use tracker.get_run to bind it"
        )
    return run._owner


def log_params(run: ExperimentRun, params: Dict):
    _origin(run).log_params(run, params)


def log_metrics(run: ExperimentRun, metrics: Dict[str, float], step: int = None):
    _origin(run).log_metrics(run, metrics, step)


def end_experiment(run: ExperimentRun, status: str = "completed"):
    _origin(run).end_run(run, status)
