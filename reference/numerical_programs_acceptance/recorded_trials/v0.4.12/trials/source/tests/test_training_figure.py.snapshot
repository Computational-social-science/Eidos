"""The training contrast must show all registered seeds and preserve exact zeros."""


def test_training_export_covers_all_seeds_without_log_floor(tmp_path):
    import json
    from pathlib import Path
    from tools.training_figure import render_training
    report = json.loads((Path(__file__).resolve().parents[1] /
                         "reference/softmax_training/docs/evidence.json").read_text(encoding="utf-8"))
    render_training(tmp_path, report)
    assert "exact zero" in (tmp_path / "trajectory.svg").read_text(encoding="utf-8")
    assert (tmp_path / "trajectory.pdf").read_bytes().startswith(b"%PDF")
    assert (tmp_path / "trajectory.csv").read_text().count("\n") == 1 + 3 * 2 * 21
