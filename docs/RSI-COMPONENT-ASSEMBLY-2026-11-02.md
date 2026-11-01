# EIDOS RSI component assembly: free local reuse first

Status: evidence-backed selection and integration proposal, 2026-11-02.
No new framework, weights, paid service or full literature store was installed
for this assessment. Repository inspection is not runtime qualification.

## Decision

Use a small composition: **existing Paper2Agent artifacts + source-grounded
retrieval informed by OpenScholar + bounded search informed by ERA + EIDOS's
independent executable evaluators**. Keep the present orchestration, provenance,
reporting and self-check/self-healing infrastructure.

The user requires free reuse: the default research path must work with local
models and without Gemini, another paid model API, a subscription or a mandatory
service credential. Public code alone does not satisfy this requirement. Compute,
electricity and storage still have costs. A remote endpoint with an
OpenAI-compatible protocol can be local; the protocol does not require OpenAI.

The [decoder study](RSI-C0-DECODER-STUDY-2026-11-02.md) gives the immediate reason:
both tested local models produced admissible syntax but failed all 23 joint
loss/gradient development points. The next intervention should supply verified
methods and bounded counterexample feedback. More agents or a prestigious
publication cannot substitute for a measured gain.

## Main-journal shortlist

Dates below identify the publisher's online publication date where verified.
This is a targeted selection, not an exhaustive claim about the newest paper
in every field. Nature-family journals and Science-family journals are not
silently counted as the two flagship journals.

