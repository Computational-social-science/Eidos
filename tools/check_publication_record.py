"""Check that the inspected manuscript artifacts still match their technical audit."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inputs(root: Path) -> list[Path]:
    files = [root/'tools'/name for name in ('publication.py','audit_publication.py','check_publication_record.py',
                                           'numerics_figure.py','training_figure.py')]
    files += [root/'reference/softmax_matrix/report.py',root/'tools/numerics_case.py']
    for name in ('numerics','softmax-matrix'):
        folder=root/'site/reports'/name
        files += [folder/f'report.{extension}' for extension in ('qmd','html','pdf','docx')]
        files += sorted(folder.rglob('*.svg'))
        files += sorted(p for p in folder.rglob('*.pdf') if p.name!='report.pdf')
    return files


def fingerprints(root: Path = ROOT) -> dict[str,str]:
    result={}
    for path in inputs(root):
        content=path.read_bytes()
        if path.suffix=='.py':
            content=content.decode('utf-8-sig').replace('\r\n','\n').encode('utf-8')
        result[path.relative_to(root).as_posix()]=hashlib.sha256(content).hexdigest()
    return result


def errors(root: Path = ROOT) -> list[str]:
    try:
        record=json.loads((root/'docs/PUBLICATION-QA.json').read_text(encoding='utf-8'))
        if record.get('technical_checks_pass') is not True:
            return ['technical manuscript audit did not pass']
        expected=fingerprints(root)
        saved=record.get('artifact_sha256')
        if not isinstance(saved,dict) or saved.keys()!=expected.keys():
            return ['publication audit inventory is missing or changed']
        return [f'publication audit is stale: {name}' for name,digest in expected.items() if saved[name]!=digest]
    except (OSError,ValueError,TypeError,AttributeError) as exc:
        return ['publication audit unavailable: '+type(exc).__name__]


if __name__=='__main__':
    issues=errors()
    print('\n'.join(issues) if issues else 'Publication technical audit matches the delivered artifacts')
    raise SystemExit(1 if issues else 0)
