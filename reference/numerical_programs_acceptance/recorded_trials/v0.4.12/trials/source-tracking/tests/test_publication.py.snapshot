"""Submission typography and required evidence statements are explicit contracts."""
import io
import zipfile
import xml.etree.ElementTree as ET

from tools.publication import W, header, declarations, manuscript_docx


def test_pdf_and_html_use_separate_production_rules():
    text=header('A bounded numerical validation')
    assert '12pt' in text and 'linenumbers' in text and 'doublespacing' in text
    assert 'Times New Roman' in text and 'reference.docx' in text
    for section in ('Data availability','Code availability','References','submission metadata'):
        assert section in declarations()


def test_word_styles_and_line_numbering_are_written_to_the_delivered_document():
    source=io.BytesIO()
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('word/styles.xml',f'<w:styles xmlns:w="{W[1:-1]}"><w:style w:type="paragraph"><w:rPr/></w:style></w:styles>')
        z.writestr('word/document.xml',f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:sectPr/></w:body></w:document>')
        z.writestr('word/media/preserve.bin',b'original asset')
    with zipfile.ZipFile(io.BytesIO(manuscript_docx(source.getvalue()))) as z:
        assert z.read('word/media/preserve.bin') == b'original asset'
        styles=ET.fromstring(z.read('word/styles.xml'))
        assert all(e.get(W+'val')=='24' for e in styles.iter(W+'sz'))
        doc=ET.fromstring(z.read('word/document.xml'))
        assert next(doc.iter(W+'lnNumType')).get(W+'restart') == 'continuous'
        section=next(doc.iter(W+'sectPr'))
        assert [e.tag for e in section] == [W+'pgSz',W+'pgMar',W+'lnNumType']
        assert styles[0].tag == W+'docDefaults'


def test_outlined_or_oversized_figure_cannot_pass(tmp_path):
    from tools.audit_publication import svg_checks
    path=tmp_path/'figure.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="518.740157pt" height="374.173228pt" viewBox="0 0 518.740157 374.173228"><text style="font-size:6px;font-family:Arial">data</text></svg>')
    assert svg_checks(path)['ok']
    path.write_text(path.read_text().replace('font-size:6px','font-size:10px'))
    assert not svg_checks(path)['ok']
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="518.740157pt" height="374.173228pt"><path id="Arial-31"/></svg>')
    assert not svg_checks(path)['ok']


def test_scaled_svg_text_does_not_borrow_unscaled_font_size(tmp_path):
    from tools.audit_publication import svg_checks
    path=tmp_path/'small.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="183mm" height="132mm" viewBox="0 0 1000 721.311"><text style="font-size:6px;font-family:Arial">data</text></svg>')
    assert not svg_checks(path)['ok']
    assert svg_checks(path)['font_range_pt'][0] < 5


def test_unqualified_text_transform_is_rejected(tmp_path):
    from tools.audit_publication import svg_checks
    path=tmp_path/'transformed.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="518.740157pt" height="374.173228pt" viewBox="0 0 518.740157 374.173228"><g transform="scale(.5)"><text style="font-size:6px;font-family:Arial">data</text></g></svg>')
    assert not svg_checks(path)['ok']


def test_edited_report_invalidates_its_old_technical_audit(tmp_path,monkeypatch):
    import json
    from tools import check_publication_record as check
    path=tmp_path/'report.pdf';path.write_bytes(b'inspected report')
    monkeypatch.setattr(check,'inputs',lambda root:[path])
    (tmp_path/'docs').mkdir()
    record={'technical_checks_pass':True,'artifact_sha256':check.fingerprints(tmp_path)}
    (tmp_path/'docs/PUBLICATION-QA.json').write_text(json.dumps(record))
    assert check.errors(tmp_path)==[]
    path.write_bytes(b'changed after inspection')
    assert check.errors(tmp_path)==['publication audit is stale: report.pdf']


def test_pagination_relationships_remain_valid_and_idempotent():
    source=io.BytesIO()
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('word/document.xml',f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:sectPr/></w:body></w:document>')
        z.writestr('word/_rels/document.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
    result=manuscript_docx(manuscript_docx(source.getvalue()))
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        for name in z.namelist():
            ET.fromstring(z.read(name))
        rels=ET.fromstring(z.read('word/_rels/document.xml.rels'))
        assert len(rels)==1
        assert z.read('word/eidos-pagination.xml').count(b' PAGE ')==1
