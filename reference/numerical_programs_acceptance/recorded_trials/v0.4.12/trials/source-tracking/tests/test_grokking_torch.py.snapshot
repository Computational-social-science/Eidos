"""The independent NumPy forward must agree with the declared Transformer."""
import pytest
torch = pytest.importorskip("torch")


def test_independent_numpy_forward_matches_torch():
    from reference.softmax_grokking.model import Transformer
    from reference.softmax_grokking.verify import numpy_forward
    import numpy as np
    torch.manual_seed(11)
    model = Transformer(31, 64, 4).double()
    tokens = torch.tensor([[0, 1], [2, 8], [30, 4], [14, 27]])
    weights = {key: value.detach().numpy() for key, value in model.state_dict().items()}
    expected = model(tokens).detach().numpy()
    assert np.allclose(numpy_forward(weights, tokens.numpy(), 4), expected, rtol=1e-11, atol=1e-11)
