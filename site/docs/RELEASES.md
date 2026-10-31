# Releases

EIDOS uses the `0.x` series for initial development. The transition from legacy
`v4.3.32` to `v0.4.1` is an explicit numbering-scheme reset, not a normal monotonic
SemVer upgrade. Legacy tags and records remain intact; they do not imply mature
production compatibility. The old policy is archived in
[RELEASES-legacy-v4.md](archive/RELEASES-legacy-v4.md).

One release represents a delivered capability, measured decision change or
correction of a published claim. Routine edits ride the next release. Version
numbers do not measure research quality or count work sessions. The
[SemVer development convention](https://semver.org/#spec-item-4) permits breaking
changes during `0.y.z`; stability must be assessed from explicit contracts.

## Source of truth

`pyproject.toml` owns the source version. `tools/versioning.py` synchronizes only
the local editable package version in `uv.lock`, the README version marker and
the technical framework's implementation baseline.
The site is built from that metadata. Original scientific locks are archived
unchanged under their canonical SHA-256 in `lock/snapshots/uv/`. Scientific lock
equivalence ignores only EIDOS's local editable version; dependency pins, artifact
hashes, markers, sources, fields and TOML value types must still match.

`site/versions.json` records the version, source commit, intended tag, delivered
summary and measured state. A release record is not proof that its tag has been
pushed or that remote CI passed. The same version cannot describe another source
commit. Historical records retain their original schema.

## Procedure

1. Implement and review the deliverable. Run the appropriate scientific and
   failure-path checks. Preserve original evidence and failures.
2. Select the version once using `build_site.py --bump patch` (or an explicitly
   chosen minor/major). `--set-version` is reserved for a documented scheme
   migration. These commands also synchronize the lock and README. Failed release
   builds restore canonical metadata and generated numerical reports while
   retaining immutable historical lock snapshots.
3. Commit the verified source, documentation and deliverables locally. Do not tag.
4. Prepare metadata from that source commit:
   `python tools/build_site.py --release --summary "Concrete delivered capability"`.
   This exercises the onboarding release gate before recording the release. An
   ordinary build does not create a release.
5. Refresh self-audit, site, dashboard and screenshots as required. Run checks
   sequentially where they produce report artifacts. Re-render manuscripts after
   production-source changes; complete page inspection and publication audits.
6. Require `python tools/versioning.py --check`, the publication fingerprint check
   and repository hooks. Commit the metadata. The record's source commit identifies
   the implementation commit; the tag will identify the final delivery commit.
7. Push the commits, require green remote CI for the exact final commit, then
   create and push its annotated `vX.Y.Z` tag. Announce only the actually published
   version. A Git tag is separate from a GitHub Release, package-index publication
   or a claim of functional completeness.

Do not rewrite legacy tags, silently upgrade experimental dependencies, reuse a
version for changed source, tag a dirty tree, or bypass checks to end a session.

CI checks committed release labels/history and publication fingerprints in an
independent checkout before any build. Push the source and metadata commits
together; the intermediate local source-preparation commit is not a published
release. Local commit hooks continue to run the scientific, site and screenshot
checks, while the complete release consistency check runs at the delivery step.

A successful self-audit publication now synchronizes its measured test, skip,
coverage and chain headlines with HEALTH and the marked current summary in the
technical framework. Writes are serialized and rolled back on publication error.
Unknown coverage is not formatted as a percentage. The check-only path does not publish these records or headline documents, so CI
still detects their committed inconsistencies; measurement can write runtime/test
artifacts.
