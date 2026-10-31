# A fix for softmax and cross-entropy, as a tool Eidos can call

The paper (Barron, Gnanapragasam & Tschannen, arXiv:2610.31642) prints a stable log-softmax and two
cross-entropy gradients. Paper2Agent's code branch turns such functions into an MCP server; this report
is the text its claims live in, so Gate S can check that the sentences a reader sees are the sentences
the evidence supports.

The existing Paper2Agent server exposes four tools: `log_softmax`, `softmax`, `hard_cross_entropy`
and `soft_target_cross_entropy`. A run of `agent.py` starts it over stdio, checks the first three
tools on the paper's input `z = [9, -9, -9]`, and exercises soft-target cross-entropy using explicit
teacher logits. It writes `docs/evidence.json` and an argument-and-result trace of every tool call
in `docs/agent_trace.json`. The backend and Python version are recorded with the evidence.

## Claims

**C1.** On the paper's input, the log-softmax tool returns the paper's stated value.

**C2.** The hard-target gradient sums to zero within float-point rounding.

## What the run also shows

A precision-cliff negative control uses hard cross-entropy with logits `[40, 0, 0]` and target 0
in float64. The conventional target derivative must be exactly zero while the fixed derivative
remains negative. The fixed gradient's zero-sum residual is bounded relative to its magnitude,
without an absolute tolerance floor. The control passes only when the conventional gradient fails
the same relative zero-sum check.

Soft-target qualification uses float32 teacher logits `[2, 1, 0]`: exact student equality and a
near-teacher student constructed by adding float32 `[-1e-7, 1e-7, 0]`. Evidence records the actual
represented student and perturbation, rather than assuming decimal literals survive conversion.
Both calls explicitly select `teacher_kind="logits"`. The independent Decimal definition in
`framework.verifiers.numerics.probe_logit_distillation` checks their returned loss and every
gradient component; a true server zero-sum flag alone cannot qualify them.

These revised controls and soft-target cases are **posthoc regression qualification** of the
arXiv:2610.31642v3 kernels. They are not new preregistered research. The original C1/C2 claim
register and its evidence pointers remain unchanged. The paper's printed-value tolerance belongs
to the separate C1 oracle; exact MCP cases test the fixed API's numerical contract.

## Scope

The registered claims cover the original paper input in NumPy float64. Additional regression
qualification covers the stated float64 precision-cliff control and two float32 logits-distillation
cases only. This says nothing about training dynamics, other backends or inputs, or the paper's
grokking experiment; those need their own specs and their own runs. Probability teachers remain
a legacy API mode and are not certified against the v3 softmax-cancellation fix.
