# Scientific delivery quality

The numerical and precision/epsilon reports use `tools/publication.py` as a shared
production policy. HTML is a readable web report; PDF and Word are manuscript
deliveries. A website screenshot is not a publication master.

## Technical requirements

The [Nature figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/)
specifies 89 or 183 mm widths, height at most 170 mm, editable text and embedded
standard fonts at 5–7 pt. The current four masters use 183 mm, Arial at 6–7 pt,
embedded TrueType fonts, sequential panel letters, accessible colours and redundant
line/marker encoding. SVG font checks use the physical viewport/viewBox scale;
unsupported text transforms fail instead of borrowing a nominal CSS font size.
PNG is a Word/preview asset; editable SVG and PDF remain separately available.

The [Nature manuscript guide](https://www.nature.com/nature/for-authors/formatting-guide)
informs A4, 12 pt Times New Roman, double spacing and continuous line numbering
in PDF/Word. Figure legends define panels, units, comparison arms and statistical
units; table captions are explicit. Word keeps an image with its legend, prevents
split rows, repeats table headers and includes page-number fields. The PDF uses
one figure/table label, rather than duplicating Pandoc's automatic label.

## Scientific reporting contract

Every report must identify the source question, tested repair, methods, comparator,
experimental unit, seeds or the reason no seed applies, actual precision/device,
all specified outcomes, limitations, independent acceptance, data availability,
code availability and references. Code/data/config/environment provenance must
resolve to actual artifacts. The original paper's authors retain method credit.

The 96 deterministic numerical settings are not 96 random replicates. Three
shared training seeds are not 18 independent seed replicates in the matrix. No
population significance, confidence interval or universal generalisation benefit
is claimed. The matrix retains 5 higher, 12 lower and 1 tied fixed-loss endpoint.
Numerical correctness, stationarity and held-out generalisation are separate claims.

## Rebuild and acceptance

Use the project Python and configured Quarto/TeX runtime. Run exporters sequentially:

```powershell
python tools/numerics_case.py --render
python reference/softmax_matrix/report.py --render
```

`tools/audit_publication.py` requires `pypdf` (on this host, the bundled document
Python provides it). It measures physical figure dimensions/fonts, editable text,
PDF font embedding/A4/sections/captions and Word styles. It writes
`docs/PUBLICATION-QA.json`, including SHA-256 fingerprints of reports, masters and
production code. `python tools/check_publication_record.py` is a dependency-free
staleness check; it does not substitute for rendering or visual inspection.

For each layout change, render every PDF and Word page to PNG and inspect all
pages. On this host PDF uses Poppler; Word uses the bundled `render_docx.py` page
pipeline with a task-local, read-only Microsoft Word conversion adapter because
bundled LibreOffice is unavailable. No managed runtime files are modified.
Keep exact report hashes, page counts, renderer and inspection outcome in
`docs/PUBLICATION-VISUAL-REVIEW.json` after that inspection. The website must also
pass browser checks at desktop and narrow widths.

Directory locks cover export plus rendering, are reentrant for the same thread
and exclusive across processes, and keep release rollback from overwriting a
different writer. ZIP replacement is atomic. This is not a claim that the entire
multi-file report directory is an atomic filesystem transaction for readers.

## Submission boundary

These are technical validation reports, not an accepted Nature article. Technical
PASS does not determine novelty, suitability or editorial acceptance. Authors,
affiliations, contributions, funding and competing interests require the human
research team's confirmation. They are not fabricated. The audit therefore keeps
`submission_ready: false`. An unverified future report cannot inherit a previous
report's PASS merely by importing its styles.
