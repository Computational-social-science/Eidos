"""Public scientific interpretation must retain unfavorable pairs and missingness."""
import pytest
from tools.academic_case import summarize_matrix


def record():
    return {'runs': [{'seed': seed, 'loss_dtype':'float32', 'epsilon':1e-8,
                      'arm':arm, 'checkpoints':[{'test_accuracy':value}]}
                     for seed, values in enumerate(((.4,.5),(.6,.4),(.5,.5)))
                     for arm,value in zip(('standard','fixed'),values)]}


def test_summary_counts_each_paired_direction_without_selection():
    result = summarize_matrix(record())
    assert (result['runs'],result['pairs'],result['higher'],result['lower'],result['ties']) == (6,3,1,1,1)


def test_missing_or_duplicate_arm_cannot_become_a_verified_summary():
    r=record(); r['runs'].pop()
    with pytest.raises(ValueError): summarize_matrix(r)
    r=record(); r['runs'].append(r['runs'][0])
    with pytest.raises(ValueError): summarize_matrix(r)


def test_homepage_names_academic_scope_and_preserves_method_attribution():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
    import site_page
    section = site_page.sec_position()
    for term in ('falsifiable','independent','Barron','reproducibility'):
        assert term in section
    evidence = site_page.sec_evidence({'matrix_summary':summarize_matrix(record()), 'demo':{}})
    assert '1 higher' in evidence and '1 lower' in evidence and '1 tie' in evidence
    assert 'paper MATCH' in evidence
    unavailable = site_page.sec_evidence({'matrix_summary':{'status':'UNVERIFIED'},'demo':{}})
    assert 'Reverification required' in unavailable
    failed = site_page.sec_evidence({'demo':{'qualification':{'verdict':'FAIL'},'training':{'status':'FAIL'}},
                                     'matrix_summary':{'status':'UNVERIFIED'}})
    assert 'A checked stationary point' not in failed and 'checked against independent Decimal' not in failed


def test_public_source_documents_are_available_under_the_site_root(tmp_path):
    from tools.site_documents import publish
    (tmp_path/'docs').mkdir()
    source=tmp_path/'docs/ACADEMIC_POSITIONING.md';source.write_text('A bounded contribution')
    publish(tmp_path)
    assert (tmp_path/'site/docs/ACADEMIC_POSITIONING.md').read_bytes()==source.read_bytes()


def test_actual_scientific_probe_model_is_named_without_promoting_it():
    from tools import build_site
    import site_page
    evidence=build_site.model_quality()
    section=site_page.sec_models({'model_quality':evidence})
    assert 'ScienceRSI-8B' in section and '13/15 (86.7%)' in section and '17/20 (85.0%)' in section
    assert 'Not promoted to a scientific gate' in section
    assert 'Experiment execution uses registered commands' in section
    missing=site_page.sec_models({'model_quality':{}})
    assert 'unavailable' in missing and '13/15' not in missing


@pytest.mark.parametrize('identity',['ScienceRSI-OTHER-QUANT','ScienceRSI-8b.i1-Q8_0','llama3.1:8b'])
def test_probe_scores_cannot_be_attributed_to_another_model_or_quantization(identity):
    from tools import build_site
    import site_page
    record={'model':identity,'n':100,'agree':100,'hits':100}
    section=site_page.sec_models({'model_quality':{'s4':record,'s7':record}})
    assert '100/100' not in section and 'unavailable' in section
