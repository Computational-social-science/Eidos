"""Dependency-specific tracking operations in a disposable, owned interpreter.

The model payload is trusted caller code, serialized by its tracker. This is an
execution boundary, not a hostile-model sandbox. No global MLflow settings leak
back into the caller.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys


def operate(request):
    operation = request["operation"]
    root = Path(request["project_root"]).resolve()
    if operation == "smoke":
        if any(root.iterdir()):
            raise ValueError("tracking smoke requires a fresh empty workspace")
        for variable, name in (
            ("DVC_GLOBAL_CONFIG_DIR", "isolated-global"),
            ("DVC_SYSTEM_CONFIG_DIR", "isolated-system"),
            ("DVC_SITE_CACHE_DIR", "isolated-site-cache"),
        ):
            directory = root / name
            directory.mkdir()
            os.environ[variable] = str(directory)
        os.environ["DVC_NO_ANALYTICS"] = "1"
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from framework import tracking

        if Path(tracking.__file__).resolve().parent != Path(__file__).resolve().parent:
            raise ValueError("tracking smoke imported another package")
        tracker = tracking.ExperimentTracker(
            {"project_root": str(root), "experiment_name": "audit"}
        )
        first, second = tracker.start_run("one"), tracker.start_run("two")
        tracker.log_metrics(first, {"score": 0.1})
        tracker.log_metrics(second, {"score": 0.9})
        tracker.end_run(first)
        independent = tracker.client.get_run(second.run_id).info.status == "RUNNING"
        tracker.end_run(second)
        data = root / "audit-data.txt"
        data.write_bytes(b"source-bound tracking smoke\n")
        data_verified = False
        private_cache = False
        if tracker.dvc_available:
            from dvc.repo import Repo

            with Repo(str(root)) as repository:
                private_cache = (
                    Path(repository.cache.repo.path).resolve().is_relative_to(root)
                )
            versioner = tracker._data_versioner()
            versioner.add(data)
            data_verified = (
                versioner.get_file_hash(data)
                == hashlib.md5(data.read_bytes()).hexdigest()
            )
        return {
            "checks": {
                "isolated_runs": first.run_id != second.run_id and independent,
                "metrics": tracker.get_run(first.run_id).metrics == {"score": 0.1}
                and tracker.get_run(second.run_id).metrics == {"score": 0.9},
                "terminal_states": tracker.get_run(first.run_id).status == "completed"
                and tracker.get_run(second.run_id).status == "completed",
                "dvc_content": data_verified,
                "private_dvc_cache": private_cache,
            },
            "run_ids": [first.run_id, second.run_id],
            "source_sha256_lf": {
                "module": hashlib.sha256(
                    Path(tracking.__file__).read_text(encoding="utf-8").encode()
                ).hexdigest(),
                "worker": hashlib.sha256(
                    Path(__file__).read_text(encoding="utf-8").encode()
                ).hexdigest(),
            },
        }
    if operation in {"dvc_url", "dvc_hash"}:
        import dvc.api

        path = request["path"]
        target = (root / path).resolve()
        target.relative_to(root)
        if operation == "dvc_url":
            return dvc.api.get_url(path, repo=str(root), remote=request["remote"])
        filesystem = dvc.api.DVCFileSystem(repo=str(root))
        try:
            info = filesystem.info(path)
            metadata = info.get("dvc_info") or {}
            digest = metadata.get("md5")
            if not isinstance(digest, str) or not re.fullmatch(
                r"[0-9a-f]{32}(?:\.dir)?", digest
            ):
                raise ValueError("target has no registered DVC MD5 checksum")
            if request["require_clean"] and target.is_file():
                with target.open("rb") as handle:
                    actual = hashlib.file_digest(handle, "md5").hexdigest()
                if actual != digest:
                    raise ValueError(
                        "workspace bytes differ from the registered DVC checksum"
                    )
            elif request["require_clean"] and target.is_dir():
                from dvc.repo import Repo
                from dvc_data.hashfile.state import StateNoop

                # DVC's usual mtime/size cache can hide preserved-stat edits.
                # Use its native tree/ignore semantics with checksum caches off.
                with Repo(str(root)) as repository:
                    repository.state = StateNoop()
                    repository.cache.repo.state = StateNoop()
                    repository.cache.local.state = StateNoop()
                    if repository.status(targets=[str(target)], check_updates=False):
                        raise ValueError(
                            "workspace data changed under uncached DVC verification"
                        )
            return digest
        finally:
            filesystem.close()
    if operation in {"model", "model_download"}:
        import cloudpickle
        import mlflow
        import mlflow.sklearn

        # Import the dependency before adding trusted project modules. Cloudpickle
        # may refer to a project class by module name; code_paths is applied by
        # MLflow only after deserialization, so those modules must be visible now.
        for entry in [root, *(Path(path) for path in request.get("module_paths", []))]:
            directory = entry if entry.is_dir() else entry.parent
            sys.path.insert(0, str(directory))
        mlflow.set_tracking_uri(request["tracking_uri"])
        mlflow.set_registry_uri(request["registry_uri"])
        mlflow.set_experiment(experiment_id=request["experiment_id"])
        client = mlflow.MlflowClient(
            tracking_uri=request["tracking_uri"], registry_uri=request["registry_uri"]
        )
        run = client.get_run(request["run_id"])
        if run.info.experiment_id != request["experiment_id"]:
            raise ValueError("model target belongs to another experiment")
        if operation == "model_download":
            model = client.get_logged_model(request["model_id"])
            if (
                model.source_run_id != request["run_id"]
                or model.experiment_id != request["experiment_id"]
            ):
                raise ValueError("model belongs to another run or experiment")
            path = mlflow.artifacts.download_artifacts(
                artifact_uri=f"models:/{model.model_id}",
                dst_path=request["destination"],
                tracking_uri=request["tracking_uri"],
                registry_uri=request["registry_uri"],
            )
            return {
                "path": path,
                "run_id": request["run_id"],
                "model_id": model.model_id,
            }
        if run.info.status != "RUNNING":
            raise ValueError(
                "model target must be a running run in the selected experiment"
            )
        with Path(request["payload"]).open("rb") as handle:
            payload = cloudpickle.load(handle)
        model_id = payload["kwargs"].get("model_id")
        if model_id:
            existing = client.get_logged_model(model_id)
            if (
                existing.source_run_id != request["run_id"]
                or existing.experiment_id != request["experiment_id"]
            ):
                raise ValueError("model belongs to another run or experiment")
        result = mlflow.sklearn.log_model(
            payload["model"],
            artifact_path=request["artifact_path"],
            run_id=request["run_id"],
            **payload["kwargs"],
        )
        if result.run_id != request["run_id"]:
            raise ValueError("logged model is bound to a different run")
        return {
            "model_uri": result.model_uri,
            "model_id": result.model_id,
            "artifact_uri": client.get_logged_model(result.model_id).artifact_location,
            "run_id": request["run_id"],
            "tracking_uri": request["tracking_uri"],
        }
    raise ValueError("unknown tracking operation")


def main(argv):
    if len(argv) != 2:
        raise ValueError("expected request and response paths")
    request = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    result = operate(request)
    with Path(argv[1]).open("x", encoding="utf-8") as handle:
        json.dump(
            {
                "kind": "eidos.tracking.operation",
                "operation": request["operation"],
                "result": result,
            },
            handle,
            allow_nan=False,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
