---
document_id: EIDOS-RSI-PLAN-001
language: en
updated: 2026-11-01
status: proposed_execution_plan
evidence_baseline_tag: v0.4.10
evidence_baseline_commit: 1b5157a08fa525eba0cf6a252616cee8681192b8
scientific_rsi_status: not_demonstrated
immediate_target: independently_evaluated_supervised_improvement
execution_mode: on_demand_bounded_campaigns
---

# EIDOS: a plan for verifiable recursive improvement

EIDOS has useful research infrastructure, but it has not demonstrated scientific
recursive self-improvement (RSI). The next investment should establish whether
EIDOS can produce, verify, retain and transfer improvements to its own research
procedure. More infrastructure is justified only when it removes a measured
obstacle to that experiment.

All future artifacts, interfaces, thresholds and milestones below are proposals.
This document does not implement a controller, qualify a model, authorize
scientific claims or certify an operational migration.

## 1. The Bootstrap question

Bootstrap is necessary to start; it is not sufficient to sustain improvement.
The critical link is **independently verified improvement of the improvement
procedure itself**. A seed needs enough competence to find at least some useful
changes, and an evaluator needs enough independence to distinguish progress from
measurement error, leakage and extra resources.

| Meaning | Function | Evidence needed |
|---|---|---|
| Project bootstrap | Create a project, registry and runnable baseline | A real consumer can run, fail correctly and deliver reproducible outputs |
| Capability bootstrap | Supply an initial model, tools, knowledge, evaluator and resource budget | The seed can propose at least some executable, verifiably useful changes |
| Recursive improvement | Let a successor improve the procedure that produces future successors | Independent, budget-matched evidence across generations and fresh tasks |
| Statistical bootstrap | Resample observations to estimate uncertainty | Valid sampling assumptions; this is an estimation method, not an RSI mechanism |

The existing `tools/bootstrap_project.py` addresses project initialization. It
does not establish capability bootstrap or recursive improvement.

```text
trusted seed + frozen task contract + resource budget
    -> observe a capability gap
    -> propose a falsifiable improvement
    -> register a comparison before running it
    -> execute in isolation
    -> evaluate with independent evidence
    -> promote or reject; preserve the complete record
    -> use the accepted successor to propose the next improvement
    -> test whether that improvement procedure transfers
```

Three distinctions prevent overstating progress:

1. A developer or an external coding assistant fixing EIDOS is ordinary system
   development. It becomes evidence about EIDOS self-improvement only when the
   specified EIDOS procedure produces the change and the record attributes all
   external assistance.
2. Improving one research answer is task improvement. Improving retrieval,
   diagnosis, experiment selection or code repair across new tasks is procedure
   improvement. Merely storing a paper or a lesson is not a measured capability gain.
3. Improving a procedure once is not sufficient evidence that the improved
   procedure can improve itself again. That is the recursive question.