| Priority | Resource and publication | Reusable contribution | EIDOS decision under free reuse |
|---|---|---|---|
| P0: reuse | **Paper2Agent**, Nature, 16 September 2026. [Paper](https://www.nature.com/articles/s41586-026-11044-y), [official code](https://github.com/jmiao24/Paper2Agent) | Paper/code/workflow resources exposed through tested MCP tools | Reuse the existing Softmax conversion; qualify each invoked operator. Do not create a second agent for the same paper. Conversion-time coding-agent requirements must not become runtime requirements for a generated tool. |
| P0: adapt | **OpenScholar**, Nature, 4 February 2026. [Paper](https://www.nature.com/articles/s41586-025-10072-4), [official code](https://github.com/AkariAsai/OpenScholar) | Passage retrieval, reranking and cited synthesis | Build a local, curated method library first. Borrow retrieval/evidence contracts; stock dependencies and large public datastore are not approved for the core environment. Local model integration still needs acceptance. |
| P0: adapt | **ERA**, Nature, 19 May 2026. [Paper](https://www.nature.com/articles/s41586-026-10658-6), [official code](https://github.com/google-research/era) | Metric-driven code mutation and tree search informed by external research ideas | Reuse the search pattern with a local proposal adapter. The official example requires a Gemini API key, so it cannot be used unchanged as EIDOS's default. |
| Conditional: biomedicine | **Biomni**, Science, 2026. [Paper](https://www.science.org/doi/10.1126/science.adz4351), [official code](https://github.com/snap-stanford/Biomni) | Biomedical tools and reusable methodological know-how | Consider individual tools only when a biomedical consumer needs them. The repository exposes local-provider options, but each dependency, dataset and tool must pass a no-paid-service execution check. |

Paper2Agent's reported reproduction capability does not independently establish
the scientific validity of a new analysis. Existing EIDOS artifacts are present
at `reference/barron2026_agent/` and
`reference/reproduction/barron2026/mcp/`; their presence does not qualify every
possible invocation. The publication is an additional reason to strengthen the
existing conversion's contracts, not evidence that EIDOS already has RSI.

OpenScholar's published evaluation concerns literature synthesis. It does not
qualify its 8B model for numerical repair. Start with 20-50 explicitly selected,
redistributable sources and local passage search; do not download its full
45-million-paper datastore. A simple local retrieval baseline can precede
embedding/reranking. Call such a subset an EIDOS adaptation, not a reproduction
of OpenScholar's full results.

ERA is especially relevant to the current one-shot failure. However, search
improves a candidate only when its metric is trustworthy. Keep candidate code
outside the evaluator's write permissions; account for every rejected attempt,
timeout and model call. An externally implemented search adapter is engineering
bootstrap, not EIDOS-generated recursive self-improvement.

For Biomni, the DOI registration identifies Science and a 20 August 2026 print
date ([registration metadata](https://api.crossref.org/works/10.1126/science.adz4351)).
The publisher's full page was inaccessible during this audit; an earlier online
date was not resolved. Its README describes a release frozen on 15 April 2025
and warns that generated code has full host privileges. Do not equate this
snapshot with the complete current platform or execute its agent in the core
research environment. Its integrated resources can have separate licenses.

## Useful references that do not pass the default assembly gate

| Resource | Verified status | Decision |
|---|---|---|
| [Co-Scientist](https://www.nature.com/articles/s41586-026-10644-y), Nature, 19 May 2026 | Paper states full source is not public; prompts/pseudocode are available | Read for hypothesis comparison. Do not advertise an official open-source installation; third-party reconstructions have separate provenance. |
| [Robin](https://www.nature.com/articles/s41586-026-10652-y), Nature, 19 May 2026; [code](https://github.com/Future-House/robin) | Apache-2.0 code; README requires an Edison account/credits/key and model-provider access | Exclude unchanged runtime from the free default. Study experiment-result feedback and domain-specific workflow interfaces. |
| [The AI Scientist](https://www.nature.com/articles/s41586-026-10265-5), Nature, 25 March 2026; [v2 code](https://github.com/SakanaAI/AI-Scientist-v2) | Public source under a custom use-restricted license; API-oriented examples | Reference workflow artifacts, ablations and failure reporting. Do not label this snapshot permissive open source or adopt its full dependency stack by default. |
| [Virtual Lab](https://www.nature.com/articles/s41586-025-09442-9), Nature, 29 July 2025; [code](https://github.com/zou-group/virtual-lab) | MIT code; current README requires an OpenAI key for its default model | Optional design reference for expert discussion. Agent agreement is not an independent oracle; unchanged runtime fails the no-key default. |
| [Organon](https://arxiv.org/abs/2610.33046), submitted 17 October 2026; [code](https://github.com/cheikh025/Organon) | Recent RSI-oriented preprint, not a verified Nature/Science article. Root license not identified in inspected snapshot; Linux/DeepSeek Harness setup | High relevance for studying changes to the improvement procedure. Research-only watchlist until licensing and a local-provider path are established; no installation or RSI inheritance claim. |

ToolUniverse is already in the host skill inventory; this does not attest an
installed, authenticated Python runtime. Inspect it when a concrete tool is
needed, rather than adding another all-purpose tool catalog. No Nature/Science
flagship publication for it was verified in this assessment.

## Small operator library before another general agent

Start from EIDOS's existing dtype-preserving `expm1`, `log1p`, lazy branches and
independent Decimal checks. Add a method entry only with:

1. Paper/source identity and a versioned implementation with redistribution terms.
2. Domain, dtype, shapes, units, gradient contract and explicitly unsupported cases.
3. Executed positive controls and deliberately broken implementations rejected
   against an independent reference on the actual backend.
4. A tool signature, bounded execution policy and evidence handle the proposer
   can cite. The candidate must not modify the reference or its acceptance rule.

Use known operators to reproduce a repair first. That is a useful capability
transfer, but not a novel discovery. Test broader claims on fresh mechanism
families and keep held-out answers outside candidate access.

## Proposed first integration experiment

This is a new protocol, not a reinterpretation of the completed v1/v2 trials.

1. Freeze a keyless local provider interface: loopback endpoint or owned process,
   model/quantization hash, seed, token/time/memory limits and explicit errors.
   GPU acceleration is optional; define a smaller CPU baseline for free reuse.
   A recorded-response replay is an evaluator check, never a live-model pass.
2. Freeze a small licensed method corpus and deterministic local retrieval.
   Store passage hashes and source locations. State whether a passage contains
   the known repair; supplying that formula changes this into a reuse task.
3. Compare two procedures with the same starting target, local model, proposal
   count and total token/wall-time budget: a repeated one-shot baseline and
   retrieval plus development-counterexample feedback. Start with at most three
   proposals per procedure. Record retrieval/search overhead in the total cost.
4. Keep the public log1mexp oracle unchanged. The combined intervention cannot
   identify the separate effects of retrieval and feedback; add preregistered
   ablations only after the basic execution path works. No sealed confirmation
   answers or evaluator internals enter feedback.
5. Report syntax acceptance, joint numerical conformance, end-to-end cost and
   all failures. Before any scientific promotion, test frozen procedures on
   fresh tasks using independently owned acceptance and uncertainty analysis.

The first engineering acceptance is an actual run with no provider keys and
outbound network unavailable, including retrieval, proposal, execution, grading
and report replay. Missing local weights or tools must produce a clear unmet
prerequisite, not silently fall back to a paid provider. Reproducible bootstrap
downloads may require network initially, but must be pinned and documented.

After that, separately test whether an EIDOS-generated improvement procedure
outperforms its predecessor under matched budgets. The
[RSI optimization plan](RSI-OPTIMIZATION-PLAN.md) remains the governing claim
boundary: installed components, repaired outputs and self-healing do not alone
establish improvement of the improver.

## Inspected upstream snapshots

These are inspection pins, not installed dependencies or approved upgrades.
Recheck full license files, notices and dependency/data/model terms before reuse.

| Repository | Inspected main commit | Root license |
|---|---|---|
| jmiao24/Paper2Agent | `8c2d059165ef8cdcb70dbea76655b9c2b55b38e6` | MIT |
| AkariAsai/OpenScholar | `0e9b8fb912273d3dae39e593da86e4f6d3bf8de1` | Apache-2.0 |
| google-research/era | `012c2d3957a3a6a249af2bbeeae53bbbd2182558` | Apache-2.0 |
| snap-stanford/Biomni | `400c1f366b96a35ca253e13c9b06c5076af41d65` | Apache-2.0 |
| Future-House/robin | `4a5cce310f3bc7663a67117db88af43b84733ffe` | Apache-2.0 |
| SakanaAI/AI-Scientist-v2 | `96bd51617cfdbb494a9fc283af00fe090edfae48` | The AI Scientist Source Code License 1.0 |
| zou-group/virtual-lab | `8a3a4fd9ccc0cd297bd523751e03bc9527c91832` | MIT |
| cheikh025/Organon | `fcd1e501ee589d363766136aceb60527a0f06b12` | Not identified; do not assume permission |

Repository URLs above identify the authors' resources. Use the commit hashes
when fetching files; a moving `main` README is not an immutable specification.
