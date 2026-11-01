"""Public SDK numerical-program boundaries and independent arithmetic controls."""
from decimal import Decimal, localcontext
import json

import numpy as np
import pytest

from framework.numerical_programs import ScalarProgram, compile_formulas, execute, parse_program
from reference.rsi_bootstrap import expressions as legacy, grader

LOSS='where(x <= log(2), log(-expm1(-x)), log1p(-exp(-x)))'
GRADIENT='exp(-x)/(-expm1(-x))'


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('value',[-2.,-0.,0.,2.])
def test_generic_typed_input_and_independent_output_buffers(dtype,value):
    program=compile_formulas('x','x')
    original=np.asarray(value,dtype=dtype)
    loss,gradient=execute(program,original)
    assert loss.dtype==gradient.dtype==original.dtype
    assert loss.shape==gradient.shape==()
    assert not np.shares_memory(loss,original) and not np.shares_memory(gradient,original)
    assert not np.shares_memory(loss,gradient)
    assert np.signbit(loss)==np.signbit(original)
    loss[...] = 123
    assert gradient==original and original==dtype(value)
    assert program.evaluate(dtype(value))[0]==dtype(value)


def test_program_has_no_ordinary_mutable_or_unvalidated_constructor():
    with pytest.raises(TypeError):ScalarProgram()
    program=compile_formulas('x','1')
    with pytest.raises(AttributeError):program._loss=None
    data=program.to_dict();data['loss']={'const':999}
    assert program.evaluate(np.float64(2))[0]==2
    decoded=parse_program(program.to_json())
    assert decoded.to_json()==program.to_json()
    assert parse_program(program.to_json().encode()).to_dict()==program.to_dict()


@pytest.mark.parametrize('value',[True,1,1.,[1.],np.asarray([1.]),np.asarray(1,dtype=np.int64),
    np.asarray(1,dtype=np.float16),np.asarray(1+0j),np.asarray(True),np.ma.asarray(1.),np.asarray('1')])
def test_input_types_are_not_silently_promoted(value):
    with pytest.raises((TypeError,ValueError)):compile_formulas('x','1').evaluate(value)


@pytest.mark.parametrize('value',[np.float32(np.nan),np.float64(np.inf),np.asarray(-np.inf)])
def test_nonfinite_input_refused(value):
    with pytest.raises(ValueError):compile_formulas('x','1').evaluate(value)


@pytest.mark.parametrize('formula',['__import__("os")','x.real','x[0]','lambda:x','[x for x in x]',
    '(x:=2)','x**2','x//2','x<1','0<=x<=1','True','None','"x"','1e400','nan','+x',
    'exp(x,x)','exp(x=x)','exp(*[x])','where(x,1,2)','x<=1','log(x<=1)',
    'where(x<=1,x,unknown(x))'])
def test_forbidden_formula_and_types(formula):
    with pytest.raises(ValueError):compile_formulas(formula,'1')


@pytest.mark.parametrize('raw',[b'{"loss":{},"loss":{},"gradient":{}}',
    b'{"loss":{"const":NaN},"gradient":{"input":"x"}}',
    b'{"loss":{"const":1e400},"gradient":{"input":"x"}}',
    b'['*65+b'0'+b']'*65])
def test_untrusted_json_refused(raw):
    with pytest.raises(ValueError):parse_program(raw)


def test_budgets_and_integer_identity():
    for source in ('x'*2049,'exp('*20+'x'+')'*20,'+'.join(['x']*140)):
        with pytest.raises(ValueError):compile_formulas(source,'1')
    with pytest.raises(ValueError):parse_program(' '*32769)
    with pytest.raises(ValueError):compile_formulas('9007199254740993','1')
    with pytest.raises(ValueError):parse_program(json.dumps({'loss':{'const':9007199254740993},'gradient':{'const':1}}))
    assert compile_formulas(str(2**100),'1').evaluate(np.float64(1))[0]==float(2**100)


@pytest.mark.parametrize('formula',['log(-x)','exp(1000)','1/0','where(log(-x)<=0,1,2)',
                                     'where(exp(1000)<=1,0,1)'])
def test_nonfinite_intermediates_cannot_be_masked(formula):
    with pytest.raises(FloatingPointError):compile_formulas(formula,'1').evaluate(np.float64(1))


def test_unrepresentable_constant_only_errors_when_selected():
    p=compile_formulas('where(x<=0,1e100,1)','1')
    assert p.evaluate(np.float32(1))[0]==1
    with pytest.raises(FloatingPointError):p.evaluate(np.float32(-1))


def test_legacy_positive_points_and_external_oracle():
    program=compile_formulas(LOSS,GRADIENT)
    historical=legacy.parse_program(program.to_json())
    for case in grader.development_cases():
        actual=program.evaluate(case.value)
        expected=legacy.execute(historical,case.value)
        assert all(np.array_equal(a,b) for a,b in zip(actual,expected))
        assert grader.grade(case,*actual)['passed']
    wrong=compile_formulas(LOSS,'0')
    assert not grader.grade(grader.development_cases()[0],*wrong.evaluate(grader.development_cases()[0].value))['passed']


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('value',[-80,-20,-.1,0,.1,20,80,100])
def test_softplus_and_supplied_derivative_against_decimal(dtype,value):
    x=np.asarray(value,dtype=dtype)
    program=compile_formulas('where(x<=0,log1p(exp(x)),x+log1p(exp(-x)))',
                             'where(x<=0,exp(x)/(1+exp(x)),1/(1+exp(-x)))')
    actual=program.evaluate(x)
    references=[]
    for precision in (160,220):
        with localcontext() as context:
            context.prec=precision
            exponential=Decimal.from_float(float(x)).exp()
            references.append(((1+exponential).ln(),exponential/(1+exponential)))
    with localcontext() as context:
        context.prec=120
        for a,low,high in zip(actual,*references):
            assert abs(low/high-1)<Decimal('1e-90')
            assert abs(Decimal.from_float(float(a))/high-1)<=Decimal('2e-5' if dtype==np.float32 else '2e-12')
    assert all(a.dtype==x.dtype for a in actual)


def test_finite_underflow_is_not_mathematical_verification():
    loss,gradient=compile_formulas('exp(-1000)','0').evaluate(np.float64(1))
    assert loss==gradient==0


def test_forbidden_candidate_cannot_write_a_file(tmp_path):
    sentinel=tmp_path/'never-created'
    with pytest.raises(ValueError):compile_formulas(f'__import__("pathlib").Path({str(sentinel)!r}).write_text("bad")','1')
    assert not sentinel.exists()