Terminology varies in the literature. This plan targets **bounded scaffold-level
recursive improvement with fixed model weights** first. It does not equate that
target with unrestricted self-modification, model-weight improvement or general
autonomous scientific discovery. STOP explicitly distinguishes its fixed-LM
code-improvement result from full RSI; DGM evaluates agent-code changes using
coding benchmarks. Those are useful precedents, not qualifications of EIDOS.
See [STOP](https://arxiv.org/abs/2310.02304v3) and
[DGM](https://arxiv.org/abs/2505.22954v3).

## 2. Evidence baseline and present decision

| Area | Observed evidence | What it does not establish |
|---|---|---|
| Software and release | v0.4.10 source audit: 1,110 passed, six skips including collection-level skips; 11 chains: 10 PASS, one SKIP. Exact-release CI: six successful jobs. Nineteen release assets verified against Git bytes. | Scientific competence, a migrated resident deployment or a new-machine installation |
| Numerical research | Softmax Collapse/Cancellation reconstruction, repair comparisons, independent numerical checks and broken controls | Reproduction of all paper training outcomes, unknown-gap discovery or universal numerical protection |
| Transfer | Independent HPAF metric-repair lifecycle and replay evidence | General scientific transfer or self-generated improvements to the improver |
| Models | Historical ScienceRSI S4: 13/15; S7: 17/20. Separate Qwen 27B development pilot: 15/15 known short S4 cases, zero invalid formats. | A matched model comparison, long-context qualification or scientific adjudication authority |
| Self-check and recovery | Bounded recovery contracts and disposable-service crash/recovery controls | Production model-service migration, logon/reboot acceptance or a clean 24-hour observation |
| Recursive loop | Execution, provenance, checking and update-governance components exist | A demonstrated EIDOS-generated C0 -> C1 -> C2 scientific-improvement campaign |

Read the scoped evidence in [RSI readiness](RSI-READINESS-2026-11-01.md),
[functional completeness](FUNCTIONAL_COMPLETENESS.md),
[model authority](MODEL-TASK-QUALITY.md),
[model capacity and pilot](LOCAL-MODEL-CAPACITY-2026-11-01.md), and the
[published baseline](https://github.com/Computational-social-science/Eidos/releases/tag/v0.4.10).
The release verification is a publication-time observation; later documentation
commits may advance `main` without changing the frozen tag.

**Decision:** retain supervised operation. Treat bounded scaffold-level RSI as
an experimental objective. Autonomous scientific RSI remains unproven; the
current evidence does not establish that it is impossible either.

Execution has started with a public numerical-oracle calibration and a C0
specification. See the [dated execution record](RSI-EXECUTION-2026-11-01.md)
for measured results and remaining gates; no model or sealed-task result is
implied by this checkpoint.

## 3. Why extended development left important defects

These are evidence-backed failure patterns, not an attribution of every defect
to model size.

| Failure pattern | Concrete observation | Required change |
|---|---|---|
| Capability declarations substituted for execution | Registered models and agents were discussed as if scientifically qualified; the actual orchestration is deterministic chains | Every capability claim needs a task, acceptance result, scope and expiry/change condition |
| Local tests missed real boundaries | Tracking could write to the wrong run/store; verification age was confused with experiment age | Test real identities and user paths, including changed inputs and deliberately broken controls |
| Verification instruments were fallible | The layout gate reported a false text collision and missed genuine parent-text collisions | Validate evaluators using independent observations and positive/negative controls |
| Reviewers shared assumptions | LLM implementation/review could agree on a faulty diagnosis | Use executable references, sealed tasks and domain review; role separation alone is insufficient |
| The central mission was underspecified | More tests, agents and polished reports did not answer whether the system improves its research procedure | Freeze an operational RSI claim and evaluate it directly |
| Source, package and runtime claims were conflated | Qualified source coexists with legacy resident processes | Record source/package/loaded-process identities separately; migration needs its own evidence |
| Resource and model quality were confounded | Larger local models were initially undercounted; Qwen admission failures preceded a successful bounded pilot | Distinguish resource admission, runtime failure, task error and unqualified scope |
| Scope grew faster than acceptance | Delivery, monitoring, models and presentation expanded together | Pause unrelated feature growth until one measured improvement loop is complete |

The practical implication is to change what development optimizes: verified
research outcomes and credible improvement attribution, rather than test count,
model size, feature count, role count or dashboard color.

## 4. Minimum architecture: reuse components, add one finite loop

| Responsibility | Existing component to reuse | Missing acceptance work |
|---|---|---|
| Consumer definition and execution | `framework/project.py`, project registries | A declared improvement-task consumer with complete inputs and outputs |
| Independent numerical checks | `framework/stable_numerics.py`, `framework/reproduction/`, `framework/verifiers/` | New mechanism families, independent references and explicit backend qualification |
| Claim/evidence handling | `framework/validity/`, `framework/provenance.py`, `framework/artifacts.py` | A candidate-to-evaluation binding that rejects stale or substituted evidence |
| Experiment identity | `framework/tracking/` | Complete candidate/search cost, parent identity, failures and human interventions |
| Process lifetime | `framework/subprocesses.py`, existing owned-process machinery | Separate candidate/evaluator access boundaries; lifetime ownership is not a hostile-code sandbox |
| Delivery | `framework/quarto_bridge/`, executable-package support | An independently replayable campaign report with all adverse outcomes |
| Operational continuity | `framework/recovery.py` and existing monitor | Preserve self-check, bounded self-healing, Startup and manual recovery |
| Promotion concepts | `framework/updates.py`, `docs/UPDATES.md` | A separately specified research-procedure promotion contract; dependency pin promotion is not scientific promotion |

Add an on-demand, finite campaign through existing chain/consumer conventions.
Do not assume a new agent-graph framework or another always-running research
daemon is required. No new CRON research tasks are proposed.

The release is an infrastructure baseline, not an already implemented C0
improver. Specify C0 first, then implement a minimal fixed procedure after G1:
read an allowed target and development feedback, request bounded model-authored
changes, execute candidates through the registered runner, select using the
development evaluator and return the best admissible candidate plus the complete
attempt record. No unrecorded external developer repair is part of that procedure.

The initial candidate may change only an explicitly declared subset of prompts,
retrieval rules, diagnosis/proposal strategy and bounded research helper code.
The evaluator, sealed answers, acceptance thresholds, permissions, resource
limits, receipts and promotion decision are outside that writable subset.

Evaluator changes require a separate reviewed version, old/new bridge runs and
a new campaign declaration. A candidate cannot improve its score by editing its
judge. Instruction text alone is not an access-control boundary: sealed answers
must not be mounted into the candidate environment, and the evaluator runs
under separate access with a narrow result interface.

## 5. Turn the Softmax case into a reusable capability

Reuse the existing Paper2Agent conversion under `reference/barron2026_agent`
and `reference/reproduction/barron2026/mcp`. Do not create a duplicate agent.
The published case is development material, not a sealed novelty test.

Build a versioned mechanism capsule containing:

- The causal mechanism and the conditions under which the failure occurs.
- A minimal broken implementation and an explicit repair with applicability limits.
- Before/after loss and gradient comparisons against an independent reference.
- Counterexamples where an unnecessary or incorrect repair damages valid behavior.
- Dtype, backend, teacher/student equality and extreme-logit boundaries.
- Executable rejection controls, source attribution and reusable check interfaces.

Qualification must probe the actual execution path. Finite loss, finite gradients
or probabilities summing to one are insufficient. Include relative-gradient
checks without an absolute floor that hides small reference gradients. AMP,
bfloat16 and higher-order backward remain unqualified until separately tested.

Then test transfer: can EIDOS recognize a related but unseen numerical defect,
design a discriminating experiment, implement a valid repair and avoid changing
a correct implementation? Split by mechanism and provenance, rather than merely
changing a seed or paraphrasing an already seen case. HPAF is a useful second
development case; it is already exposed and cannot become a fresh holdout.

Successful transfer supports a bounded capability claim. Discovering a genuinely
new scientific gap additionally requires source comparison and domain review;
repairing a known-paper example does not establish novelty.

## 6. Qualification and causal evaluation protocol

### 6.1 Separate development, selection and sealed confirmation

Create development tasks for tuning, validation tasks for candidate selection,
and independent sealed confirmation batches B1 and B2. Keep task-family and
source-provenance separation. Archive exposure and evaluator-call histories.
Retire a confirmation batch after its outcome has informed development.

Use deterministic references where possible, such as independently implemented
high-precision numerical calculations or the existing C++/exhaustive HPAF
references. For experimental design, citation entailment and novelty, require
an independently prepared rubric and qualified human adjudication of disputed
cases. Another prompt or another instance of the same model is not ground truth.
Unknown pretraining contamination cannot be ruled out merely by hiding local files.

An initial corpus target is 60 valid and 60 invalid independently curated task
units, with fresh disjoint confirmation batches sized after pilot estimates.
This is a proposed pilot target, not an adequate sample size for every claim.
Variants sharing one underlying failure mechanism are clustered observations.

### 6.2 Measure the mission and report uncertainty

Report invalid-claim acceptance, missed defects, valid-case rejection,
abstention/coverage, source entailment, executable repair success, transfer,
wall-clock latency, total compute/tokens and human intervention time. Preserve
per-family results. An always-rejecting system must not pass on low false
acceptance alone.

For zero false acceptances in n independent representative invalid cases, the
one-sided 95% binomial upper bound is `1 - 0.05^(1/n)`: approximately 4.87% for
60 cases, 2.95% for 100 and 0.994% for 300. At least 299 such zero-error cases
are needed to put that bound below 1%. Clustering, adaptive selection and
distribution shift weaken this interpretation. A small clean pilot does not
justify autonomous scientific authority.

After development estimates, preregister task-specific safety/validity gates,
minimum useful gain, coverage constraints, uncertainty method and required
sample size before opening B1 or B2. Use paired comparisons and account for
task-family clustering and repeated selection. Do not tune thresholds after
seeing confirmation results or hide validity failures in a composite score.

### 6.3 Attribute improvement to the procedure

Compare against a frozen parent and a fixed seed improver with the same total
budget. Count failed proposals, search calls, evaluator calls, retries, model
loading, tool execution and human help. Predeclare equivalent stopping rules.
Separate one-time development costs from per-campaign costs and report both.

Keep model weights, quantization and inference settings fixed in the first
campaign. Ablate procedure changes versus added knowledge and versus a model
upgrade in separate comparisons. More compute, a stronger external model or
additional human repair must not be credited to recursive improvement.

The proposed minimum recursive experiment is:

1. C0 generates a candidate procedure C1 using development/selection feedback.
2. Lock C1, then compare C1 and C0 on fresh confirmation batch B1.
3. Use accepted C1 as the active improver to generate C2 without access to B2.
4. Lock C2 and measure its downstream gain over C1 on fresh B2 tasks. Treat
   this as task-performance evidence, separate from improver-effectiveness evidence.
5. For improver effectiveness, give C0 and C1 the same frozen starting artifact
   A, permissible task context, feedback/exposure history H and total budget B.
   Include a frozen copy of C1 as a target: C1 must improve its own procedure,
   and the C0 control must try to improve that identical target. Only the
   improver implementation differs. C1 remains locked as it was before B1;
   neither branch receives B1 answers or post-B1 human tuning. Lock both
   resulting successors before evaluating them on the same fresh sealed outcomes.
6. Repeat these paired improvement opportunities across preregistered targets
   and seeds, with identical search/selection opportunities within each pair.
   Estimate uncertainty by independent task family; a single fortunate C2 is
   not an estimated improvement rate.

The procedure estimand is the paired difference between
`V(Improve_C1(A, H, B))` and `V(Improve_C0(A, H, B))`, where V is the same
independent sealed evaluation for the pair. It differs from `V(C2) - V(C1)`.
This matched branch prevents a stronger starting artifact, additional task
exposure or extra search from being mistaken for a better improver. Separate
outcome batches are required when an earlier result has informed a later choice.

Passing two generations would support a bounded recursive-procedure result
under this local operational definition. It would not prove indefinite progress,
accelerating intelligence or general scientific autonomy. If C1/C2 improve only
task answers, classify the result as ordinary task improvement.

## 7. Local model and hardware strategy

Use the current project's environment for framework work. Keep CUDA research
execution separate and record the actual interpreter. Do not infer availability
from an old installation registry or interchange bare `python` with `py -3.14`.

The dated capacity record identifies an i9-13900K, about 128 GiB RAM and an RTX
4070 with 12,282 MiB VRAM. The separately hashed Hermes Qwen 27B file occupies
16,464,440,224 bytes, exceeding total VRAM even before runtime memory. Partial
CPU/GPU offload is therefore relevant. Its observed 2.31-2.67 generation tokens
per second is a shared-system pilot measurement, not an optimal throughput limit.

| Candidate | Proposed use in qualification | Current authority |
|---|---|---|
| Hashed local Qwen 27B artifact | Primary candidate for grounded reasoning, experiment design and repair | Development-pilot evidence only; no scientific gate authority |
| ScienceRSI-8B | Baseline and additional objections | Historical short-task errors retained; no scientific gate authority |
| StartLux decision model | Existing bounded typed routing | Routing calibration does not transfer to scientific judgement |
| Other installed larger/MoE models | Evaluate only if a measured capability or cost gap justifies it | Presence alone gives no qualification |

Tune resource profiles on development tasks, starting with measured 4k/8k
contexts, then freeze a feasible profile for confirmation. Record artifact,
tokenizer/chat template, engine, prompt, context, thinking mode, seed, GPU layers
and decoding settings. An advertised 262k context is not a tested local capacity.

Queue heavy inference and GPU experiments with measured headroom and declared
resource windows. Retain the resident service unless a separately authorized
migration is completed. Record admission failure, resource abort, timeout,
malformed output and scientific error separately; also report end-to-end task
completion so infrastructure failures cannot disappear from reliability metrics.
Set realistic output budgets and deadlines before evaluation.

A stronger hosted reference may be an optional separate comparison if budget
and data-use permissions permit. It is not a prerequisite silently imposed by
this plan, and its assistance must be attributed.

## 8. Execution roadmap and acceptance gates

Timeboxes are planning estimates in working days, not delivery promises. Gates
determine progression. Owners below are responsibilities, not claims that extra
staff or independent reviewers are already assigned.

| Phase | Estimate | Work and proposed outputs | Exit gate |
|---|---|---|---|
| P0: mission and ownership | 1-2 days | Capability charter; requirements/evidence ledger; frozen C0 specification; source/package/runtime identity record; explicit model and compute budget | G0: one falsifiable improvement claim, defined writable scope and an evaluator owner |
| P1: independent evaluation | 3-5 days | Mechanism capsules, development/validation/sealed manifests, independent oracles, baseline model/task results | G1: evaluator passes broken controls; sealed access and contamination history verified; baseline/error/coverage/cost recorded |
| P2: one finite campaign | 5-10 days | Implement and freeze minimal C0; candidate record, isolated execution, immutable evaluation binding, promotion/rollback rehearsal, reproducible campaign report | G2: a real candidate completes every transition; evaluator edits, stale receipts, missing provenance and over-budget runs cannot promote |
| P3: recursive comparison | 5-10 days | Preregistered C0/C1/C2 comparisons, matched C0/C1 improvers on identical targets/history/budgets, fresh sealed outcomes and ablations | G3: downstream and improver-effectiveness gains separately meet frozen validity/coverage/cost criteria; no unsupported RSI claim if either result is null |
| P4: research transfer | 5-10 days | One independent research consumer, followed by another if the first passes; replayable report and data/code/config lineage | G4: end-to-end transfer and source fidelity independently checked; novelty reviewed separately |

Research owner: selects scientific objectives and accepts critical design/novelty
decisions. Maintainer: implements bounded changes and preserves operational
capabilities. Independent evaluator: controls sealed tasks and adjudication.
Until that evaluator responsibility is actually assigned, autonomous scientific
qualification and a claim of independent RSI acceptance remain blocked. Software
preparation and supervised development can proceed.

First 48-hour work queue:

1. Freeze the current release as infrastructure evidence and specify the minimal
   C0 improver separately. Document which running processes actually load the
   release. Keep pending migration explicit; isolated research preparation can
   continue without stopping legacy services.
2. Specify one first task: transfer a numerical check-and-repair procedure to a
   new mechanism family while preserving correct controls. Freeze the comparison,
   allowed changes, resource limits, attribution rules and expected artifacts.
3. Assign independent evaluation ownership and prepare separate development and
   sealed-task manifests. Do not generate the sealed answers in the candidate's
   chat or accessible working tree.
4. Run a matched development baseline for Qwen 27B and ScienceRSI where the
   artifacts are available; record real source/code reasoning, correction,
   abstention and latency. Historical 13/15 versus 15/15 is not this comparison.
5. Convert the existing Softmax case into the mechanism capsule and verify both
   broken and correct controls. Add the finite campaign only after G1 is met.

Operational migration is a parallel deployment requirement, not a reason to
declare the scientific experiment passed or to remove self-healing. Earlier
stop/restart actions were rejected by automatic approval review with `blocked
by policy`; no more specific reason was provided. They were not bypassed.
See [scheduling policy](SCHEDULING-POLICY.md).

## 9. Evidence records and promotion rules

Proposed campaign artifacts, to be implemented after the protocol is frozen:

| Artifact | Required contents |
|---|---|
| Campaign declaration | Requirement IDs, operational claim, task families, split manifest hashes, preregistered analysis, thresholds, budgets and owner |
| Candidate record | Candidate/parent IDs, exact diff and source digest, change scope, model/runtime identities, seeds, data/config versions and human/external assistance |
| Execution receipt | Actual loaded inputs, outputs/digests, time/resource use, tool calls, adverse events and terminal status |
| Evaluation receipt | Frozen oracle/version, task-manifest and candidate binding, per-task outcomes, controls, uncertainty and evaluator identity |
| Promotion record | Parent/candidate, all hard-gate results, decision, approver, rollback target and deployed identity |
| Campaign report | Every attempted candidate, total costs, null/adverse results, transfer limits and replay instructions |

These are record requirements, not existing CLI/API names. Secrets and sealed
answers must not be copied into public receipts.

REQ-01: A candidate cannot promote itself or alter its evaluator.

REQ-02: Missing, stale, malformed or mismatched evidence means UNQUALIFIED/ERROR,
never PASS. A resource abort is retained, not silently retried until a good score.

REQ-03: Existing accepted capabilities, self-check and bounded recovery must
remain available. A documented rollback must restore the previous procedure.

REQ-04: Software qualification, scientific validity, scientific novelty and live
deployment acceptance remain separate decisions.

REQ-05: Accepted findings and rejection lessons are filed in the current project
wiki when present, with provenance and applicability limits. Retrieval success
is tested on future tasks; filing alone is not capability promotion.

REQ-06: Final reports include honest before/after comparisons, uncertainty,
methods and reproducible artifacts. Publication-style figures and technical
format checks do not substitute for scientific review or journal acceptance.

## 10. Stop rules and decision review

Stop a candidate immediately for attempted evaluator/answer access, invalid
provenance, exceeded hard budgets, unsupported promotion or an unresolved
regression in an accepted capability. Preserve the record and classify the
failure before proposing a new run.

After two preregistered campaigns without a useful held-out gain, pause feature
expansion and diagnose the bottleneck: seed competence, evaluator validity,
task difficulty, resource feasibility or search strategy. Do not rescue the
claim by changing confirmation thresholds, hiding failed candidates or relabeling
development cases as independent tests.

At approximately 30 working days, review the evidence accumulated rather than
assuming all phases have finished:

- If G1/G2 fail, retain EIDOS as supervised research infrastructure and repair
  the specific failed contract.
- If task performance improves without improvement-procedure evidence, report
  bounded task/procedure optimization and continue supervised use.
- If G3/G4 pass under the frozen protocol, report a bounded scaffold-level
  recursive-improvement result with its task, resource and human-support limits.
- Do not advertise general autonomous scientific RSI without substantially
  broader, independent scientific evidence.

## 11. Primary research context

- [Self-Taught Optimizer (STOP), v3](https://arxiv.org/abs/2310.02304v3): a seed
  improver improves its own code using a fixed LM and is evaluated on downstream
  tasks; the authors explicitly limit the full-RSI interpretation.
- [Darwin Godel Machine, v3](https://arxiv.org/abs/2505.22954v3): agent-code
  self-modification, empirical benchmark evaluation and an archive of agents.
  Coding benchmark gains do not establish autonomous scientific discovery.
- [Goedel Machines, v5](https://arxiv.org/abs/cs/0309048v5): a theoretical
  proof-based self-rewrite construction conditional on its formal setup and
  provable utility. EIDOS does not implement or inherit that guarantee.

The architecture and gates in this document are EIDOS-specific proposals
informed by these precedents and the local evidence. They are not a claim of
consensus that two generations prove RSI or that bootstrap alone creates it.
