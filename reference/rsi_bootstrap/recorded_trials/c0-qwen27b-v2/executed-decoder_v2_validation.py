import json
from reference.rsi_bootstrap import c0,expressions
def validate_member(node, k=22, d=16):
    if k < 1 or d < 1:
        raise ValueError('Decoder complexity budget exceeded')
    if list(node) in (['input'], ['const']):
        return
    op = node['op']
    args = node['args']
    if op in {'neg', 'exp', 'expm1', 'log', 'log1p'} and k >= 2 and (d >= 2):
        validate_member(args[0], k - 1, d - 1)
    elif op in {'add', 'sub', 'mul', 'div'} and k >= 3 and (d >= 2):
        for child in args:
            validate_member(child, (k - 1) // 2, d - 1)
    elif op == 'where' and k >= 6 and (d >= 3):
        for child in args[0]['args']:
            validate_member(child, (k - 2) // 4, d - 2)
        for child in args[1:]:
            validate_member(child, (k - 2) // 4, d - 1)
    else:
        raise ValueError('Decoder complexity/type budget exceeded')

def validate_decoded(content, expected=None):
    import re
    answer = json.loads(content, object_pairs_hook=c0._object, parse_constant=c0._nonfinite)
    if not isinstance(answer, dict) or list(answer) != ['program', 'explanation']:
        raise ValueError('Wrong envelope or field order')
    program = answer['program']
    if not isinstance(program, dict) or list(program) != ['loss', 'gradient']:
        raise ValueError('Wrong program field order')
    expressions.parse_program(json.dumps(program, allow_nan=False))
    validate_member(program['loss'])
    validate_member(program['gradient'])
    explanation = answer['explanation']
    if not isinstance(explanation, str) or re.fullmatch('[A-Za-z][A-Za-z0-9 .,:;/()_+*=\\-]{0,127}', explanation) is None:
        raise ValueError('Explanation violates frozen ASCII grammar')
    if not content.startswith('{') or '\\' in content:
        raise ValueError('Grammar requires literal ASCII field strings and no leading space')
    for outside in re.split('"[^"]*"', content):
        if any((len(m.group()) > 2 for m in re.finditer('\\s+', outside))):
            raise ValueError('Whitespace exceeds frozen grammar')

    def order(node):
        keys = list(node)
        if keys in (['input'], ['const']):
            return
        if keys != ['op', 'args']:
            raise ValueError('Wrong node field order')
        for child in node['args']:
            order(child)
    order(program['loss'])
    order(program['gradient'])
    if expected is not None and content != json.dumps(expected, separators=(',', ':')):
        raise ValueError('Literal constraint did not hold exactly')
    return answer
