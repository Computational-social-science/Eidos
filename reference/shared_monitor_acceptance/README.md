# Shared worker acceptance — unreleased development

Stable EIDOS remains 0.4.12. This profile develops explicit `observe`/`enroll`
operations and source-monitor aggregation for independent project environments.
It does not deploy or restart the existing monitor at port 8765.

The first [protocol record](recorded_trials/protocol-v1/acceptance.json) and
[raw manifest](recorded_trials/protocol-v1/manifest.json) retain 47 payloads from
the initial scoped candidate. Its wheel is
`c380014e39a127e38f02f720cac8ddee71ccbd2b80a0034a6cc69538dafcfe50`.
It qualified two actual same-host Linux installed venv entries, distinct project
identities and rejection of a resolved-to-system-Python launch. Source-focused
Windows tests and coverage have their own raw records. It does not qualify later
metadata validation, aggregation or UI changes; those need a new candidate.

Current development adds bounded asynchronous observation, separate effective
science and transport states, removal/runtime/input invalidation, registration
failure isolation and escaped dashboard cards. Synthetic positive and negative
scientific fixtures establish orchestration behavior, not empirical research.
The [integration-v2 record](recorded_trials/integration-v2/acceptance.json) and
[141-payload manifest](recorded_trials/integration-v2/manifest.json) bind current
wheel `63a5af9706b5370cc934c23c1fbac86933dfc2f3aca171b8f63f2d0378751c98`.
Two native Windows measurements include distinct installed prefixes/dependency
sets, source-monitor HTTP and real Chrome desktop/mobile controls. The public
parameterized entry passes in a fresh Unicode/spaced workspace. Linux installs
the same wheel offline into two venvs, exercises the source collector, rejects
a real FIFO registration and retains the blocked-read counterfactual. The old
profile remains immutable. No profile in this directory constitutes a 0.5.0
release, independent-machine acceptance, production migration or scientific RSI.

The source control monitor and installed project workers have different deployment
boundaries. Installing the SDK wheel does not install this repository's complete
monitor, Quarto/TeX, models or scientific data. The observer never invokes a
research gate; explicit project execution and scientific acceptance remain
separate operations. The default path needs no paid model API or service key.

## Native Windows replay

Use a dedicated controller environment matching the source checkout's frozen
development/tracking/verifier/browser dependencies, with installed Chrome or
the documented Playwright fallback. The controller uses this repository's
dashboard and synthetic fixtures. This setup is acceptance tooling, not a new
prerequisite for normal project CLI use. A source archive and an installed
monitor package are different products.

From the matching checkout, substitute actual paths:

```powershell
$controllerPy = '<controller environment>/Scripts/python.exe'
$acceptanceRoot = '<dedicated new workspace>'
$profile = 'reference/shared_monitor_acceptance/recorded_trials/integration-v2'
$candidateWheel = (Resolve-Path "$profile/input/eidos-0.5.0-py3-none-any.whl").Path
$lockedRequirements = (Resolve-Path "$profile/input/core-requirements.txt").Path
foreach ($arm in @('a','b')) {
  uv venv --seed --python 3.12 "$acceptanceRoot/env-$arm"
  $workerPy = "$acceptanceRoot/env-$arm/Scripts/python.exe"
  uv pip install --python $workerPy --require-hashes -r $lockedRequirements
  uv pip install --python $workerPy --no-deps $candidateWheel
}
uv pip install --python "$acceptanceRoot/env-b/Scripts/python.exe" sympy==1.14.0 mpmath==1.3.0
& $controllerPy reference/shared_monitor_acceptance/check.py --source . --workspace $acceptanceRoot --wheel $candidateWheel
```

Public dependency bootstrap may download packages. The Windows run was not
network-denied; do not infer an offline Windows claim from cached setup. The
separate Linux run explicitly disables networking and binds its prepared wheel
cache. The public driver refuses optimized execution and any existing managed
project/control/results targets before fixture writes. Preserve failed attempts
and use a new workspace for another measurement. It serves only an owned
ephemeral localhost port and closes its HTTP/browser/observer resources; it
does not run the production sampler, scheduler or recovery entry points.

## Completed source audit and adapter entry

The separate `recorded_trials/source-audit-20261103` profile freezes the terminal
source audit: 1,309 tests passed, six skipped, 77% whole-framework coverage,
ten chains passed and one skipped, with unchanged source/distribution identities.
It does not retroactively change either installed-worker profile.
`agent-tool-smoke.json` records selected installed CLI operations underlying the
thin instruction adapter, not live Agent/model behavior.

This branch is not a published release: release-integrity checking still refuses
the development-version/stable-history mismatch. Controller packaging, production
migration and the full downstream repair/release/replay loop remain open.

## Current probe-fix source checkpoint

`recorded_trials/integration-probe-fix-v3` qualifies the current native Windows
worker/source-controller/browser replay with wheel SHA256 `57f7e6481aa7f706420e3a45ba3052a10c43da58050435167dadfce99cc94b2c`.
`recorded_trials/source-audit-probe-fix-20261103` retains the renewed 1,317-pass,
six-skip, 77% source audit. Earlier profiles remain historical. The current
availability repair has Windows installed old/new controls in
`reference/inference_probe_acceptance`; its Linux qualification remains open.
Copy mode is required for mutable failure-injection isolation; default uv
hardlinks are not file-level independence. No production migration is claimed.
