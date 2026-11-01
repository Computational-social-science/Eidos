"""Standalone installed-wheel controls for fresh SDK render/figure delivery.

Requires Poppler pdfinfo. Controlled CLI fixtures qualify the SDK boundary;
--real-quarto additionally exercises an actual Quarto + TeX installation.
"""

from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import distributions, version
import json
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import zipfile
from framework.quarto_bridge import QuartoBridge, QuartoManuscriptBuilder, _delivery
from framework import subprocesses

DRIVER = 'import json,sys,zipfile\nfrom pathlib import Path\nargs=sys.argv[1:];mode=Path("mode").read_text();fmt=args[args.index("--to")+1]\nfolder=Path(args[args.index("--output-dir")+1]) if "--output-dir" in args else Path.cwd()\nfolder.mkdir(parents=True,exist_ok=True)\nif mode=="none" or (mode=="partial" and fmt!="html"):raise SystemExit(0)\ntarget=folder/("index."+fmt)\nif mode=="corrupt":target.write_bytes(b"invalid artifact");raise SystemExit(0)\nif fmt=="html":\n target.write_text(\'<!doctype html><html><head><title>Fixture</title></head><body><img src="index_files/plot.svg"></body></html>\',encoding="utf-8")\n resources=folder/"index_files";resources.mkdir(exist_ok=True)\n (resources/"plot.svg").write_text(\'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><path d="M0 0L20 20"/></svg>\')\nelif fmt=="pdf":\n from matplotlib.figure import Figure\n figure=Figure();figure.text(.1,.5,"Controlled PDF fixture");figure.savefig(target)\nelse:\n with zipfile.ZipFile(target,"w") as z:\n  z.writestr("[Content_Types].xml",\'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>\')\n  z.writestr("_rels/.rels",\'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>\')\n  z.writestr("word/document.xml",\'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Fixture</w:t></w:r></w:p></w:body></w:document>\')\nif mode=="mutate":Path("index.qmd").write_text("changed during render")\nif mode=="missing-resource" and fmt=="html":(folder/"index_files/plot.svg").unlink()\n'


class ControlledBridge(QuartoBridge):
    """Replace only the external Quarto executable with a controlled CLI."""

    def _check_quarto(self):
        self.quarto_cmd = sys.executable
        self.quarto_version = "controlled CLI fixture"
        return True


def fixture(root: Path, mode="good"):
    manuscript = root / "manuscript"
    manuscript.mkdir(parents=True)
    (manuscript / "index.qmd").write_text(
        "# Controlled acceptance manuscript\n", encoding="utf-8", newline="\n"
    )
    (manuscript / "render").write_text(DRIVER, encoding="utf-8", newline="\n")
    (manuscript / "mode").write_text(mode, encoding="utf-8")
    return ControlledBridge(
        {
            "project_root": root,
            "render_inputs": ["manuscript/render", "manuscript/mode"],
        }
    )


