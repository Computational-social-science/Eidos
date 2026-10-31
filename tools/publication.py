"""Shared manuscript production settings; technical checks do not imply journal acceptance."""
from __future__ import annotations
import io
import math
import re
import subprocess
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


FIGURE_GUIDE = 'https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/'
FORMAT_GUIDE = 'https://www.nature.com/nature/for-authors/formatting-guide'
CSS = '''
body{font-family:Georgia,"Times New Roman",serif;font-size:17px;line-height:1.85;color:#202124;background:#fff}
main.content{max-width:1000px;min-width:0;width:100%;margin:auto;padding:30px 24px}h1{font-size:30px;line-height:1.25;max-width:28ch}
h2{font-size:22px;line-height:1.4;margin:2em 0 .6em}h3{font-size:18px;margin:1.5em 0 .5em}
p,li{max-width:85ch;overflow-wrap:anywhere}a{color:#245c83}pre,code{font-family:Consolas,monospace;font-size:.85em}
table{display:block;overflow-x:auto;max-width:100%;font-size:14px;line-height:1.6;border-collapse:collapse;width:100%}th,td{padding:9px 10px;border-bottom:1px solid #ddd}
th{text-align:left;font-weight:bold}figure{margin:26px 0}figure img{width:100%;height:auto;background:white}
figcaption{font-size:14px;line-height:1.65;color:#343434;margin-top:12px}caption{caption-side:top;text-align:left}
pre{padding:14px;background:#f5f5f3;overflow:auto}#TOC{font-family:Arial,sans-serif;font-size:13px}
@media(max-width:600px){body{font-size:16px}main.content{padding:20px 16px}h1{font-size:25px}.cell-output-display{overflow:auto}}
@media print{#TOC,nav{display:none}body{font-size:12pt;color:black}}
'''


def header(title: str) -> str:
    import yaml
    config = {
        'title': title, 'lang': 'en', 'date': '2026-10-31',
        'format': {
            'html': {'embed-resources': True, 'toc': True, 'toc-depth': 2,
                     'include-in-header': [{'text': '<style>'+CSS+'</style>'}]},
            'pdf': {'documentclass': 'article', 'pdf-engine': 'lualatex', 'papersize': 'a4',
                    'geometry': ['left=13.5mm','right=13.5mm','top=22mm','bottom=22mm'],
                    'fontsize': '12pt', 'mainfont': 'Times New Roman',
                    'include-in-header': [{'text': r'''\usepackage{setspace}
\doublespacing
\usepackage{lineno}
\linenumbers
\usepackage{caption}
\usepackage{needspace}
\captionsetup{labelformat=empty,font=normalsize,justification=raggedright,singlelinecheck=false}
\makeatletter
\renewcommand{\maketitle}{\begingroup\setlength{\parindent}{0pt}{\large\bfseries\@title\par}\vspace{0.4em}{\normalsize Research validation report\par}{\normalsize\@date\par}\vspace{1em}\endgroup}
\makeatother'''}]},
            'docx': {'reference-doc': 'reference.docx'}
        }
    }
    return '---\n'+yaml.safe_dump(config,sort_keys=False,allow_unicode=True)+'---\n\n'


def declarations() -> str:
    return '''
## Data availability

Original protocols, raw measurements, seed/split identifiers and saved-model
artifacts are available in [the evidence record](evidence.json) and
[the checksummed reproduction bundle](reproduce.zip). Every specified outcome is retained. The repository records code, data
and environment hashes; artifact acceptance can be rerun independently.

## Code availability

Source and tests are included in `reproduce.zip` and in the
[EIDOS repository](https://github.com/Computational-social-science/Eidos).
Follow the bundle README for CPU acceptance and the recorded runtime for retraining.
The original numerical method is attributed to its authors in the references.

## Reporting and submission metadata

This is a technical validation report. Authors, affiliations, funding, author
contributions and competing-interest declarations must be completed by the human
research team before journal submission. No inferred personal or funding metadata
has been supplied. Technical production follows the linked figure and manuscript
guides; scientific suitability and editorial acceptance require separate review.

## References

1. Barron, J. T., Gnanapragasam, D. & Tschannen, M. *A Fix for Softmax and
   Cross-Entropy*, version 3. [arXiv:2610.31642v3](https://arxiv.org/html/2610.31642v3).
2. Nature. [Research figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/).
3. Nature. [Formatting guide](https://www.nature.com/nature/for-authors/formatting-guide).
'''


W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ET.register_namespace('w', W[1:-1])


def _child(parent, tag):
    found = parent.find(W+tag)
    return found if found is not None else ET.SubElement(parent,W+tag)


