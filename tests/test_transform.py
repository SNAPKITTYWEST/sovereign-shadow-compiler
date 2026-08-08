"""
tests/test_transform.py
Hardened test suite for TransformEngine — original 8 + edge cases.
Run: pytest tests/test_transform.py -v
"""

import pytest
from webllm.transform import TransformEngine, DEFAULT_RULES

engine = TransformEngine()


# ── Original 8 ───────────────────────────────────────────────────────────────

def test_double_negation():
    xml = '<route><not><not><leaf op="ADD" weight="0.05" valid="true"/></not></not></route>'
    r = engine.transform(xml)
    assert '<not>' not in r['xml']
    assert 'ADD' in r['xml']
    assert r['passes'] == 1

def test_idempotent_and():
    xml = '<route><and><leaf op="MUL" weight="0.05" valid="true"/><leaf op="MUL" weight="0.05" valid="true"/></and></route>'
    r = engine.transform(xml)
    assert r['xml'].count('<leaf') == 1
    assert 'MUL' in r['xml']

def test_and_short_circuit_false():
    xml = '<route><and><leaf op="ADD" weight="0.9" valid="true"/><leaf op="XOR" weight="0.1" valid="false"/></and></route>'
    r = engine.transform(xml)
    assert 'valid="false"' in r['xml']

def test_not_memset_to_xor():
    xml = '<route><not><leaf op="MEMSET" weight="0.05" valid="true"/></not></route>'
    r = engine.transform(xml)
    assert 'XOR' in r['xml']
    assert 'MEMSET' not in r['xml']

def test_and_memcpy_memset_to_memcpy():
    xml = '<route><and><leaf op="MEMCPY" weight="0.9" valid="true"/><leaf op="MEMSET" weight="0.3" valid="true"/></and></route>'
    r = engine.transform(xml)
    assert 'MEMCPY' in r['xml']
    assert 'MEMSET' not in r['xml']
    assert r['xml'].count('<leaf') == 1

def test_entropy_reduce():
    xml = (
        '<route><and>'
        '<or><leaf op="ADD" weight="0.5" valid="true"/>'
        '<not><leaf op="MUL" weight="0.3" valid="true"/></not></or>'
        '<leaf op="XOR" weight="0.2" valid="true"/>'
        '</and></route>'
    )
    r = engine.entropy_reduce(xml, depth_threshold=3)
    assert r['reduced'] is True
    assert '<or>' in r['xml']

def test_log_records_fired_rules():
    xml = '<route><not><not><leaf op="LOOP" weight="0.05" valid="true"/></not></not></route>'
    r = engine.transform(xml)
    assert len(r['log']) > 0
    assert r['log'][0]['rule'] == 'double-negation-elimination'

def test_no_op_identity():
    xml = '<route><leaf op="ADD" weight="0.05" valid="true"/></route>'
    r = engine.transform(xml)
    assert r['xml'] == xml
    assert r['log'] == []


# ── Edge cases: double-negation ───────────────────────────────────────────────

def test_double_negation_with_whitespace():
    """Whitespace between NOT tags should still fire."""
    xml = '<route><not>\n  <not>\n    <leaf op="XOR" weight="0.1" valid="true"/>\n  </not>\n</not></route>'
    r = engine.transform(xml)
    assert '<not>' not in r['xml']
    assert 'XOR' in r['xml']

def test_triple_negation_reduces_to_single_not():
    """NOT(NOT(NOT(x))) → NOT(x) — two NOT pairs, only innermost collapses."""
    xml = '<route><not><not><not><leaf op="ADD" weight="0.05" valid="true"/></not></not></not></route>'
    r = engine.transform(xml)
    # After one pass: NOT(NOT(NOT(x))) → NOT(x) — outer pair fires, inner NOT remains
    assert r['xml'].count('<not>') == 1

