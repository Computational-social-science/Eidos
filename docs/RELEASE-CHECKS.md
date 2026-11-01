# Release checks and external directory attribution

Version 0.4.10 corrects an overbroad submission check: an external directory
named `tmp`, `p2a` or `stage_*` does not by itself establish that Eidos created
it. Moving unrelated files to make a commit green is not a valid repair.

`python tools/audit_stray.py --json` still inspects the project's parent and,
on Windows, its drive root. It visits only top-level directories and never
modifies their contents. The report distinguishes:

- **Exit 0 / PASS:** no attributable blockers; generic scratch/colon names and
  valid ownership markers for other projects remain visible warnings.
- **Exit 1 / FAIL:** an exact mangling of the current absolute project path,
  the reserved Eidos scratch namespace, or an explicit marker for this project.
  Namespace findings are policy violations, not proof of who created a file.
- **Exit 2 / ERROR:** incomplete inspection or invalid explicit ownership
  metadata. Missing or unreadable inspection roots cannot become a clean scan.

The optional `.eidos-owner.json` marker is inspected in every top-level
directory, including ordinary names. It contains exactly `schema` and an
absolute `project_root`; schema must be `eidos.scratch-owner.v1`. Path comparison
uses resolved platform path rules. Duplicate keys, broken JSON, relative paths,
wrong types, symlinks and oversized markers are rejected. A valid marker for a
different checkout takes precedence over a namespace guess. Markers are local
attribution metadata, not cryptographic proof or protection against a malicious
local writer.

The pre-commit hook shows nonblocking warnings and reports attribution/errors
without recommending deletion or moving unowned files. Project scratch output
still belongs under `.scratch/`; lack of an ownership marker is not a general
permission to write elsewhere. An unmarked generic spill can only be reported
as unattributed by this bounded retrospective check.

Regression evidence: thirteen new failure-path/CLI cases fail on the previous
implementation; the initial seventeen stray-check tests pass after repair. Four
additional controls cover nonregular/oversized markers and entry metadata errors.
The final Windows run has twenty passes and one POSIX-only FIFO skip; an actual
network-disabled Linux container passes all twenty-one cases. The controls
include preservation of a shared file, a project marker under an ordinary name,
a foreign marker, malformed markers, missing/unreadable inspection and the
Windows path-mangling predicate. Nonblocking opening and regular-file descriptor
checks prevent FIFO markers from hanging the check. The original generic-name
detector remains.

This check does not replace full tests, chain checks, numerical acceptance,
installed-package replay, artifact inspection or exact-commit CI. Source
qualification, installed-wheel qualification and live process migration retain
their distinct evidence scopes. A GitHub release must publish the inspected Git
bytes, with source version, release history, delivery assets and exact-commit CI
in agreement; a locally updated version number alone does not establish release.