def caption_tables(text: str, captions: list[str]) -> str:
    lines, result, index, in_table = text.splitlines(), [], 0, False
    start=0
    for line in [*lines, '']:
        is_table = line.startswith('|')
        if is_table and not in_table: start=len(result)
        if in_table and not is_table:
            if index >= len(captions):
                raise ValueError('missing table caption')
            table_lines=result[start:]
            insertion=start
            previous=next((i for i in range(start-1,-1,-1) if result[i].strip()),None)
            if previous is not None and result[previous].startswith('## '):
                insertion=previous
            if len(table_lines)>12:
                result[insertion:insertion]=['::: {.content-visible when-format="pdf"}', '```{=latex}', r'\clearpage', '```', ':::', '']
            else:
                columns=len(table_lines[0].strip('|').split('|'))
                characters=max(8,int((518-12*columns)/columns/6))
                needed=4+sum(max(math.ceil(len(cell.strip())/characters) for cell in row.strip('|').split('|'))
                             for row in [table_lines[0],*table_lines[2:]])
                result[insertion:insertion]=['::: {.content-visible when-format="pdf"}', '```{=latex}',
                                     rf'\Needspace{{{needed}\baselineskip}}', '```', ':::', '']
            title, _, rest = captions[index].partition('. ')
            caption = ': **' + title.rstrip('. ') + '.**'
            if rest:
                caption += ' ' + rest
            result.extend(['', caption, ''])
            index += 1
        result.append(line)
        in_table = is_table
    if index != len(captions):
        raise ValueError('caption inventory does not match tables')
    return '\n'.join(result)


def caption_figures(text: str) -> str:
    """Keep the short figure title bold in every target format."""
    def bold_title(match):
        title, separator, rest = match[1].partition('. ')
        return '![' + '**' + title.rstrip('. ') + '.**' + (' ' + rest if separator else '') + ']'
    return re.sub(r'!\[(Figure [0-9]+ \|[^\]]+)\]', bold_title, text)


def _xml(root, original: bytes) -> bytes:
    namespaces = {}
    for _, pair in ET.iterparse(io.BytesIO(original), events=['start-ns']):
        namespaces[pair[0]] = pair[1]
        if not pair[0].startswith('ns'):
            ET.register_namespace(*pair)
    result = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    mc = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
    for prefix in root.get(mc+'Ignorable', '').split():
        if prefix in namespaces and ('xmlns:'+prefix+'=').encode() not in result:
            root.set('xmlns:'+prefix, namespaces[prefix])
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def _order(parent, names):
    ranks={W+name:i for i,name in enumerate(names.split())}
    parent[:] = sorted(parent,key=lambda e:ranks.get(e.tag,len(ranks)))


def _page_footer(source):
    """Add a page-number field without replacing an existing default footer."""
    relpath='word/_rels/document.xml.rels'
    if relpath not in source.namelist():
        return {}
    document=ET.fromstring(source.read('word/document.xml'))
    sections=list(document.iter(W+'sectPr'))
    if not sections or any(e.get(W+'type')=='default' for section in sections for e in section.findall(W+'footerReference')):
        return {}
    relations=ET.fromstring(source.read(relpath))
    relns='{http://schemas.openxmlformats.org/package/2006/relationships}'
    identity='rIdEidosPagination'
    name='word/eidos-pagination.xml'
    if name in source.namelist() or any(e.get('Id')==identity for e in relations):
        raise ValueError('pagination relationship collision')
    ET.SubElement(relations,relns+'Relationship',{'Id':identity,'Type':'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer','Target':'eidos-pagination.xml'})
    r='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    for section in sections:
        ET.SubElement(section,W+'footerReference',{W+'type':'default',r+'id':identity})
    types=ET.fromstring(source.read('[Content_Types].xml'))
    t='{http://schemas.openxmlformats.org/package/2006/content-types}'
    ET.SubElement(types,t+'Override',{'PartName':'/'+name,'ContentType':'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml'})
    footer=ET.Element(W+'ftr')
    paragraph=ET.SubElement(footer,W+'p')
    props=ET.SubElement(paragraph,W+'pPr')
    ET.SubElement(props,W+'pStyle',{W+'val':'Footer'})
    ET.SubElement(props,W+'jc',{W+'val':'center'})
    field=ET.SubElement(paragraph,W+'fldSimple',{W+'instr':' PAGE '})
    ET.SubElement(ET.SubElement(field,W+'r'),W+'t').text='1'
    return {relpath:_xml(relations,source.read(relpath)), '[Content_Types].xml':_xml(types,source.read('[Content_Types].xml')),
            'word/document.xml':_xml(document,source.read('word/document.xml')),name:ET.tostring(footer)}


