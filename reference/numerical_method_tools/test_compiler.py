"""Controls for formula translation; no model/provider is called."""
import copy
import json

import numpy as np
import pytest

from reference.numerical_method_tools import compiler
from reference.rsi_bootstrap import expressions, grader


@pytest.mark.parametrize('dtype', [np.float32, np.float64])
def test_arithmetic_translation_and_dtype(dtype):
    tree = compiler.compile_formulas('log1p(x) + 2*x - x/2', 'exp(-x)')
    outputs = expressions.execute(expressions.parse_program(json.dumps(tree)), np.asarray(.2, dtype=dtype))
    x = np.asarray(.2, dtype=dtype)
    assert outputs[0] == np.log1p(x) + np.asarray(2, dtype=dtype)*x - x/np.asarray(2, dtype=dtype)
    assert outputs[1] == np.exp(-x)
    assert all(value.dtype == x.dtype for value in outputs)


@pytest.mark.parametrize('formula', ['where(x <= 1, log(x), log(-x))',
                                     'log(x) if x <= 1 else log(-x)'])
def test_lazy_branches(formula):
    tree = compiler.compile_formulas(formula, '1/x')
    outputs = expressions.execute(expressions.parse_program(json.dumps(tree)), np.asarray(.5))
    assert outputs == (np.log(np.asarray(.5)), np.asarray(2.))


@pytest.mark.parametrize('formula', [
    '__import__("os")', 'x.real', 'x[0]', 'lambda: x', '[x for x in x]',
    '(x:=2)', 'x**2', 'x//2', 'x<1', '0 <= x <= 1', 'True', 'None', '"x"',
    'nan', 'inf', '1e400', 'log(x, base=2)', 'log(*[x])', 'exp(x,x)',
    'where(x,1,2)', 'x <= 1', 'x+True', 'log(x<=1)', '+x',
    'where(x<=1,x,unknown(x))', 'x if x<=1 else __import__("os")',
])
def test_forbidden_syntax_and_types_refused(formula):
    with pytest.raises(ValueError):
        compiler.compile_formulas(formula, '1')


def test_source_and_expression_limits():
    for formula in ('x'*2049, 'exp('*20+'x'+')'*20, '+'.join(['x']*140)):
        with pytest.raises(ValueError):
            compiler.compile_formulas(formula, '1')
    for value in (None, 1, b'x'):
        with pytest.raises(ValueError):
            compiler.compile_formulas(value, '1')


def test_candidate_cannot_execute_python(tmp_path):
    sentinel = tmp_path/'must-not-exist'
    attack = f'__import__("pathlib").Path({str(sentinel)!r}).write_text("bad")'
    with pytest.raises(ValueError):
        compiler.compile_formulas(attack, '1')
    assert not sentinel.exists()


def test_sourced_method_passes_existing_decimal_oracle():
    method = compiler.load_method('log1mexp-v1')
    tree = compiler.compile_formulas(method['loss'], method['gradient'])
    program = expressions.parse_program(json.dumps(tree))
    for case in grader.development_cases():
        assert grader.grade(case, *expressions.execute(program, case.value))['passed']
    assert 'maintainer' in method['derivative_attribution'].lower()
    assert method['source_urls'][0].startswith('https://search.r-project.org/')


@pytest.mark.parametrize('kind', ['duplicate', 'unknown_field', 'credentials', 'bad_id', 'oversize'])
def test_catalog_identity_and_size(tmp_path, kind):
    value = compiler.strict_json(compiler.CATALOG.read_bytes())
    if kind == 'duplicate': value['methods'].append(copy.deepcopy(value['methods'][0]))
    elif kind == 'unknown_field': value['methods'][0]['auto_download'] = True
    elif kind == 'credentials': value['methods'][0]['source_urls'] = ['https://key@example.com/']
    elif kind == 'bad_id': value['methods'][0]['id'] = []
    else: value['notice'] = 'x'*32769
    path = tmp_path/'catalog.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError): compiler.load_method('log1mexp-v1', path)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e400}',
                               b'['*1500+b'0'+b']'*1500],
                         ids=['duplicate','nan','infinity','overflow','deep-json'])
def test_duplicate_nonfinite_json_refused(raw):
    with pytest.raises(ValueError): compiler.strict_json(raw)


def test_unknown_method_never_falls_back():
    with pytest.raises(ValueError): compiler.load_method('invented')


def test_origin_card_survives_layout_changes_but_not_changed_facts(tmp_path, monkeypatch):
    bank = compiler.strict_json(compiler.BANK.read_bytes())
    file = tmp_path/'bank.json'
    file.write_bytes(json.dumps(bank, indent=4).replace('\n', '\r\n').encode())
    monkeypatch.setattr(compiler, 'BANK', file)
    assert compiler.load_method('log1mexp-v1')['origin_card_id'] == 'log1mexp-piecewise'
    bank['cards'][0]['text'] += 'Altered meaning.'
    file.write_text(json.dumps(bank), encoding='utf-8')
    with pytest.raises(ValueError): compiler.load_method('log1mexp-v1')


def test_json_depth_guard_respects_string_quotes_and_escapes():
    value = {'literal': '['*1500+'\\"quoted\\"'+']'*1500}
    assert compiler.strict_json(json.dumps(value).encode()) == value
