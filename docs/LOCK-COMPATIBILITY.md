# Original experiment locks and delivery compatibility

The original Softmax matrix lock remains at its recorded canonical SHA-256
`e99760dc7a5756aa08ef06433caa81d66d559112d3f8a9401b15d2e15db96c5e`.
Training evidence, protocols and source digests are not rewritten for a new
framework release.

The tracking repair raises the local project's MLflow/DVC minimum declarations.
The frozen third-party package records remain unchanged, but the original
version-only lock comparison correctly refuses these extra metadata differences.
That strict `historical_lock_matches` contract remains unchanged.

The matrix verifier explicitly opts into a separate attestation under
`eidos.tracking-minima-frozen-resolution.v1` when strict comparison fails.
It requires the authenticated original snapshot and permits only:

- the local editable Eidos three-part release version;
- the four existing `mlflow`/`dvc` requirement specifiers under `tracking` and
  `all`, with exactly the reviewed old-to-new minimum pairs;
- ordering changes in root/package `resolution-markers` arrays, with every
  literal and its multiplicity preserved.

Every frozen candidate of a changed requirement must satisfy both old and new
constraints and carry a registry identity and hashed artifacts. Requirement
identities/order and all remaining TOML fields use typed equality. Missing or
duplicate requirements, excluded conditional candidates, altered pins, graph
edges, sources, artifact hashes, marker literals, ordinary list order and schema
types are refused.

The generated matrix delivery includes `original-experiment-uv.lock` and
`delivery-lock-compatibility.json`, with original/delivery canonical and raw
digests, the policy identifier and the complete permitted-difference list.
The verifier bundle retains the hash-addressed original snapshot as well.

This establishes unchanged frozen third-party resolution under a named policy.
It does not claim identical runtime metadata behavior, a future re-resolution,
new training, or cross-machine scientific equivalence. Saved-model CPU checks
and recorded CUDA acceptance retain their separate scopes. The report continues
to show every unfavorable result.
