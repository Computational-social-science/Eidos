"""Render the public aggregate audit; never open the private source corpora."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tools import publication


def validate_aggregate(record: dict) -> None:
    """Refuse to typeset fixed-case claims from failed, changed or partial inputs."""
    expected = {"advbench_llm_perturbed_1.json": 513,
                "advbench_unicode_whitespace_perturbed.json": 520}
    if record.get("accepted") is not True or record.get("records") != 1033:
        raise ValueError("unaccepted or incomplete local audit")
    if {name: row["pairs"] for name, row in record["per_corpus"].items()} != expected:
        raise ValueError("local corpus inventory changed")
    original = record["original_engine"]
    if (original.get("actual_original_diff_runs_checked") != 1033
            or original.get("all_legacy_costs_match") is not True
            or original.get("original_code_and_data_modified") is not False
            or not re.fullmatch(r"[a-f0-9]{64}", original.get("source_sha256", ""))):
        raise ValueError("original implementation cross-check missing")
    data = record.get("data_sha256")
    if (not isinstance(data, dict) or set(data) != set(expected)
            or any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in data.values())):
        raise ValueError("private corpus hashes missing or invalid")
    qualification = record.get("qualification", {})
    required = {"ordered_pairs": 225, "legacy_control_mismatches": 40,
                "zero_control_mismatches": 210, "graph_max_length": 3,
                "graph_alphabet": "aβ", "rapidfuzz": "3.14.6",
                "backend": "rapidfuzz.distance.metrics_cpp"}
    if not isinstance(qualification, dict) or any(qualification.get(k) != v for k, v in required.items()):
        raise ValueError("independent qualification missing or changed")
    for name, mismatches, excess in (("advbench_llm_perturbed_1.json", 2, 112),
                                     ("advbench_unicode_whitespace_perturbed.json", 0, 0)):
        row = record["per_corpus"][name]
        if (row.get("legacy_mismatches") != mismatches or row.get("maximum_overestimate") != excess
                or row.get("underestimates") != 0):
            raise ValueError("per-corpus results do not support the fixed-case report")
    for name, recorded in record["source_sha256"].items():
        if name not in ("run.py", "verify.py", "protocol.json", "pyproject.toml", "uv.lock"):
            raise ValueError("unexpected source input")
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != recorded:
            raise ValueError("local audit source is stale: " + name)
    if set(record["source_sha256"]) != {"run.py", "verify.py", "protocol.json", "pyproject.toml", "uv.lock"}:
        raise ValueError("incomplete source inventory")
    cells = record["joint_cost_counts"]
    if not cells or any(type(row.get(k)) is not int or row[k] < (1 if k == "count" else 0)
                        for row in cells for k in ("count", "exact", "legacy")):
        raise ValueError("invalid aggregate cell")
    if (sum(row["count"] for row in cells) != 1033
            or sum(row["legacy_mismatches"] for row in record["per_corpus"].values()) != 2
            or sum(row["count"] for row in cells if row["exact"] != row["legacy"]) != 2
            or max(row["legacy"] - row["exact"] for row in cells) != 112):
        raise ValueError("aggregate counts do not support the fixed-case report")


def produce() -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    record = json.loads((HERE / "docs/local-audit.json").read_text(encoding="utf-8"))
    validate_aggregate(record)
    output = ROOT / "site/reports/hpaf-metric"
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Arial", "font.size": 6.5, "axes.labelsize": 7,
                         "axes.titlesize": 7, "xtick.labelsize": 6, "ytick.labelsize": 6,
                         "legend.fontsize": 6, "svg.fonttype": "none", "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 72 / 25.4))
    ax = axes[0]
    cells = record["joint_cost_counts"]
    xs, ys = [r["exact"] for r in cells], [r["legacy"] for r in cells]
    sizes = [10 + 4 * r["count"] ** .5 for r in cells]
    maximum = max([*xs, *ys])
    ax.plot([0, maximum], [0, maximum], color="#697078", linewidth=.7, linestyle="--", label="Equality")
    ax.scatter(xs, ys, s=sizes, facecolor="#c5723a", edgecolor="#352e28", linewidth=.4,
               label="Legacy cost; size encodes pair count", zorder=3)
    ax.set(xlabel="Independently checked minimum edit distance", ylabel="Legacy opcode-script cost")
    ax.set_title("a  Complete supplied corpus: 1,033 pairs", loc="left", fontweight="bold", pad=10)
    ax.text(.04, .93, "2 unequal pairs; maximum excess = 112", transform=ax.transAxes, va="top")
    ax.legend(loc="lower right", frameon=False)
    ax = axes[1]
    ax.bar([0, 1], [3, 1], width=.48, color=["#c5723a", "#3d738a"])
    for x, y in enumerate((3, 1)):
        ax.text(x, y + .08, str(y), ha="center")
    ax.set(xticks=[0, 1], xticklabels=["Legacy cost", "Minimum edit distance"], ylabel="Unit edits", ylim=(0, 3.7))
    ax.set_title("b  Benign example: aaa → abaa", loc="left", fontweight="bold", pad=10)
    ax.text(.04, .9, "Insert b once; no normalization", transform=ax.transAxes)
    fig.subplots_adjust(left=.075, right=.985, bottom=.22, top=.84, wspace=.36)
    fig.savefig(output / "figure-metric.svg")
    fig.savefig(output / "figure-metric.pdf")
    fig.savefig(output / "figure-metric.png", dpi=600)
    plt.close(fig)
    labels = {"advbench_llm_perturbed_1.json": "LLM perturbations",
              "advbench_unicode_whitespace_perturbed.json": "Unicode edits"}
    rows = "\n".join(f"| {labels[name]} | {r['pairs']} | {r['legacy_mismatches']} | {r['maximum_overestimate']} | 0 |"
                     for name, r in record["per_corpus"].items())
    text = publication.header("An exact edit-rate repair in an independent forensic project", date="2026-11-01") + f"""
