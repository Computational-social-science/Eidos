"""The stationarity experiment must start with equal represented logits, not just weights."""
import copy
import pytest

torch = pytest.importorskip("torch")


def test_teacher_cache_uses_the_same_batch_shape_as_each_student_forward():
    from reference.softmax_training.train import prepare_teacher_targets
    torch.manual_seed(3)
    model = torch.nn.Sequential(torch.nn.Linear(106, 128), torch.nn.ReLU(), torch.nn.Linear(128, 53))
    model.requires_grad_(False)
    train_x, test_x = torch.randn(1404, 106), torch.randn(1405, 106)
    target, log_p, heldout = prepare_teacher_targets(model, train_x, test_x, 4.0)
    student = copy.deepcopy(model).requires_grad_(True)
    assert torch.equal(student(train_x) / 4, target)
    assert torch.equal(student(test_x), heldout)
    assert torch.equal(torch.nn.functional.log_softmax((heldout / 4).double(), -1), log_p)


def test_weight_equality_does_not_excuse_different_initial_logits():
    from reference.softmax_training.train import require_equal_logits
    with pytest.raises(RuntimeError, match="initial logits"):
        require_equal_logits(torch.zeros(3), torch.tensor([0, 0, 1e-7]))
