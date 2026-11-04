# Local repair lifecycle: source checkpoint

The implementation contract is in `docs/FEEDBACK-LIFECYCLE.md`. The current
`recorded_trials/source-audit-v2` profile seals the final stable-input full audit
and UI corrections. The retained `source-audit-v1` checkpoint seals its earlier audit,
focused coverage and actual failing/passing regression logs. It measures 1,363
passing tests, six skips, 77% whole-framework coverage and ten passing/one skipped
chains. The focused feedback-module coverage is 83% under its separate scope.

The unit controls include invalid transition/evidence refusal, complete receipt
validation before journal publication, project-pin locking, interrupted adoption
and reversion, rollback history preservation, fresh replay, pinned-worker closure,
stale withdrawal and publication-record consistency. Fabricated publication
records are **test fixtures**, not evidence of a real GitHub release.

Actual normal-installed console and inference caller trials are retained under
`reference/agent_naming_acceptance` and `reference/inference_probe_acceptance`.
None of these checkpoints closes the planned real originating-project campaign.
Immutable old/bad/repaired artifacts, protected evaluator, published exact-head
CI/release and originating-project adoption/replay/reversion still need their
own actual lifecycle receipts. Resident production migration and scientific RSI
remain separate qualifications. Do not reinterpret this source profile as them.

## Real producer

`campaign.py` runs from a normal candidate installation using `-I`; it never
imports an SDK from the checkout. `control-wheel` creates an explicit unchanged-
SDK negative candidate with its own version and valid RECORD. Prepare a new
workspace containing `wheels/` and independent copy-mode `env-old`, `env-bad`,
`env-new` installations using the frozen core requirements. Select the originating
project and the qualified probe driver/fixture explicitly:

```text
<env-new-python> -I -X utf8 campaign.py prepare --workspace <workspace> --project <origin> --oracle <inference_probe_acceptance/check.py> --fixture <test_inference_probe_lifetime.py>
<env-new-python> -I -X utf8 campaign.py finish --workspace <workspace>
```

`prepare` seals policy before executing old/bad/repaired artifacts and stops at
VALIDATED. It retains actual CLI refusal history and refuses premature closure.
`finish` fetches the actual public release, tag, source history, ancestry, CI and
asset bytes, then exercises adoption, failed-replay reversion and fresh replay.
An unsuccessful/unobserved post-adoption probe reverts an unqualified adoption.
Per-attempt remote directories retain partial fetches, and resume follows the
core journal state without replaying an already committed release transition.
Unknown attribution and genuine scientific negative results are not repair PASS.

Use only a dedicated explicit on-demand project selection; these operations do
not replace the resident monitor's interpreter or run a scientific experiment.
The native-origin case's scientific status remains UNRUN. No API key, model
service or paid provider is needed by this producer; publication is the ordinary
maintainer-authenticated GitHub workflow and subsequent reads are public.