def manuscript_docx(content: bytes) -> bytes:
    """Apply actual Word styles and line numbering, preserving relationships/assets."""
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            if name.endswith(('.xml','.rels')):
                ET.fromstring(source.read(name))
        updates=_page_footer(source)
        infos=[*source.infolist(),*(zipfile.ZipInfo(name) for name in updates if name not in source.namelist())]
        for info in infos:
            body = updates[info.filename] if info.filename in updates else source.read(info.filename)
            if info.filename == 'word/styles.xml':
                root = ET.fromstring(body)
                defaults = _child(_child(root,'docDefaults'),'rPrDefault')
                for props in [_child(defaults,'rPr'), *root.findall(f'{W}style/{W}rPr')]:
                    fonts = _child(props,'rFonts')
                    for key in list(fonts.attrib):
                        if 'theme' in key.lower(): del fonts.attrib[key]
                    fonts.attrib.update({W+'ascii':'Times New Roman',W+'hAnsi':'Times New Roman',W+'cs':'Times New Roman'})
                    _child(props,'sz').set(W+'val','24')
                    _child(props,'szCs').set(W+'val','24')
                for style in root.findall(W+'style'):
                    if style.get(W+'type') == 'paragraph':
                        _child(_child(style,'pPr'),'spacing').attrib.update({W+'line':'480',W+'lineRule':'auto'})
                    if style.get(W+'styleId','').lower().startswith(('title','subtitle','heading')):
                        _child(_child(style,'rPr'),'color').attrib.clear()
                        _child(_child(style,'rPr'),'color').set(W+'val','000000')
                        _child(_child(style,'rPr'),'spacing').set(W+'val','0')
                    if style.get(W+'styleId','').lower().startswith(('title','heading')):
                        _child(_child(style,'rPr'),'b').set(W+'val','1')
                    if 'caption' in style.get(W+'styleId','').lower():
                        _child(_child(style,'rPr'),'i').set(W+'val','0')
                        _child(_child(style,'pPr'),'keepLines').set(W+'val','1')
                for props in root.iter(W+'pPr'):
                    _order(props,'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange')
                for props in root.iter(W+'rPr'):
                    _order(props,'rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange')
                for style in root.findall(W+'style'):
                    _order(style,'name aliases basedOn next link autoRedefine hidden uiPriority semiHidden unhideWhenUsed qFormat locked personal personalCompose personalReply rsid pPr rPr tblPr trPr tcPr')
                _order(root,'docDefaults latentStyles style')
                body = _xml(root, body)
            elif info.filename == 'word/document.xml':
                root = ET.fromstring(body)
                document_body=root.find(W+'body')
                if document_body is not None:
                    children=list(document_body)
                    for i,node in enumerate(children):
                        if node.tag==W+'p':
                            props=node.find(W+'pPr')
                            style=props.find(W+'pStyle') if props is not None else None
                            name=style.get(W+'val','') if style is not None else ''
                            if name.lower() in ('title','subtitle','date'):
                                _child(_child(node,'pPr'),'jc').set(W+'val','left')
                            if list(node.iter(W+'drawing')) and i+1<len(children):
                                caption=children[i+1]
                                if caption.tag==W+'p':
                                    _child(_child(node,'pPr'),'keepNext').set(W+'val','1')
                                    _child(_child(node,'pPr'),'keepLines').set(W+'val','1')
                                    _child(_child(caption,'pPr'),'keepLines').set(W+'val','1')
                        if node.tag==W+'tbl':
                            rows=node.findall(W+'tr')
                            if rows:
                                _child(_child(rows[0],'trPr'),'tblHeader').set(W+'val','1')
                            if len(rows)>12 and i>0 and children[i-1].tag==W+'p':
                                _child(_child(children[i-1],'pPr'),'pageBreakBefore').set(W+'val','1')
                                _child(_child(children[i-1],'pPr'),'keepNext').set(W+'val','1')
                            for row in rows:
                                _child(_child(row,'trPr'),'cantSplit').set(W+'val','1')
                            if len(rows)<=12:
                                for row in rows[:-1]:
                                    for paragraph in row.iter(W+'p'):
                                        _child(_child(paragraph,'pPr'),'keepNext').set(W+'val','1')
                    for props in root.iter(W+'pPr'):
                        _order(props,'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange')
                for section in root.iter(W+'sectPr'):
                    line = _child(section,'lnNumType')
                    line.attrib.update({W+'countBy':'1',W+'restart':'continuous',W+'distance':'200'})
                    section.remove(line)
                    after = {'pgNumType','cols','formProt','vAlign','noEndnote','titlePg','textDirection','bidi','rtlGutter','docGrid','printerSettings','sectPrChange'}
                    position = next((i for i,e in enumerate(section) if e.tag.removeprefix(W) in after), len(section))
                    section.insert(position,line)
                    _child(section,'pgSz').attrib.update({W+'w':'11906',W+'h':'16838'})
                    _child(section,'pgMar').attrib.update({W+'top':'1247',W+'bottom':'1247',W+'left':'765',W+'right':'765'})
                    _order(section,'headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange')
                body = _xml(root, body)
            target.writestr(info,body)
    return output.getvalue()


def reference_docx(output: Path, quarto: str) -> None:
    content = subprocess.check_output([quarto,'pandoc','--print-default-data-file','reference.docx'])
    (output/'reference.docx').write_bytes(manuscript_docx(content))


def finish_docx(output: Path) -> None:
    path = output/'report.docx'
    path.write_bytes(manuscript_docx(path.read_bytes()))
