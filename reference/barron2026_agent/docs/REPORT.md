# A fix for softmax and cross-entropy, as a tool Eidos can call

The paper (Barron, Gnanapragasam & Tschannen, arXiv:2610.31642) prints a stable log-softmax and two
cross-entropy gradients. Paper2Agent's code branch turns such functions into an MCP server; this report
is the text its claims live in, so Gate S can check that the sentences a reader sees are the sentences
the evidence supports.

The server exposes four tools: `log_softmax`, `softmax`, `hard_cross_entropy` and
`soft_target_cross_entropy`. A run of `agent.py` starts it over stdio, calls each tool on the paper's own
input `z = [9, -9, -9]`, and writes `docs/evidence.json`.

## Claims

**C1.** On the paper's input, the log-softmax tool returns the paper's stated value.

**C2.** The hard-target gradient sums to zero within float-point rounding.

## What the run also shows

A negative control runs beside the claims: the same soft-target tool called with a teacher that does not
sum to one `[0.5, 0.6]`. Its gradient sum must leave exactly `1 - sum(teacher)` behind. If that control
did not fire, the zero-sum check in C2 would be accepting broken gradients, and its pass would mean
nothing.

## Scope

One input vector, one arithmetic (float64 numpy), two equalities. This says nothing about training
dynamics, numerical behaviour in other precisions, or the paper's grokking experiment; those need their
own specs and their own runs.
