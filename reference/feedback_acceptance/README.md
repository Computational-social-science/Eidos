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
