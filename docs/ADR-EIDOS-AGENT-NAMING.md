# Product naming decision: EIDOS Agent

Decision: 2026-11-03, following the user's naming preference.

Use **EIDOS Agent** as the product name. The intended public distribution is
`eidos-agent`, import namespace `eidos_agent`, and console entry `eidos-agent`.
PyPI's JSON endpoints for `eidos-agent` and `eidosagent` returned 404 at the
decision checkpoint; this is an availability observation, not a reservation.
The existing PyPI `eidos` is an unrelated astronomy distribution.

Keep the GitHub repository URL `Computational-social-science/Eidos` for now.
Preserve historical artifacts, module names and receipts exactly. Branding does
not establish autonomous reasoning, an agent graph, or scientific RSI.

## Compatibility boundary

The 2026-11-04 **0.5.0 compatibility preview** is actually published with the
additional console alias. Distribution `eidos` and namespace `framework` remain
unchanged. The GitHub wheel is the qualified installation path; a public-index
package/import migration is still open. Existing resident 0.4.12 services retain
their own runtime. See [the delivery record](RELEASE-PUBLICATION-0.5.0.json).

The prior installed SDK development evidence uses distribution `eidos`, import
namespace `framework` and console `eidos`. The new development source additionally
declares `eidos-agent` as a console alias for the same implementation. An alias
does not rename a distribution or import namespace, and the published 0.4.12
installation does not gain it from a source edit. These technical identities remain
explicit legacy compatibility identifiers in that evidence. Do not relabel its
wheels or publish that name on PyPI. A GitHub compatibility release and a future
public-index distribution are separate deliverables.

The namespace migration needs its own acceptance gate before public-index
publication: inventory active import/module/console consumers; adopt a single
canonical implementation; qualify any bounded source-compatibility bridge;
exclude the generic `framework` namespace from the new installed distribution;
verify coexistence/conflict behavior in fresh copy-mode environments; and update
worker discovery, metadata, locks, provenance and documentation together. Frozen
scientific and failure-injection records are not migration targets.

P3 first closes the software repair/release/replay bookkeeping against immutable
artifacts. Its deployment and publication evidence must state the actual package
identity in use. The product heading can change now; import/package compatibility
must be demonstrated before advertising the new `pip install` command.
