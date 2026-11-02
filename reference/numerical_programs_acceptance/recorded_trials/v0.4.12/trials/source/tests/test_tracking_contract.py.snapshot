"""Run identity is authoritative; ambient MLflow state is not a target selector."""

from pathlib import Path
import sys

import pytest

from framework import tracking

mlflow = pytest.importorskip("mlflow")


@pytest.fixture
def tracking_space(tmp_path, monkeypatch):
    """Keep even a broken default-store write inside a disposable test directory."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tracking, "DVC_AVAILABLE", False)
    previous = mlflow.get_tracking_uri()
    ambient = tmp_path / "ambient.db"
    mlflow.set_tracking_uri(f"sqlite:///{ambient.as_posix()}")
    yield tmp_path
    while mlflow.active_run() is not None:
        active_id = mlflow.active_run().info.run_id
        for database in tmp_path.rglob("*.db"):
            uri = f"sqlite:///{database.as_posix()}"
            try:
                mlflow.MlflowClient(tracking_uri=uri).get_run(active_id)
            except mlflow.exceptions.MlflowException as exc:
                if exc.error_code != "RESOURCE_DOES_NOT_EXIST":
                    raise
            else:
                mlflow.set_tracking_uri(uri)
                mlflow.end_run(status="KILLED")
                break
        else:
            raise RuntimeError("Cannot find the disposable fluent run for cleanup")
    mlflow.set_tracking_uri(previous)


def tracker_at(root, name, uri=None):
    project = root / name
    project.mkdir(exist_ok=True)
    return tracking.ExperimentTracker(
        {
            "project_root": str(project),
            "experiment_name": name,
            "mlflow_uri": uri or f'sqlite:///{(project / "runs.db").as_posix()}',
            "enable_dvc": False,
        }
    )


def test_constructor_preserves_ambient_tracking_store(tracking_space):
    before = mlflow.get_tracking_uri()
    tracker_at(tracking_space, "one")
    assert mlflow.get_tracking_uri() == before


def test_two_runs_interleave_without_becoming_fluent_runs(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    one = tracker.start_run("one")
    two = tracker.start_run("two")
    tracker.log_metrics(one, {"score": 0.1}, step=2)
    tracker.log_metrics(two, {"score": 0.9}, step=4)
    tracker.end_run(one)
    assert tracker.client.get_run(one.run_id).info.status == "FINISHED"
    assert tracker.client.get_run(two.run_id).info.status == "RUNNING"
    assert tracker.client.get_run(one.run_id).data.metrics == {"score": 0.1}
    assert tracker.client.get_run(two.run_id).data.metrics == {"score": 0.9}
    assert mlflow.active_run() is None


def test_metrics_target_passed_run_even_with_nested_fluent_run(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run("owned")
    mlflow.set_tracking_uri(tracker.mlflow_uri)
    with mlflow.start_run(experiment_id=tracker.experiment_id, nested=True) as other:
        tracker.log_metrics(run, {"loss": 0.25}, step=3)
        assert tracker.client.get_run(run.run_id).data.metrics == {"loss": 0.25}
        assert tracker.client.get_run(other.info.run_id).data.metrics == {}


def test_ending_passed_run_does_not_end_ambient_run(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run("owned")
    mlflow.set_tracking_uri(tracker.mlflow_uri)
    ambient = mlflow.start_run(experiment_id=tracker.experiment_id, nested=True)
    tracker.end_run(run)
    assert tracker.client.get_run(run.run_id).info.status == "FINISHED"
    assert tracker.client.get_run(ambient.info.run_id).info.status == "RUNNING"
    assert mlflow.active_run().info.run_id == ambient.info.run_id


def test_another_tracker_does_not_redirect_existing_tracker(tracking_space):
    first = tracker_at(tracking_space, "one")
    second = tracker_at(tracking_space, "two")
    run = first.start_run("first")
    first.log_params(run, {"seed": 19})
    assert first.client.get_run(run.run_id).data.params == {"seed": "19"}
    assert second.client.search_runs([second.experiment_id]) == []


def test_foreign_experiment_run_refused(tracking_space):
    first = tracker_at(tracking_space, "one")
    second = tracker_at(tracking_space, "two", uri=first.mlflow_uri)
    run = first.start_run("first")
    with pytest.raises(ValueError, match="experiment|belong|owner"):
        second.log_metrics(run, {"wrong": 1.0})
    assert first.client.get_run(run.run_id).data.metrics == {}


def test_convenience_uses_origin_without_creating_default_store(tracking_space):
    project = tracking_space / "explicit"
    project.mkdir()
    run = tracking.start_experiment(
        "named",
        config={
            "project_root": str(project),
            "enable_dvc": False,
        },
    )
    tracking.log_params(run, {"seed": 7})
    tracking.log_metrics(run, {"loss": 0.5})
    tracking.end_experiment(run)
    assert run.experiment_name == "named"
    assert not (tracking_space / "mlruns.db").exists()
    assert not (tracking_space / ".dvc").exists()


def test_terminal_run_refuses_further_writes(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run()
    tracker.end_run(run)
    with pytest.raises(ValueError, match="running|terminal|finish|active"):
        tracker.log_metrics(run, {"late": 1.0})
    assert tracker.client.get_run(run.run_id).data.metrics == {}


def test_reloaded_run_preserves_status_and_git_metadata(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run()
    tracker.end_run(run)
    loaded = tracker.get_run(run.run_id)
    assert loaded.status == run.status == "completed"
    assert loaded.git_commit == run.git_commit


def test_artifacts_and_tags_target_the_requested_run(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run("owned")
    artifact = tracking_space / "evidence.txt"
    artifact.write_text("bounded evidence", encoding="utf-8")
    directory = tracking_space / "bundle"
    directory.mkdir()
    (directory / "config.json").write_text('{"seed":19}', encoding="utf-8")
    mlflow.set_tracking_uri(tracker.mlflow_uri)
    with mlflow.start_run(experiment_id=tracker.experiment_id, nested=True) as other:
        tracker.log_artifact(run, artifact, "results")
        tracker.log_artifacts(run, directory, "bundle")
        tracker.add_tags(run, {"condition": "fixed"})
        assert tracker.client.get_run(run.run_id).data.tags["condition"] == "fixed"
        assert "condition" not in tracker.client.get_run(other.info.run_id).data.tags
        assert {item.path for item in tracker.client.list_artifacts(run.run_id)} == {
            "results",
            "bundle",
        }
        assert tracker.client.list_artifacts(other.info.run_id) == []


def test_actual_model_roundtrip_and_registry_preserve_ambient_run(tracking_space):
    sklearn = pytest.importorskip("sklearn")
    from sklearn.tree import DecisionTreeRegressor
    import cloudpickle
    import mlflow.artifacts
    import mlflow.sklearn

    tracker = tracker_at(tracking_space, "models")
    run = tracker.start_run("model-source")
    model = DecisionTreeRegressor(random_state=19).fit([[0], [1], [2]], [0, 1, 4])
    ambient_uri = mlflow.get_tracking_uri()
    ambient_client = mlflow.MlflowClient(tracking_uri=ambient_uri)
    ambient_experiment = ambient_client.create_experiment(
        "ambient-model",
        artifact_location=(tracking_space / "ambient-artifacts").as_uri(),
    )
    with mlflow.start_run(experiment_id=ambient_experiment) as ambient:
        try:
            result = tracker.log_model(
                run,
                model,
                registered_model_name="QualifiedModel",
                skops_trusted_types=["sklearn.tree._tree.Tree"],
                pip_requirements=[
                    f"scikit-learn=={sklearn.__version__}",
                    f"cloudpickle=={cloudpickle.__version__}",
                ],
            )
        except tracking.TrackingOperationError as exc:
            pytest.fail("Disposable model worker failed: " + exc.stderr)
        assert mlflow.get_tracking_uri() == ambient_uri
        assert mlflow.active_run().info.run_id == ambient.info.run_id
        logged = tracker.client.get_logged_model(result["model_id"])
        assert logged.source_run_id == run.run_id
        assert logged.experiment_id == tracker.experiment_id
        assert tracker.client.get_run(run.run_id).info.status == "RUNNING"
        assert ambient_client.get_run(ambient.info.run_id).info.status == "RUNNING"
        from mlflow.utils.file_utils import local_file_uri_to_path

        original_artifacts = Path(
            local_file_uri_to_path(logged.artifact_location)
        ).resolve()
        forbidden = original_artifacts / "recursive-download"
        with pytest.raises(ValueError, match="overlaps"):
            tracker.download_model(run, result["model_id"], forbidden)
        assert not forbidden.exists()
        assert not (
            original_artifacts / ".eidos-export-recursive-download.lock"
        ).exists()
        local = tracker.download_model(
            run, result["model_id"], tracking_space / "downloaded-model"
        )
        loaded = mlflow.sklearn.load_model(local)
        assert loaded.predict([[0], [1], [2]]).tolist() == [0.0, 1.0, 4.0]
        versions = tracker.client.search_model_versions("name='QualifiedModel'")
        assert len(versions) == 1 and versions[0].run_id == run.run_id
        assert mlflow.get_tracking_uri() == ambient_uri
        assert mlflow.active_run().info.run_id == ambient.info.run_id
    tracker.end_run(run)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "0.5"])
def test_invalid_metric_batch_does_not_partially_write(tracking_space, value):
    tracker = tracker_at(tracking_space, "metrics")
    run = tracker.start_run()
    with pytest.raises(ValueError, match="finite real"):
        tracker.log_metrics(run, {"good": 1.0, "invalid": value})
    assert tracker.client.get_run(run.run_id).data.metrics == {}


def test_foreign_store_run_refused_before_mutation(tracking_space):
    first = tracker_at(tracking_space, "first")
    second = tracker_at(tracking_space, "second")
    run = first.start_run()
    with pytest.raises(ValueError, match="store"):
        second.add_tags(run, {"wrong-store": "true"})
    assert "wrong-store" not in first.client.get_run(run.run_id).data.tags


def test_model_target_override_and_invalid_end_status_refused(tracking_space):
    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run()
    with pytest.raises(ValueError, match="explicit run"):
        tracker.log_model(run, None, run_id="another")
    with pytest.raises(ValueError, match="status"):
        tracker.end_run(run, status="arbitrary")
    assert tracker.client.get_run(run.run_id).info.status == "RUNNING"


def test_detached_convenience_run_requires_explicit_binding(tracking_space):
    run = tracking.ExperimentRun("not-bound", "unknown")
    with pytest.raises(ValueError, match="originating tracker"):
        tracking.log_params(run, {"seed": 19})
    assert not (tracking_space / "mlruns.db").exists()


def test_relative_uri_custom_project_model_and_name_roundtrip(
    tracking_space, monkeypatch
):
    import importlib
    import mlflow.artifacts
    import mlflow.sklearn

    pytest.importorskip("sklearn")
    root = tracking_space / "project-code"
    root.mkdir()
    (root / "project_estimator.py").write_text(
        "import numpy as np\nfrom sklearn.base import BaseEstimator, RegressorMixin\n"
        "class ProjectEstimator(RegressorMixin, BaseEstimator):\n"
        "    def predict(self, values):\n        return np.full(len(values), 2.5)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    module = importlib.import_module("project_estimator")
    try:
        tracker = tracking.ExperimentTracker(
            {
                "project_root": str(root),
                "enable_dvc": False,
                "experiment_name": "project",
                "mlflow_uri": "sqlite+pysqlite:///relative.db",
                "registry_uri": "sqlite+pysqlite:///relative.db",
            }
        )
        run = tracker.start_run()
        try:
            result = tracker.log_model(
                run,
                module.ProjectEstimator(),
                name="custom",
                code_paths=["project_estimator.py"],
                serialization_format="cloudpickle",
                pip_requirements=["scikit-learn", "cloudpickle"],
            )
        except tracking.TrackingOperationError as exc:
            pytest.fail("Disposable custom model worker failed: " + exc.stderr)
        assert (root / "relative.db").is_file()
        assert not (tracking_space / "relative.db").exists()
        tracker.end_run(run)
        local = tracker.download_model(
            run, result["model_id"], tracking_space / "downloaded-custom"
        )
        assert mlflow.sklearn.load_model(local).predict([[0], [1]]).tolist() == [
            2.5,
            2.5,
        ]
        assert tracker.client.get_run(run.run_id).info.status == "FINISHED"
    finally:
        sys.modules.pop("project_estimator", None)


def test_run_record_remains_json_serializable(tracking_space):
    from dataclasses import asdict
    import json

    tracker = tracker_at(tracking_space, "one")
    run = tracker.start_run()
    document = json.loads(json.dumps(asdict(run)))
    assert document["run_id"] == run.run_id
    assert document["tracking_uri"] == tracker.mlflow_uri
    assert "_owner" not in document
    import pickle

    restored = pickle.loads(pickle.dumps(run))
    assert restored.run_id == run.run_id and restored._owner is None


def test_separate_trackers_cannot_write_after_concurrent_termination(
    tracking_space, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    first = tracker_at(tracking_space, "one")
    second = tracking.ExperimentTracker(
        {
            **first.config,
            "mlflow_uri": first.mlflow_uri.replace("sqlite:", "sqlite+pysqlite:", 1),
        }
    )
    run = first.start_run()
    other = second.get_run(run.run_id)
    entered, release, ending = threading.Event(), threading.Event(), threading.Event()
    events = []
    original_batch = first.client.log_batch
    original_end = second.client.set_terminated

    def paused_batch(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        original_batch(*args, **kwargs)
        events.append("write")

    def record_end(*args, **kwargs):
        original_end(*args, **kwargs)
        events.append("end")

    def end():
        ending.set()
        second.end_run(other)

    monkeypatch.setattr(first.client, "log_batch", paused_batch)
    monkeypatch.setattr(second.client, "set_terminated", record_end)
    with ThreadPoolExecutor(max_workers=2) as pool:
        write_future = pool.submit(first.log_metrics, run, {"ordered": 1.0})
        assert entered.wait(10)
        end_future = pool.submit(end)
        try:
            assert ending.wait(10)
            assert not end_future.done()
        finally:
            release.set()
        write_future.result(timeout=10)
        end_future.result(timeout=10)
    assert events == ["write", "end"]
    with pytest.raises(ValueError, match="terminal"):
        first.log_metrics(run, {"late": 1.0})


@pytest.mark.parametrize(
    "key,value",
    [
        ("enable_dvc", "false"),
        ("model_timeout_s", float("nan")),
        ("tracking_lock_timeout_s", 0),
        ("mlflow_uri", "sqlite://"),
        ("mlflow_uri", "sqlite:///:memory:"),
        ("mlflow_uri", "sqlite+pysqlite:///:memory:"),
    ],
)
def test_invalid_configuration_does_not_create_store(tracking_space, key, value):
    root = tracking_space / "invalid"
    root.mkdir()
    with pytest.raises(ValueError):
        tracking.ExperimentTracker({"project_root": str(root), key: value})
    assert not (root / "mlruns.db").exists()


def test_run_ownership_coordinates_actual_separate_process(tracking_space):
    import json
    from framework.subprocesses import run_tree

    tracker = tracker_at(tracking_space, "processes")
    tracker.config["tracking_lock_timeout_s"] = 0.2
    run = tracker.start_run()
    package_root = str(Path(tracking.__file__).resolve().parents[2])
    program = (
        "import sys,json;sys.path.insert(0," + repr(package_root) + ");"
        "from framework.tracking import ExperimentTracker;"
        "tracker=ExperimentTracker(json.loads(sys.argv[1]));"
        "run=tracker.get_run(sys.argv[2]);tracker.end_run(run)"
    )
    command = [
        sys.executable,
        "-I",
        "-X",
        "utf8",
        "-c",
        program,
        json.dumps(tracker.config),
        run.run_id,
    ]
    with tracker._ownership(run):
        refused = run_tree(command, cwd=tracking_space, timeout=60)
        assert refused.returncode != 0 and "TimeoutError" in refused.stderr
        assert tracker.client.get_run(run.run_id).info.status == "RUNNING"
    accepted = run_tree(command, cwd=tracking_space, timeout=60)
    assert accepted.returncode == 0, accepted.stderr
    assert tracker.client.get_run(run.run_id).info.status == "FINISHED"