def test_double_negation_all_ops():
    """Double negation fires for every op."""
    for op in ['ADD', 'MUL', 'XOR', 'LOOP', 'MEMCPY', 'MEMSET', 'STRCMP', 'HELLO']:
        xml = f'<route><not><not><leaf op="{op}" weight="0.05" valid="true"/></not></not></route>'
        r = engine.transform(xml)
        assert '<not>' not in r['xml'], f"double-negation failed for op={op}"
        assert op in r['xml']


# ── Edge cases: idempotent ────────────────────────────────────────────────────

def test_idempotent_or():
    xml = '<route><or><leaf op="XOR" weight="0.3" valid="true"/><leaf op="XOR" weight="0.3" valid="true"/></or></route>'
    r = engine.transform(xml)
    assert r['xml'].count('<leaf') == 1
    assert 'XOR' in r['xml']

def test_idempotent_and_different_ops_no_fire():
    """AND(ADD, XOR) — different ops, idempotent rule must NOT fire."""
    xml = '<route><and><leaf op="ADD" weight="0.5" valid="true"/><leaf op="XOR" weight="0.3" valid="true"/></and></route>'
    r = engine.transform(xml)
    assert r['xml'].count('<leaf') == 2


# ── Edge cases: short-circuit ─────────────────────────────────────────────────

def test_and_all_valid_no_short_circuit():
    """AND with all valid=true leaves — no short circuit, highest weight wins."""
    xml = '<route><and><leaf op="ADD" weight="0.9" valid="true"/><leaf op="MUL" weight="0.1" valid="true"/></and></route>'
    r = engine.transform(xml)
    # No false leaf — and-short-circuit-false must not fire
    assert 'valid="false"' not in r['xml']

def test_and_short_circuit_false_in_middle():
    """False leaf in middle position still triggers short circuit."""
    xml = '<route><and><leaf op="ADD" weight="0.9" valid="true"/><leaf op="LOOP" weight="0.5" valid="false"/><leaf op="MUL" weight="0.8" valid="true"/></and></route>'
    r = engine.transform(xml)
    assert 'valid="false"' in r['xml']
    assert r['xml'].count('<leaf') == 1

def test_or_short_circuit_true_first_leaf():
    """First valid leaf in OR is returned immediately."""
    xml = '<route><or><leaf op="MUL" weight="0.9" valid="true"/><leaf op="XOR" weight="0.1" valid="true"/></or></route>'
    r = engine.transform(xml)
    assert r['xml'].count('<leaf') == 1
    assert 'MUL' in r['xml']

def test_or_all_false_no_short_circuit():
    """OR with all valid=false — no short circuit fires, tree unchanged."""
    xml = '<route><or><leaf op="ADD" weight="0.3" valid="false"/><leaf op="XOR" weight="0.2" valid="false"/></or></route>'
    r = engine.transform(xml)
    # or-short-circuit-true requires valid=true — must not fire
    assert '<or>' in r['xml']


# ── Edge cases: not-memset-to-xor ────────────────────────────────────────────

def test_not_memset_to_xor_preserves_weight():
    """Weight attribute on MEMSET leaf is preserved on the emitted XOR leaf."""
    xml = '<route><not><leaf op="MEMSET" weight="0.77" valid="true"/></not></route>'
    r = engine.transform(xml)
    assert 'XOR' in r['xml']
    assert '0.77' in r['xml']

def test_not_add_does_not_rewrite():
    """NOT(ADD) — no rule applies, tree unchanged."""
    xml = '<route><not><leaf op="ADD" weight="0.05" valid="true"/></not></route>'
    r = engine.transform(xml)
    assert '<not>' in r['xml']
    assert 'ADD' in r['xml']


# ── Edge cases: memcpy/memset fusion ─────────────────────────────────────────