def checked_outputs(bridge, result):
    assert result["success"] is True, result
    receipt = json.loads(Path(result["manifest"]).read_text())
    for name, digest in receipt["outputs"].items():
        assert (
            hashlib.sha256((bridge.output_dir / name).read_bytes()).hexdigest()
            == digest
        )
    expected_formats = {"html", "pdf", "docx"}
    assert set(result["formats"]) == set(receipt["formats"]) == expected_formats
    for fmt in expected_formats:
        assert (bridge.output_dir / ("index." + fmt)).is_file()
    expected_inputs = [bridge.manuscript_dir / "index.qmd"]
    expected_inputs += [
        bridge.project_root / name for name in bridge.config.get("render_inputs", [])
    ]
    assert receipt["inputs"] == {
        path.relative_to(bridge.project_root)
        .as_posix(): hashlib.sha256(path.read_bytes())
        .hexdigest()
        for path in expected_inputs
    }
    for fmt, row in result["formats"].items():
        assert row["published"] and row["success"]
        assert Path(row["path"]) == bridge.output_dir / ("index." + fmt)
        assert row["sha256"] == receipt["outputs"]["index." + fmt]
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-quarto", action="store_true")
    args = parser.parse_args()
    installed = Path(sys.modules[QuartoBridge.__module__].__file__).resolve()
    assert (
        installed.is_relative_to(Path(sys.prefix).resolve())
        and "site-packages" in installed.parts
    ), installed
    pdfinfo = shutil.which("pdfinfo")
    assert pdfinfo, "Install Poppler pdfinfo before running acceptance"
    pdf_version = subprocesses.run_tree([pdfinfo, "-v"], cwd=Path.cwd(), timeout=10)
    cases = []

    def accepted(name):
        cases.append({"case": name, "accepted": True})

    with tempfile.TemporaryDirectory(prefix="eidos-installed-render-") as directory:
        base = Path(directory)
        for mode in ("none", "partial", "corrupt", "mutate", "missing-resource"):
            bridge = fixture(base / mode, mode)
            old = bridge.output_dir / "index.html"
            old.write_text("previous output")
            result = bridge.render("all")
            assert (
                result["success"] is False and old.read_text() == "previous output"
            ), result
            assert not (bridge.output_dir / "render-manifest.json").exists()
            accepted("reject " + mode + " and preserve previous publication")
        bridge = fixture(base / "complete")
        receipt = checked_outputs(bridge, bridge.render("all"))
        assert (bridge.output_dir / "index_files/plot.svg").is_file()
        accepted("complete three-format files, resources and receipt")
        old = bridge.output_dir / "index.html"
        before = old.read_bytes()
        bridge.config["render_inputs"].append("outputs/index.html")
        result = bridge.render("html")
        assert result["success"] is False and old.read_bytes() == before, result
        accepted("reject overwriting a declared input")
        conflict = fixture(base / "reserved")
        program = conflict.manuscript_dir / "render"
        program.write_text(
            program.read_text()
            + '\n(folder/"render-manifest.json").write_text("resource collision")\n'
        )
        assert conflict.render("html")["success"] is False
        assert not (conflict.output_dir / "index.html").exists()
        accepted("reject reserved receipt resource")

        class WrongTool(QuartoBridge):
            def _quarto_candidates(self):
                return iter([sys.executable])

        wrong = WrongTool({"project_root": base})
        assert wrong.quarto_available is False
        accepted("reject wrong executable version")
        for fmt in ("svg", "png", "pdf"):
            script = bridge.project_root / ("plot " + fmt + ".py")
            script.write_text(
                "import argparse;argparse.ArgumentParser().parse_args()\nimport matplotlib.pyplot as p\np.plot([0,1],[1,0])\nraise SystemExit(0)\n"
            )
            result = bridge.render_figure(script, fmt)
            assert result["success"] is True, result
            path = Path(result["path"])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == result["sha256"]
            _delivery.validate(path, fmt, path.parent)
            accepted("single Matplotlib " + fmt + " with normal CLI exit")
        for expression in ("0.0", "__import__('numpy').int64(0)"):
            script = bridge.project_root / "failed-exit.py"
            script.write_text(
                "import matplotlib.pyplot as p;p.plot([0,1],[1,0]);raise SystemExit("
                + expression
                + ")"
            )
            result = bridge.render_figure(script, "svg")
            assert result["success"] is False and result["exit_code"] == 1, result
            accepted("reject noninteger exit " + expression)
        fake_pdf = base / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\nxref\nstartxref\n9\n%%EOF\n")
        try:
            _delivery.validate(fake_pdf, "pdf", base)
        except ValueError:
            pass
        else:
            raise AssertionError("empty PDF shell accepted")
        accepted("reject PDF shell without a document")
        if args.real_quarto:
            manuscript = base / "real project" / "custom manuscript"
            builder = QuartoManuscriptBuilder(manuscript)
            builder.set_metadata(
                title="Real render: controlled acceptance", author=["Fixture author"]
            )
            builder.add_section(
                "Result",
                "A genuine render with $x^2$ and a table.\n\n| arm | value |\n|---|---|\n| A | 1 |\n",
            )
            builder.add_table(
                "Constructed table",
                [[1, "a|b"], [2, "line\nbreak"]],
                headers=["n", "literal"],
            )
            result = builder.render("all")
            assert result["success"] is True, result
            real = QuartoBridge(
                {"project_root": manuscript.parent, "manuscript_dir": str(manuscript)}
            )
            checked_outputs(real, result)
            assert all(r["bytes"] > 1000 for r in result["formats"].values())
            accepted("actual Quarto three formats from custom manuscript directory")
    print(
        json.dumps(
            {
                "generated": datetime.now(timezone.utc).isoformat(),
                "platform": sys.platform,
                "python": sys.version,
                "executable": sys.executable,
                "installed_module": str(installed),
                "sdk_version": version("eidos"),
                "pdfinfo": (pdf_version.stdout + pdf_version.stderr).strip(),
                "cases": cases,
                "real_quarto": args.real_quarto,
                "dependencies": sorted(
                    set((d.metadata.get("Name"), d.version) for d in distributions())
                ),
                "scope": "Installed SDK delivery boundary, controlled CLI and actual Matplotlib; actual Quarto only when explicitly requested. Not scientific truth, journal acceptance, new-machine or runtime-service migration.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
