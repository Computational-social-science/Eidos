# Reproduction integrity

Version 0.4.8 repairs the three false-MATCH defects disclosed in 0.4.7.
[Installed-wheel acceptance](REPRODUCTION-ACCEPTANCE.json) records 18 case groups
and 512 oracle comparisons per OS, plus actual defect probes in the preserved
0.4.7 installation. Historical wheels and release receipts are not overwritten.

Finite integers and binary64 floats are compared as exact represented rational
values. Booleans, numeric strings, NaN/Infinity, negative/nonfinite tolerances and
nonboolean relative flags are refused. Relative tolerance uses
`tolerance * abs(expected)` without an absolute floor. Integer differences above
2**53 survive. JSON decimal fractions are interpreted as binary64, not arbitrary
precision decimal measurements. Exact error and threshold are retained as hex
numerator/denominator pairs; the convenient `delta` can be rounded or null and
does not determine the verdict. Tests include a fixed-seed, independently
implemented Decimal oracle over 512 comparisons and deliberate negative controls.

```sh
python tools/reproduction_check.py run spec.json --cwd project --out receipts
python tools/reproduction_check.py run-set bundle.json --cwd project --out receipts
python tools/reproduction_check.py show paper-id --cwd project --out receipts
```

Use argv arrays and declare `paper`, `command`, `expected`, optional `tolerance`,
`relative` and dotted `json_path`. Scientific qualification additionally requires
an original spec file, timezone-aware `registered_at`, declared integer `seed`
(or null with `seed_reason`), `data_version` and `config_version`. The command
must actually apply its seeds and versions; recording labels does not prove it.

Declare project-relative code/data/config files in `inputs`. The directly
executed Python script and present project `pyproject.toml`/`uv.lock` are included.
Module-mode Python requires explicit inputs. Imported helpers, installed packages,
remote services and undeclared data are not discovered transitively. Receipts
bind executable bytes, runner sources, working directory, original specification
and declared input bytes. Consumer snapshots require exact external paths in
`validity_external_inputs` before following dependencies outside their project.

Stdout contains one JSON result, optionally preceded by plain log lines; send
JSON-like logs to stderr. Duplicate keys, NaN/Infinity, binary64 overflow,
ambiguous multiple results and nonnumeric selected values are refused. Invalid
specs fail before execution. Missing tools, nonzero exits, timeouts, changed
inputs and malformed outputs produce UNRUN. Owned child lifetimes close
descendants; both streams are retained.

S12 recomputes values and validates current bindings. Complete bundle inventory,
order and indices must match the original file; a successful child cannot qualify
the paper without its complete parent. Legacy bare MATCH is blocked pending
replay. `show` separates stored verdict from current qualification. Atomic writes
preserve previous distinct receipts in `history/`.

These are local coherence checks over a trusted command, not signed execution
attestation, independently witnessed preregistration or proof of scientific
truth. A repository writer can replace records and source. Controlled stubs do
not reproduce paper training. The Softmax kernel/gradient evidence retains its
own scope; full paper training remains unqualified.

The three public installed-wheel checkers explicitly refuse `-O`/`-OO`; normal
run records include optimization level zero. Both operating systems retain
actual optimized-mode rejection controls, so disabled assertions cannot generate
a successful qualification document.
