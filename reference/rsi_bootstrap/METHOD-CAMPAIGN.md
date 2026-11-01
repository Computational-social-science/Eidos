# Local known-method retrieval and feedback comparison

This source-checkout experiment compares three independent proposals against
three proposals augmented with a small local method bank and public numerical
feedback. It uses existing local model/backend files and no paid service or
mandatory service key. It is not an installation of the full OpenScholar/ERA
systems, a literature-discovery benchmark or a demonstration of RSI.

The bank intentionally contains a documented repair for this known task.
Summaries and the derivative derivation were prepared by the external maintainer
workflow. They are not discoveries made by the tested local model. The comparison
changes both supplied knowledge and feedback history; it is not the roadmap's
matched-A/H/B test of an improved improver.

## Execute

Use the [local runtime guide](LOCAL-RUNTIME.md) to supply a trusted native
llama.cpp binary, GGUF model, hashes and protected-service observations. For this
preregistered comparison, configure 12 threads, context 8192, maximum 768 target
output tokens and a 900-second whole-attempt deadline. The schema/limits and
same-host prerequisites of the local runtime still apply.

From the repository root, with the project's active interpreter:

```text
python -m reference.rsi_bootstrap.method_campaign --config local-model.json --output runs/method-campaign-001
```

The output directory must be new. The default corpus is `methods/cards.json`.
Custom banks must be explicit project files and pass the schema/identity checks;
changing a bank defines a new experiment. Review source and redistribution terms
before adding resources. No upstream article, implementation or model weight
is silently downloaded by this command.

## What runs

The fixed order is baseline-1, retrieval-feedback-1, baseline-2,
retrieval-feedback-2, baseline-3, retrieval-feedback-3. Each target has a new
owned model server and must report zero cached prompt tokens. Both arms retain
all three proposals even after a successful candidate.

The baseline receives the original task only. The treatment retrieves two cards
with deterministic lexical scoring. Later treatment requests also use the best
prior admissible candidate from that arm, with earliest ties, plus at most four
actual failed public observations. Malformed responses have no invented numeric
score. No sealed answers are involved. The parent reconstructs the expected
request and checks it against the context actually sent.

Each arm has the same ceilings: three target proposals, 10,000 total model tokens
and 3,000 charged seconds. Logical token counts include target and post-target
literal-control prompts/completions, including cached prompt tokens. Actual
costs may differ under equal ceilings; the report must show them.

Before generation, `/apply-template` and `/tokenize` perform non-generative
preflight on the owned backend. Token/context reserves include output maxima
and a declared template margin. Actual usage must be coherent, and nonempty
output cannot claim zero completion tokens. Literal controls are auxiliary
generation calls, not research candidates. They follow the target.

Failure or budget overflow stops the comparison. Launch intent and failure costs
are retained; unavailable token costs remain unknown. A partial comparison cannot
be treated as complete or used to claim a treatment gain. Budget checks do not
establish physical compute attestation against a hostile backend/maintainer.

## Read the artifacts

- `campaign-protocol.json`: frozen sources, bank, config, query, order, clocks and budgets.
- `progress.json`: durable attempt intent/status, including a currently interrupted attempt.
- Each attempt directory: exact low-level runtime protocol, actual response,
  evaluator/core result, control, logs and runtime outcome.
- Each `*.request.json`: exact arm-specific context, dependencies and remaining allowance.
- `campaign-result.json`: worker outcomes and costs including failed attempts.
- `campaign-outcome.json`: parent reconstruction and runtime acceptance, with
  setup, dispatch, verification and total API timing.

A complete experiment can contain only failed candidates. Exit zero means the
comparison met its execution/accounting contract; inspect candidate conformance
separately. No candidate gains scientific authority or promotion. A nonzero exit
preserves an incomplete experiment and its diagnostics.

Cost timing uses `perf_counter`; deadline timing uses `monotonic`. Their clock
implementations/resolutions are recorded. The cross-clock consistency check
allows one internal deadline-clock tick; the arm budget itself uses exact
recorded outer cost durations. Total API timing excludes interpreter/CLI startup
and the final atomic receipt write. These are measured software scopes, not hard
real-time, OS memory/disk or network-isolation guarantees.

Run synthetic controls without model weights:

```text
python -m pytest reference/rsi_bootstrap -q
```

Any result remains a repeated-proposal observation on one public function.
Independent new-machine/Linux model execution, GPU adaptation, novel research,
sealed transfer and recursive improvement require separate evidence.
