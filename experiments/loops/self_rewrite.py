"""Iterated self-rewrite: a classic iterated map, applied to an LLM pipeline.

Why this is the consumer of the local-operator layer
----------------------------------------------------
A self-rewrite loop -- "restate this instruction in your own words", applied to the
model's own output -- is an iterated map ``p_{n+1} = S(p_n)``. It is the smallest object
in current LLM practice that has the three properties the operator layer was built for:

* it is a **map**, so fixed points and their stability are meaningful;
* it is **short-time**: one rewrite is cheap, and the interesting behaviour is in the
  composition of many;
* it **degenerates**: the loop either settles (a fixed point), cycles, or drifts. Whether
  a pipeline of models rewriting each other converges is an open, practical question.

The layer is used as designed: fit a local operator on the first half of the iterations,
predict the fixed point by Newton, then check that prediction against the iterations the
operator never saw.

No PDE is involved and none is claimed. The map is on a hashed text representation, which
is crude but deterministic and dependency-free; a sentence encoder can be substituted
without changing the interface.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..surrogate import RandomFeatureOperator, fixed_point

DIM = 256
INSTRUCTION = ("Restate the following instruction in your own words. Keep its meaning "
               "and all constraints. Reply with the instruction only.\n\n")


def embed(text: str) -> np.ndarray:
    """Deterministic hashed character-trigram embedding, L2-normalised.

    A sentence encoder would be better; this one has no download, no GPU and no
    version skew, which matters more for a gate than a few points of similarity.
    """
    vec = np.zeros(DIM, dtype=float)
    clean = " ".join(text.lower().split())
    for i in range(max(1, len(clean) - 2)):
        gram = clean[i:i + 3]
        h = int.from_bytes(hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest(),
                           "little")
        vec[h % DIM] += 1.0 if (h >> 63) & 1 else -1.0
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance in [0, 2]; 0 means the two texts hash identically.

    Both inputs are re-normalised: a predicted vector comes out of a linear operator and
    is not unit length, and the unnormalised dot product produced distances below zero.
    """
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    cos = float(np.dot(a, b) / (na * nb))
    return float(1.0 - max(-1.0, min(1.0, cos)))


@dataclass
class LoopTrace:
    texts: List[str]
    vectors: np.ndarray
    distances: List[float]          # d(p_n, p_{n+1})
    fixed: bool = False
    contraction: float = float("nan")   # mean log-distance slope; negative = contracting

    def as_dict(self) -> Dict[str, object]:
        return {"cycles": len(self.texts) - 1, "fixed": self.fixed,
                "contraction": self.contraction,
                "distances": [round(d, 6) for d in self.distances]}


def run_loop(generate: Callable[[str], str], seed: str, cycles: int) -> LoopTrace:
    """Apply the rewrite map ``cycles`` times, recording text and distances."""
    texts = [seed]
    for _ in range(cycles):
        texts.append(generate(INSTRUCTION + texts[-1]))
    vectors = np.stack([embed(t) for t in texts])
    distances = [distance(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
    fixed = bool(distances and distances[-1] < 0.05)
    contraction = float("nan")
    positive = [d for d in distances if d > 0]
    if len(positive) >= 2:
        contraction = float(np.polyfit(np.arange(len(positive)), np.log(positive), 1)[0])
    return LoopTrace(texts, vectors, distances, fixed, contraction)


@dataclass
class OperatorPrediction:
    fixed_point: Optional[np.ndarray]
    converged: bool
    train_error: float
    test_error: float
    agreement: float          # distance between predicted fixed point and the observed one


def fit_and_predict(trace: LoopTrace, n_features: int = 512,
                    split: float = 0.5) -> OperatorPrediction:
    """Fit ``S`` on the first half of the iterations, predict, then score on the second.

    The split is the point: predicting the iterations the operator was fitted on proves
    nothing. ``test_error`` is the mean cosine distance on held-out transitions.
    """
    x, y = trace.vectors[:-1], trace.vectors[1:]
    cut = max(2, int(math.ceil(len(x) * split)))
    op = RandomFeatureOperator(n_features=n_features, seed=0).fit(
        x[:cut], y[:cut], np.zeros(cut))
    train_err = float(np.mean([distance(op.step(x[i], 0.0), y[i]) for i in range(cut)]))
    test_err = (float(np.mean([distance(op.step(x[i], 0.0), y[i])
                              for i in range(cut, len(x))]))
                if cut < len(x) else float("nan"))

    u_star, info = fixed_point(op.step, 0.0, x[-1], tol=1e-6, max_iter=80)
    observed = trace.vectors[-1]
    agreement = float(distance(u_star, observed)) if info["converged"] else float("nan")
    return OperatorPrediction(u_star if info["converged"] else None,
                              bool(info["converged"]), train_err, test_err, agreement)


def evaluate(traces: Sequence[LoopTrace], split: float = 0.5) -> Dict[str, object]:
    preds = [fit_and_predict(t, split=split) for t in traces]
    test = [p.test_error for p in preds if p.test_error == p.test_error]
    agree = [p.agreement for p in preds if p.agreement == p.agreement]
    return {
        "seeds": len(traces),
        "fixed_observed": sum(1 for t in traces if t.fixed),
        "contraction_median": float(np.median([t.contraction for t in traces
                                               if t.contraction == t.contraction]))
        if any(t.contraction == t.contraction for t in traces) else float("nan"),
        "converged_operator": sum(1 for p in preds if p.converged),
        "median_test_error": float(np.median(test)) if test else float("nan"),
        "median_agreement": float(np.median(agree)) if agree else float("nan"),
        "predictions": [{"converged": p.converged, "train_error": p.train_error,
                         "test_error": p.test_error, "agreement": p.agreement}
                        for p in preds],
    }