## Abstract

A metric can be executable and repeatable while measuring a different quantity
from the one its documentation names. In an existing Unicode forensic project,
an edit rate described as normalized Levenshtein distance used the cost of a
`SequenceMatcher` alignment. A retrospective complete-file audit found two
differences among 1,033 paired records; the largest excess was 112 unit edits.
Separating visual alignment from minimum edit-distance calculation repaired the
metric. An independent C++ implementation agreed with all repaired distances.
Exhaustive edit graphs, deliberate wrong metrics and input-change controls bounded
the acceptance claim. This case demonstrates a metric repair and an independently
reusable verification path; it establishes neither attack success nor a new
scientific discovery.

## Metric contract and repair

The original engine used `difflib.SequenceMatcher(None, source, target)` with
default automatic-junk handling. Insertions and deletions contributed their run
lengths; replacements contributed the larger run length. This defines a valid
opcode-script cost, but Python explicitly does not guarantee minimal edits.
The contract error lies in calling that cost Levenshtein distance.

Keep the visual diff unchanged. Compute the quantitative numerator separately
using the minimum number of unit-cost insertions, deletions and substitutions.
The adapter supplies a two-row dynamic program. Preserve the original denominator:
distance divided by `max(len(source), 1)`. The resulting rate is directional and
can exceed one. Units are Unicode code points without Unicode normalization,
not bytes or grapheme clusters. Similarity ratios remain separate outputs.

## Methods: independent checks and controls

The validator uses RapidFuzz 3.14.6's explicit C++ Levenshtein backend with
weights `(1, 1, 1)` and no preprocessing. It does not import the producer's metric.
An exhaustive breadth-first edit graph checks all 225 ordered pairs over
alphabet {{a, β}} with lengths zero through three. The producer is executed on
the same 225 pairs and ten additional benign/Unicode examples. An experimental unit
here is one deterministic string-pair setting, not an independent random trial. These are finite
qualification sets, not a proof over arbitrary strings.

The graph rejects the legacy cost on 40 pairs and a zero-distance control on
210 pairs. Separate acceptance tests reject legacy-as-exact results, wrong
normalization, missing rows, Boolean distances, changed source, changed data,
missing evidence and malformed/unpaired input. Source, configuration, lock and
corpus hashes bind each execution. No seed applies to deterministic enumeration.

## Complete-file results

| Supplied corpus | Pairs | Legacy unequal | Max. excess | Repaired unequal |
|:--|--:|--:|--:|--:|
{rows}

: **Table 1.** Before/after comparison against independently calculated minimum
edit distances. Counts describe every record in the two supplied files; records
are not independent experimental replications. There is no significance test or
population inference. Maximum excess is legacy cost minus minimum edit distance.

