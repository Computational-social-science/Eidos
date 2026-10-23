# Referee simulation — Eidos, reviewed as if it were a paper

Three stances, as for a project: **A** (scientific method — does the framework measure
what it claims), **B** (software engineering — does it hold under CI and change), **C**
(adoption — would anyone else use it). An objection is `[RESOLVED]` only where an artefact
answers it, and the count in `analysis/CLAIMS.yaml` is parsed from these tags.

## O1. The gates measure artefacts, not arguments
`[RESOLVED]` **A**

Twenty artefact gates can pass while the central sentence is unsupported. Gate S now reads
`analysis/CLAIMS.yaml`, resolves every evidence pointer and refuses a register whose
declared unresolved count disagrees with the referee document. It found a real gap in the
first project it was pointed at (5 open objections).

## O2. No continuous integration
`[RESOLVED]` **B**

`.github/workflows/ci.yml` runs the suite on 3.11 and 3.12, then every chain, the coupling
audit, the contracts, Gate S on a fixture and the local-operator gate. Runs on `main` are
green.

## O3. The `--ci` flag could not change a verdict
`[RESOLVED]` **B**

Chains executed at import time, before argparse, so `STRICT_REGISTRY` was always strict
and the audit job failed on a checkout it had been told to tolerate. Chains are now
registered and executed in `main()`; the behaviour is pinned by a test and was verified
both ways (missing root + `--ci` → SKIP; missing root without → ERROR).

## O4. No coverage measurement
`[RESOLVED]` **B**

Coverage is now measured on every self-audit run and recorded in `docs/SELF_AUDIT.json`
(73% of `framework/` at the time of writing). A drop of more than one point fails the
self-audit check, so the number cannot quietly decay. `quarto_bridge` and `tracking` gained
resolution tests (`tests/test_bridges.py`) that pin the executable lookup without requiring
either tool to be installed.

## O5. The surrogate layer has no consumer
`[RESOLVED]` **A**

A module without a consumer is the mistake this framework already made once and deleted.
The local-operator layer ships with a consumer: `docs/OPERATOR_COMPOSITION_PREREG.md`
turns Proposition A into a fixed-point/bifurcation question, and uses exactly the
`fixed_point` / `spectral_radius` / `continue_branch` functions.

## O6. The Lean chain was never run on real proofs
`[RESOLVED]` **A**

Two runs on 2026-10-21: `lean-nhb` (`PhaseI.Selective.silent_iff_acceptedAndWrong`) in
2.7 s and the mathlib-backed `atlas-lean` (`SpernerProperty.boolean_sperner`) in 112.9 s,
both PASS with the kernel control (a file asserting `1 = 2` must fail to compile).

## O7. A pointer-based registry breaks on a fresh clone
`[RESOLVED]` **B**

`load_projects(allow_missing=not STRICT_REGISTRY)` makes an absent checkout a SKIP in CI
and an error on a developer machine; `test_missing_project_root_raises_locally_but_is_skippable_in_ci`
pins both directions.

## O8. One adopter is not evidence of generality
`[RESOLVED]` **C**

A second adopter is registered: `projects/lean_nhb` points at a Lean 4 library with no
Python, no pytest and no manuscript. `python -m framework.project check lean_nhb` returns
PASS (exit 0, 1.43 s) by mapping `lake build`'s exit code, with no special-casing for the
toolchain. The interface held without modification, which is what generality has to mean
here; a project that needed the framework changed would have falsified it.

---

**Counts**: 8 objections, 8 resolved, 0 unresolved.
