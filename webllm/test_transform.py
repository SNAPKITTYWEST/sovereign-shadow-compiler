"""
test_transform.py
Direct port of test_transform.mjs — same 8 tests, same assertions.
Run: python webllm/test_transform.py
"""

import sys
from webllm.transform import TransformEngine

PASS = '\033[32m  PASS\033[0m'
FAIL = '\033[31m  FAIL\033[0m'

passed = 0
failed = 0


def test(name: str, ok: bool, detail: str = ''):
    global passed, failed
    if ok:
        print(f'{PASS}  {name}')
        passed += 1
    else:
        print(f'{FAIL}  {name}')
        if detail:
            print(f'       {detail}')
        failed += 1


engine = TransformEngine()

print('\nTransformEngine test suite\n')

# 1. double-negation: NOT(NOT(x)) -> x
xml = '<route><not><not><leaf op="ADD" weight="0.05" valid="true"/></not></not></route>'
result = engine.transform(xml)
ok = 'ADD' in result['xml'] and '<not>' not in result['xml']
test('double-negation: NOT(NOT(x)) -> x', ok, result['xml'])

# 2. idempotent-and: AND(MUL, MUL) -> single MUL leaf
xml = '<route><and><leaf op="MUL" weight="0.05" valid="true"/><leaf op="MUL" weight="0.05" valid="true"/></and></route>'
result = engine.transform(xml)
ok = result['xml'].count('<leaf') == 1 and 'MUL' in result['xml']
test('idempotent-and: AND(MUL, MUL) -> single MUL leaf', ok, result['xml'])

# 3. and-short-circuit-false: AND with valid=false leaf -> invalid
xml = '<route><and><leaf op="ADD" weight="0.9" valid="true"/><leaf op="XOR" weight="0.1" valid="false"/></and></route>'
result = engine.transform(xml)
ok = 'valid="false"' in result['xml']
test('and-short-circuit-false: AND with valid=false leaf -> invalid', ok, result['xml'])

# 4. not-memset-to-xor: NOT(MEMSET) emits XOR leaf
xml = '<route><not><leaf op="MEMSET" weight="0.05" valid="true"/></not></route>'
result = engine.transform(xml)
ok = 'XOR' in result['xml'] and 'MEMSET' not in result['xml']
test('not-memset-to-xor: NOT(MEMSET) emits XOR leaf', ok, result['xml'])

# 5. and-memcpy-memset-to-memcpy: AND(MEMCPY, MEMSET) -> single MEMCPY leaf
xml = '<route><and><leaf op="MEMCPY" weight="0.9" valid="true"/><leaf op="MEMSET" weight="0.3" valid="true"/></and></route>'
result = engine.transform(xml)
ok = 'MEMCPY' in result['xml'] and 'MEMSET' not in result['xml'] and result['xml'].count('<leaf') == 1
test('and-memcpy-memset-to-memcpy: AND(MEMCPY, MEMSET) -> single MEMCPY leaf', ok, result['xml'])

# 6. entropyReduce: depth>3 AST flattens to <or> of all leaves
xml = (
    '<route><and>'
    '<or><leaf op="ADD" weight="0.5" valid="true"/>'
    '<not><leaf op="MUL" weight="0.3" valid="true"/></not></or>'
    '<leaf op="XOR" weight="0.2" valid="true"/>'
    '</and></route>'
)
result = engine.entropy_reduce(xml, depth_threshold=3)
ok = result['reduced'] and '<or>' in result['xml']
test('entropyReduce: depth>3 AST flattens to <or> of all leaves', ok, str(result))

# 7. transform log records fired rules
xml = '<route><not><not><leaf op="LOOP" weight="0.05" valid="true"/></not></not></route>'
result = engine.transform(xml)
ok = len(result['log']) > 0 and result['log'][0]['rule'] == 'double-negation-elimination'
test('transform log records fired rules', ok, str(result['log']))

# 8. no-op: single valid leaf is unchanged with empty log
xml = '<route><leaf op="ADD" weight="0.05" valid="true"/></route>'
result = engine.transform(xml)
ok = result['xml'] == xml and result['log'] == []
test('no-op: single valid leaf is unchanged with empty log', ok, str(result['log']))

# ── Summary ──────────────────────────────────────────────────────────────────
print(f'\n{passed + failed} tests: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
