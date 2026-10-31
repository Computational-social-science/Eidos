"""Data, independent NumPy inference and portable evidence helpers (no Torch import)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile
import re
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode()).hexdigest()


def json_digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def dataset(modulus):
    tokens = np.array([(a, b) for a in range(modulus) for b in range(modulus)], dtype=np.int64)
    return tokens, (tokens[:, 0] + tokens[:, 1]) % modulus


def shapes(p, d):
    return {"position": (2, d), "embedding.weight": (p, d), "qkv.weight": (3*d, d),
            "qkv.bias": (3*d,), "projection.weight": (d, d), "projection.bias": (d,),
            "ff1.weight": (4*d, d), "ff1.bias": (4*d,), "ff2.weight": (d, 4*d),
            "ff2.bias": (d,), "head.weight": (p, d), "head.bias": (p,)}


def numpy_forward(weights, tokens, heads):
    """Independent float64 evaluation of the declared two-token causal network."""
    weights = {name: np.asarray(value, dtype=np.float64) for name, value in weights.items()}
    def linear(x, key):
        return x @ weights[key + ".weight"].T + weights[key + ".bias"]
    x = weights["embedding.weight"][tokens] + weights["position"]
    batch, length, width = x.shape
    q, k, v = [part.reshape(batch, length, heads, width // heads).transpose(0, 2, 1, 3)
               for part in np.split(linear(x, "qkv"), 3, axis=-1)]
    scores = q @ k.swapaxes(-2, -1) / np.sqrt(width // heads)
    scores = np.where(np.triu(np.ones((length, length), dtype=bool), 1), -np.inf, scores)
    exponent = np.exp(scores - scores.max(axis=-1, keepdims=True))
    attention = (exponent / exponent.sum(axis=-1, keepdims=True)) @ v
    x = x + linear(attention.transpose(0, 2, 1, 3).reshape(batch, length, width), "projection")
    x = x + linear(np.maximum(linear(x, "ff1"), 0), "ff2")
    return linear(x[:, -1], "head")


def classification_metrics(logits, labels, train, test):
    logits = np.asarray(logits, dtype=np.float64)
    correct = logits.argmax(-1) == labels
    target = logits[np.arange(len(labels)), labels]
    others = np.where(np.arange(logits.shape[1]) == np.asarray(labels)[:, None], -np.inf, logits)
    margins = target - np.logaddexp.reduce(others, axis=-1)
    return {"train_accuracy": float(correct[train].mean()), "test_accuracy": float(correct[test].mean()),
            "mean_margin": float(margins[train].mean()),
            "cross_entropy_float64": float(np.logaddexp(0, -margins[train]).mean())}


def load_weights(stem, protocol):
    """Bind the JSON mirror to Torch raw storage without loading pickle code."""
    stem = Path(stem)
    payload = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
    expected = shapes(protocol["modulus"], protocol["width"])
    if set(payload) != set(expected):
        raise ValueError("unexpected model tensor inventory")
    weights = {key: np.asarray(payload[key], dtype=np.float32) for key in expected}
    if any(weights[key].shape != shape or not np.isfinite(weights[key]).all() for key, shape in expected.items()):
        raise ValueError("invalid tensor shape or range")
    with zipfile.ZipFile(stem.with_suffix(".pt")) as archive:
        names = sorted((name for name in archive.namelist() if re.search(r"/data/\d+$", name)),
                       key=lambda name: int(name.rsplit("/", 1)[1]))
        if len(names) != len(expected) or sum(archive.getinfo(n).file_size for n in names) > 10_000_000:
            raise ValueError("invalid raw storage inventory")
        for name, key in zip(names, expected):
            if archive.read(name) != weights[key].astype("<f4").tobytes():
                raise ValueError("JSON mirror differs from saved model: " + key)
    return weights
