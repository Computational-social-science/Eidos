# Direct SDK manuscript and figure delivery

QuartoBridge previously treated a process exit of zero as a successful render,
even with no output. It returned an outputs directory while Quarto wrote into the
manuscript directory. A controlled wrong-tool/render fixture reproduced all three
formats reporting success with no artifact. This is distinct from the project
command gate, whose declared-output checks already reject that situation.

## Current contract

`QuartoBridge.render('all')` requires HTML, PDF and DOCX. Only `all`, `html`,
`pdf` and `docx` are accepted. Each command runs in the SDK's bounded Job/process
group, with closed stdin and captured UTF-8 diagnostics. `quarto.timeout` is a
per-command deadline (default 300 seconds); `probe_timeout` defaults to 30 seconds.
These are process deadlines, not a hard real-time deadline for the entire batch.

The bridge directs each render to a new private staging directory, fixes the
primary names to `index.html`, `index.pdf` and `index.docx`, and verifies the
result. HTML needs a complete envelope and its directly referenced local assets;
remote assets and transitive CSS/network dependencies require separate browser or
offline checks. PDF uses Poppler `pdfinfo` and requires a parsed document with a
positive page count. DOCX requires a readable ZIP, valid XML roots, the internal
main-document relationship, content types and Word body. PNG figures use Pillow
verification; SVG figures require a valid SVG XML root. These are production
checks, not scientific content or journal acceptance.

Install Quarto for manuscript rendering. PDF also needs a working TeX installation
and Poppler `pdfinfo` on PATH. Missing tools never produce a successful delivery.
The selected Quarto executable must return a semantic version to `--version`.
This is a tool-availability check, not binary attestation. `QUARTO_BIN` remains the
first candidate. `no_freeze=True` requests execution and cache refresh using
supported Quarto options; execution daemons are disabled for these bounded jobs.

Only a complete requested batch is published. Result rows contain `published`,
`path`, `bytes` and `sha256`; the returned `output_dir` is where the files reside.
`render-manifest.json` records declared input and output checksums. The source QMD
and nearby Quarto configuration are bound automatically. Use `render_inputs` for
other project-relative files such as data, bibliography, code and assets. This is
an explicit inventory, not discovery of every transitive dependency. Seed, data
version and scientific conclusions still belong in the project's research record.

Publication holds one writer lock, checks portable path/receipt collisions and
refuses to overwrite declared inputs. It copies through atomic file replacements,
checks inputs and copied outputs again, then publishes the receipt last. A failed
render or publication retains the previous delivery; concurrent user edits to
inputs are preserved. Only named output files participate in rollback. Readers
must verify receipt checksums to reject a mixed concurrent read; this is not a
transactional filesystem snapshot for arbitrary readers or writers.

## Figures and programmatic manuscripts

`render_figure(script, 'svg' | 'png' | 'pdf')` executes a trusted Python/Matplotlib
script with the selected SDK interpreter and Agg backend. The script must leave
exactly one open pyplot figure. Zero-argument CLI scripts and normal Python zero
exits are supported. Nonzero exits, non-integer exit objects, zero/multiple open
figures, changed declared inputs and incomplete artifacts are refused. Output is
`outputs/figures/<script-stem>.<format>` with a checksum receipt; DPI is 600.
Declare data/helpers through `figure_inputs`. Scientific interpretation, seeds,
typography and journal style require their own checks.

`QuartoManuscriptBuilder` honors its actual manuscript directory, creates it when
building, writes UTF-8 QMD atomically and serializes metadata with safe YAML.
Tables require rectangular rows and matching headers; an omitted header still
produces a Markdown separator. Cell pipes/newlines are escaped, and captions and
reference blocks are emitted explicitly.

## Acceptance and remaining scope

The installed-wheel checker is
[reference/quarto_delivery_acceptance/check.py](../reference/quarto_delivery_acceptance/check.py).
It has controlled external-CLI cases and actual Matplotlib cases. Its optional
`--real-quarto` adds an actual Quarto/TeX three-format run from a custom manuscript
directory. These qualification modes are reported separately. The driver requires
all three physical primary formats and independently recomputes input/output
checksums; agreement between two SDK result fields is insufficient.

Other direct SDK subprocess callers, live monitor migration, reboot/logon,
clean-24-hour stability and new-machine qualification remain separate work.
Existing numerical studies retain their frozen locks and evidence.

Sources: [Quarto render CLI](https://quarto.org/docs/cli/render.html),
[execution behavior](https://quarto.org/docs/projects/code-execution.html),
[Poppler](https://poppler.freedesktop.org/).
