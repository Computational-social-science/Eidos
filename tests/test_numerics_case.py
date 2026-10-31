"""The public case must contain actual, independently checked numerical results."""

from tools.numerics_case import build_case, export_case, _error


def test_metrics_do_not_round_decimal_reference_to_float_before_comparing():
    from decimal import Decimal, localcontext
    with localcontext() as context:
        context.prec = 80
        exact = Decimal(1) / Decimal(3)
    relative, absolute, norm = _error([1 / 3], [exact])
    assert 1e-18 < relative < 1e-15
    assert absolute > 0 and norm > 0


def test_a_bad_displayed_case_cannot_borrow_pass_from_the_twelve_spot_checks(monkeypatch):
    from tools import numerics_case
    original = numerics_case.kernels.hard_cross_entropy
    def broken(z, target):
        loss, gradient = original(z, target)
        if float(z[0]) == 22:
            gradient = gradient * 2
        return loss, gradient
    monkeypatch.setattr(numerics_case.kernels, "hard_cross_entropy", broken)
    data = build_case()
    assert data["qualification"]["verdict"] == "FAIL"
    assert data["qualification"]["sweep"]["failed"]


def test_wrong_displayed_loss_cannot_borrow_pass_from_good_gradients(monkeypatch):
    from tools import numerics_case
    original = numerics_case.kernels.hard_cross_entropy
    def broken(z, target):
        loss, gradient = original(z, target)
        return (loss * 2 if float(z[0]) == 22 else loss), gradient
    monkeypatch.setattr(numerics_case.kernels, "hard_cross_entropy", broken)
    assert build_case()["qualification"]["verdict"] == "FAIL"


def test_case_exposes_the_float32_cliff_and_fixed_gradient():
    data = build_case()
    case = next(row for row in data["collapse"] if row["dtype"] == "float32" and row["margin"] == 18)
    assert case["standard_gradient"][0] == 0
    assert case["fixed_gradient"][0] < 0
    assert case["fixed_error"] < 1e-5
    assert data["qualification"]["verdict"] == "PASS"


def test_case_separates_exact_equality_from_rounded_perturbations():
    data = build_case()
    rows = [row for row in data["cancellation"] if row["perturbation"] == 0]
    assert {row["dtype"] for row in rows} == {"float32", "float64"}
    assert all(row["fixed_gradient"] == [0.0, 0.0, 0.0] for row in rows)
    assert all(row["reference_norm"] == 0 for row in rows)


def test_export_contains_reproducible_downloads(tmp_path):
    import zipfile
    data = build_case()
    export_case(tmp_path, data)
    for name in ("evidence.json", "cases.csv", "report.qmd", "reproduce.zip"):
        assert (tmp_path / name).is_file()
    with zipfile.ZipFile(tmp_path / "reproduce.zip") as bundle:
        names = set(bundle.namelist())
        assert {"README.md", "pyproject.toml", "uv.lock", "evidence.json"} <= names
        assert "framework/stable_numerics.py" in names
        assert "tools/numerics_case.py" in names
        assert "reference/reproduction/barron2026/mcp/vendor/LICENSE" in names
        assert "projects/softmax_training/project.yaml" in names
        assert "tests/test_training_consumer.py" in names
        assert all(".venv" not in name for name in names)


def test_bundle_command_rebuilds_all_displayed_cases(tmp_path):
    import json
    import subprocess
    import sys
    import zipfile
    export_case(tmp_path)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(tmp_path / "reproduce.zip") as bundle:
        bundle.extractall(extracted)
    result = subprocess.run([sys.executable, "reproduce.py"], cwd=extracted,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    rebuilt = json.loads((extracted / "regenerated/evidence.json").read_text(encoding="utf-8"))
    original = json.loads((extracted / "evidence.json").read_text(encoding="utf-8"))
    assert rebuilt["collapse"] == original["collapse"]
    assert rebuilt["cancellation"] == original["cancellation"]