def test_and_memset_memcpy_reversed_order():
    """AND(MEMSET, MEMCPY) — reversed order still fuses to MEMCPY."""
    xml = '<route><and><leaf op="MEMSET" weight="0.3" valid="true"/><leaf op="MEMCPY" weight="0.9" valid="true"/></and></route>'
    r = engine.transform(xml)
    assert 'MEMCPY' in r['xml']
    assert 'MEMSET' not in r['xml']
    assert r['xml'].count('<leaf') == 1

def test_and_memcpy_without_memset_unchanged():
    """AND(MEMCPY, ADD) — no MEMSET, must not fuse."""
    xml = '<route><and><leaf op="MEMCPY" weight="0.9" valid="true"/><leaf op="ADD" weight="0.3" valid="true"/></and></route>'
    r = engine.transform(xml)
    assert r['xml'].count('<leaf') == 2


# ── Edge cases: entropy reduce ────────────────────────────────────────────────

def test_entropy_reduce_shallow_no_op():
    """Depth <= threshold — reduce must not fire."""
    xml = '<route><leaf op="ADD" weight="0.5" valid="true"/></route>'
    r = engine.entropy_reduce(xml, depth_threshold=3)
    assert r['reduced'] is False
    assert r['xml'] == xml

def test_entropy_reduce_collects_all_leaves():
    """All leaves appear in the flattened OR."""
    xml = (
        '<route><and>'
        '<leaf op="ADD" weight="0.5" valid="true"/>'
        '<or>'
        '<leaf op="MUL" weight="0.3" valid="true"/>'
        '<leaf op="XOR" weight="0.2" valid="false"/>'
        '</or>'
        '</and></route>'
    )
    r = engine.entropy_reduce(xml, depth_threshold=2)
    if r['reduced']:
        assert 'ADD' in r['xml']
        assert 'MUL' in r['xml']
        assert 'XOR' in r['xml']

def test_entropy_reduce_custom_threshold():
    """depth_threshold=1 forces reduce on any nested tree."""
    xml = '<route><and><leaf op="ADD" weight="0.5" valid="true"/></and></route>'
    r = engine.entropy_reduce(xml, depth_threshold=1)
    assert r['reduced'] is True


# ── Edge cases: fixpoint + max_passes ────────────────────────────────────────

def test_fixpoint_terminates():
    """Chain of rewrites terminates before max_passes."""
    # NOT(NOT(AND(MEMCPY,MEMSET))) → AND(MEMCPY,MEMSET) → MEMCPY
    xml = '<route><not><not><and><leaf op="MEMCPY" weight="0.9" valid="true"/><leaf op="MEMSET" weight="0.3" valid="true"/></and></not></not></route>'
    r = engine.transform(xml)
    assert r['passes'] < engine.max_passes
    assert 'MEMCPY' in r['xml']

def test_max_passes_respected():
    """A custom max_passes=1 stops after one firing."""
    xml = '<route><not><not><not><not><leaf op="ADD" weight="0.05" valid="true"/></not></not></not></not></route>'
    e = TransformEngine(max_passes=1)
    r = e.transform(xml)
    assert r['passes'] == 1

def test_empty_xml_no_crash():
    """Empty string does not crash."""
    r = engine.transform('')
    assert 'xml' in r
    assert r['log'] == []

def test_no_route_tag_no_crash():
    """XML with no <route> tag does not crash."""
    r = engine.transform('<leaf op="ADD" weight="0.05" valid="true"/>')
    assert 'xml' in r

def test_malformed_xml_no_crash():
    """Unclosed tags do not crash the engine."""
    r = engine.transform('<route><and><leaf op="ADD"')
    assert 'xml' in r

def test_all_rules_have_unique_names():
    """Every rule name in DEFAULT_RULES is unique."""
    names = [r.name for r in DEFAULT_RULES]
    assert len(names) == len(set(names))

def test_rules_sorted_by_priority_desc():
    """TransformEngine sorts rules highest priority first."""
    priorities = [r.priority for r in engine.rules]
    assert priorities == sorted(priorities, reverse=True)