![**Figure 1 | Separate visual alignment from quantitative distance.** **a,** Complete-file joint counts of independently checked minimum edit distance and legacy opcode-script cost for 1,033 pairs. Marker area increases with pair count; the dashed line denotes equality. Two pairs differ and the maximum excess is 112 edits. **b,** In the public benign example aaa to abaa, inserting b once suffices, whereas the legacy alignment costs three edits. All repaired local distances match the independent C++ reference. No sampling, error bars or model inference apply.](figure-metric.svg){{width=183mm}}

## Reproduction, provenance and limits

Original HPAF source SHA-256: `{record['original_engine']['source_sha256']}`.
The actual original `diff_runs` function was checked on all 1,033 records and
matched the adapter's legacy numerator. Original code and data were unchanged.
The private corpus hashes and public aggregate counts are in
[the local audit record](local-audit.json). The original raw strings and original
HTML reports are not distributed. Thus public replay independently reproduces
the 235 benign qualification pairs, not the inaccessible private corpus.

Use [the standalone case instructions](CASE.md) and [public reproduction bundle](reproduce.zip).
Install from the included lock, run `eidos-reproduce.py` in a fresh copy and inspect
its execution record. Required outputs, deliberate wrong evidence and input
invalidation are separate from a successful process exit. A report or a green
gate does not establish EIDOS completeness, scientific novelty or journal acceptance.

## Data availability

The public fixture, source, protocol, exact dependency lock and acceptance controls
are distributed in `reproduce.zip`; only newly created benign strings enter it.
Aggregate local-corpus evidence is provided in `local-audit.json`. Local original
corpora remain private; their complete-file findings cannot be independently
recomputed without authorized access. All unfavorable metric discrepancies remain
in the aggregate record. Full local replay and public-fixture replay have distinct
acceptance scopes.

## Code availability

The producer, independent validator, protocol, lock, controls and public fixtures
are in `reproduce.zip` and the EIDOS repository. HPAF's original `README.md`, line
48, supplies the metric promise; the preserved forensic engine supplies the old
implementation. The adapter repairs the metric separately without overwriting
that original project.

## Reporting and submission metadata

This technical validation report follows the shared manuscript and figure policy.
Human authorship, affiliations, funding, contributions and competing interests
remain to be completed before submission. Scientific and editorial review remain
separate; `submission_ready` is false.

## References

1. Python Software Foundation. [difflib: SequenceMatcher contract](https://docs.python.org/3.12/library/difflib.html).
2. RapidFuzz. [Levenshtein distance, version 3.14.6](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html).
3. Nature. [Research figure guide]({publication.FIGURE_GUIDE}).
4. Nature. [Formatting guide]({publication.FORMAT_GUIDE}).
"""
    legend = "**Figure 1 | Separate visual alignment from quantitative distance.** **a,** Complete-file joint counts of independently checked minimum edit distance and legacy opcode-script cost for 1,033 pairs. Marker area increases with pair count; the dashed line denotes equality. Two pairs differ and the maximum excess is 112 edits. **b,** In the public benign example aaa to abaa, inserting b once suffices, whereas the legacy alignment costs three edits. All repaired local distances match the independent C++ reference. No sampling, error bars or model inference apply."
    start = text.index("![**Figure 1")
    end = text.index("\n\n", start)
    text = text[:start] + "\n\n".join(
        f'::: {{.content-visible when-format="{target}"}}\n![{legend}](figure-metric.{extension}){{width=100%}}\n:::'
        for target, extension in (("pdf", "pdf"), ("html", "svg"), ("docx", "png"))) + text[end:]
    qmd = output / "report.qmd"
    qmd.write_text(text, encoding="utf-8")
    (output / "local-audit.json").write_bytes((HERE / "docs/local-audit.json").read_bytes())
    (output / "CASE.md").write_bytes((HERE / "CASE.md").read_bytes())
    publication.reference_docx(output, os.environ.get("QUARTO_BIN", "quarto"))
    return qmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    from framework.artifacts import output_lock
    with output_lock(ROOT / "site/reports/hpaf-metric"):
        qmd = produce()
        if args.render:
            for target in ("html", "pdf", "docx"):
                subprocess.run([os.environ.get("QUARTO_BIN", "quarto"), "render", str(qmd), "--to", target],
                               cwd=qmd.parent, check=True)
            docx = qmd.with_suffix(".docx")
            docx.write_bytes(publication.manuscript_docx(docx.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
