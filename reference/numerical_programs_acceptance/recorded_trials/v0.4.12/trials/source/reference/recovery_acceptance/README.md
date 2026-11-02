# Disposable service recovery checker

Run from a configured Eidos source checkout:

```sh
python reference/recovery_acceptance/check.py --out .scratch/recovery-live.json
```

The standard-library HTTP fixture uses an ephemeral loopback port and private
temporary state. The parent contains all fixture descendants, verifies cleanup
and checks that loaded modules match fingerprinted source. Thirteen controls
cover actual crash/restart, verification, status/redirect failures, duplicate
refusal and Windows console visibility. Windows and Linux are the qualified
platforms. This is not an operation on existing model services.

`--fault-worker` and `--fault-worker-json list|empty|checks-null` are explicit
negative controls: they must exit nonzero and publish FAIL, including when a prior
actual PASS was deliberately copied to the selected output. `-O/-OO` is refused
before publication. Preserve normal qualification receipts separately.

See [the method and before/after record](../../docs/RECOVERY-ACCEPTANCE.md) for
scope, replay of the old source and remaining runtime acceptance.
