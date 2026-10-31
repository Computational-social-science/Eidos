"""Measure production requirements for the delivered scientific figures and reports.

Run with the bundled PDF runtime (pypdf) and Poppler on PATH. A technical PASS
does not establish scientific suitability or complete human submission metadata.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def svg_checks(path: Path) -> dict:
    root=ET.parse(path).getroot()
    def mm(value):
        number=float(re.match(r'[0-9.]+',value)[0])
        return number*25.4/72 if value.endswith('pt') else number if value.endswith('mm') else number*25.4/96
    width,height=mm(root.attrib['width']),mm(root.attrib['height'])
    viewbox=[float(v) for v in root.get('viewBox','').replace(',',' ').split()]
    # A CSS px is a user unit. With a viewBox its physical size is set by the
    # viewport transform; Matplotlib uses a one-point-per-user-unit viewBox.
    scales=([width*72/25.4/viewbox[2],height*72/25.4/viewbox[3]] if len(viewbox)==4 else [.75,.75])
    supported=abs(scales[0]-scales[1])<1e-5
    scale=min(scales)
    texts=[];sizes=[];fonts=set()
    def visit(node,inherited,unscaled):
        nonlocal supported
        props=dict(inherited)
        props.update({k.strip():v.strip() for k,_,v in (part.partition(':') for part in node.get('style','').split(';')) if k})
        for key in ('font-size','font-family'):
            if node.get(key): props[key]=node.get(key)
        remaining=re.sub(r'(?:translate|rotate)\([^)]*\)','',node.get('transform','')).strip()
        unscaled=unscaled and not remaining and 'transform' not in props
        if node.tag.rsplit('}',1)[-1] in ('text','tspan'):
            texts.append(node)
            if node.text and node.text.strip():
                match=re.fullmatch(r'([0-9.]+)(px|pt)?',props.get('font-size',''))
                if not match or not unscaled:
                    supported=False
                else:
                    sizes.append(float(match[1])*(4/3 if match[2]=='pt' else 1)*scale)
                fonts.add(props.get('font-family','').split(',')[0].strip("'\" "))
        for child in node: visit(child,props,unscaled)
    visit(root,{},True)
    outlines=[e.get('id') for e in root.iter() if re.match(r'(Arial|Helvetica|DejaVu|Liberation|Times)[^-]*-[0-9a-fA-F]+$',e.get('id',''))]
    checks={'width_89_or_183_mm':min(abs(width-89),abs(width-183))<.05,
            'height_at_most_170_mm':height<=170.05,
            'editable_text':bool(texts) and not outlines,
            'supported_text_geometry':supported,
            'standard_font':bool(fonts) and fonts<={'Arial','Helvetica'},
            'font_size_5_to_7_pt':bool(sizes) and min(sizes)>=5-1e-6 and max(sizes)<=7+1e-6}
    return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
            'width_mm':width,'height_mm':height,'text_nodes':len(texts),'font_names':sorted(fonts),
            'font_range_pt':[min(sizes),max(sizes)] if sizes else None,'checks':checks,'ok':all(checks.values())}


def pdf_fonts(path: Path) -> dict:
    command=shutil.which('pdffonts')
    if not command:
        from pypdf import PdfReader
        reader=PdfReader(path);rows=[];visited=set()
        def inspect(resources):
            resources=resources.get_object()
            if id(resources) in visited: return
            visited.add(id(resources))
            for reference in resources.get('/Font',{}).values():
                font=reference.get_object()
                descendants=font.get('/DescendantFonts') or [font]
                for child in descendants:
                    child=child.get_object();descriptor=child.get('/FontDescriptor')
                    descriptor=descriptor.get_object() if descriptor else {}
                    embedded=any(k in descriptor for k in ('/FontFile','/FontFile2','/FontFile3'))
                    rows.append((str(child.get('/BaseFont')),str(child.get('/Subtype')),embedded))
            for reference in resources.get('/XObject',{}).values():
                child=reference.get_object()
                if child.get('/Resources'): inspect(child['/Resources'])
        for page in reader.pages: inspect(page['/Resources'])
        return {'all_embedded':bool(rows) and all(r[2] for r in rows),
                'no_type3_fonts':all(r[1]!='/Type3' for r in rows),
                'font_table':sorted(set(f'{name} {kind} embedded={embedded}' for name,kind,embedded in rows))}
    flags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0
    result=subprocess.run([command,str(path)],capture_output=True,text=True,timeout=30,creationflags=flags)
    if result.returncode: raise RuntimeError('PDF font inspection failed')
    rows=[line for line in result.stdout.splitlines()[2:] if line.strip()]
    return {'all_embedded':bool(rows) and all(len(r.split())>=5 and r.split()[-5]=='yes' for r in rows),
            'no_type3_fonts':all('Type 3' not in r for r in rows),'font_table':rows}


def report_checks(directory: Path) -> dict:
    from pypdf import PdfReader
    reader=PdfReader(directory/'report.pdf')
    text=re.sub(r'\s+',' ',' '.join(page.extract_text() or '' for page in reader.pages))
    required=('Methods','Data availability','Code availability','References','experimental unit')
    fonts=pdf_fonts(directory/'report.pdf')
    checks={term:term.lower() in text.lower() for term in required}
    checks.update(pdf_fonts_embedded=fonts['all_embedded'],no_type3_fonts=fonts['no_type3_fonts'])
    checks['a4_pages']=all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.89)<1 for p in reader.pages)
    checks['no_duplicate_caption_labels']=not re.search(r'(Figure|Table)\s+\d+\s*:\s*\1\s+\d+',text)
    legends=re.findall(r'!\[(\*\*Figure[^\]]+)\]',(directory/'report.qmd').read_text(encoding='utf-8'))
    checks['figure_legends_under_300_words']=bool(legends) and all(len(t.split())<300 for t in legends)
    with __import__('zipfile').ZipFile(directory/'report.docx') as z:
        document=ET.fromstring(z.read('word/document.xml'))
        styles=ET.fromstring(z.read('word/styles.xml'))
        ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        checks['word_line_numbers']=bool(list(document.iter(ns+'lnNumType')))
        checks['word_12pt']=bool(list(styles.iter(ns+'sz'))) and all(e.get(ns+'val')=='24' for e in styles.iter(ns+'sz'))
        spacings=[e.get(ns+'line') for e in styles.iter(ns+'spacing') if e.get(ns+'line') is not None]
        checks['word_double_spacing']=bool(spacings) and all(value=='480' for value in spacings)
    return {'path':directory.relative_to(ROOT).as_posix(),'pages':len(reader.pages),'checks':checks,
            'font_table':fonts['font_table'],'ok':all(checks.values())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'docs/PUBLICATION-QA.json')
    args=parser.parse_args()
    sys.path.insert(0,str(ROOT))
    from framework.artifacts import output_lock
    with output_lock(ROOT/'site/reports/numerics'), output_lock(ROOT/'site/reports/softmax-matrix'):
        return audit(args.out)


def audit(output: Path) -> int:
    from tools.check_publication_record import fingerprints
    from framework.artifacts import atomic_output
    before=fingerprints()
    figures=[ROOT/'site/reports/numerics'/f'figure-{dtype}.svg' for dtype in ('float32','float64')]
    figures += [ROOT/'site/reports/numerics/training/trajectory.svg',ROOT/'site/reports/softmax-matrix/accuracy-matrix.svg']
    svg=[svg_checks(p) for p in figures]
    fonts=[{'path':p.with_suffix('.pdf').relative_to(ROOT).as_posix(),**pdf_fonts(p.with_suffix('.pdf'))} for p in figures]
    reports=[report_checks(ROOT/'site/reports'/name) for name in ('numerics','softmax-matrix')]
    ok=all(r['ok'] for r in [*svg,*reports]) and all(f['all_embedded'] and f['no_type3_fonts'] for f in fonts)
    after=fingerprints()
    stable=before==after
    ok=ok and stable
    record={'technical_checks_pass':ok,'submission_ready':False,'stable_inputs':stable,'artifact_sha256':after,
            'hash_policy':'SHA-256; production Python canonical UTF-8/LF, delivered artifacts exact bytes preserved by Git -text.',
            'scope':'Measured technical production requirements; final page inspection and human submission metadata are separate.',
            'guides':['https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/',
                      'https://www.nature.com/nature/for-authors/formatting-guide'],
            'figures':svg,'pdf_figure_fonts':fonts,'reports':reports}
    with atomic_output(output) as temporary:
        temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'technical_checks_pass':ok,'submission_ready':False,'report_pages':[r['pages'] for r in reports]}))
    return 0 if ok else 1


if __name__=='__main__': raise SystemExit(main())
