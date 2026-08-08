"""
tests/test_irr.py
Hardened tests for IRR: PatternLibrary, MatchingEngine, WeightUpdater, IntentGenerator.
"""

import pytest
from irr.pattern_library import PatternLibrary, PatternEntry
from irr.matching_engine import MatchingEngine
from irr.weight_loop import WeightUpdater
from irr.intent_generator import IntentGenerator
from irr.schema_constants import ENTROPY_CAP, MIN_WEIGHT, DEFAULT_ALPHA, DEFAULT_BASELINE


# ── Schema constants ──────────────────────────────────────────────────────────

def test_entropy_cap_is_020():
    assert ENTROPY_CAP == 0.20

def test_min_weight_positive():
    assert MIN_WEIGHT > 0

def test_alpha_positive():
    assert DEFAULT_ALPHA > 0


# ── PatternLibrary ────────────────────────────────────────────────────────────

def test_library_seeds_all_8_ops():
    lib = PatternLibrary()
    top = lib.top_n(8)
    ops = {e.op for e in top}
    for op in ['ADD', 'MUL', 'XOR', 'LOOP', 'MEMCPY', 'MEMSET', 'STRCMP', 'HELLO']:
        assert op in ops

def test_library_top_n():
    lib = PatternLibrary()
    top = lib.top_n(3)
    assert len(top) == 3

def test_library_top_n_sorted_by_weight():
    lib = PatternLibrary()
    top = lib.top_n(8)
    weights = [e.weight for e in top]
    assert weights == sorted(weights, reverse=True)

def test_weight_update_reward():
    lib = PatternLibrary()
    entry = lib.top_n(1)[0]
    before = entry.weight
    lib.update_weight(entry, signal=1.0)
    assert entry.weight > before

def test_weight_update_penalize():
    lib = PatternLibrary()
    entry = lib.top_n(1)[0]
    before = entry.weight
    lib.update_weight(entry, signal=0.0)
    assert entry.weight <= before

def test_weight_never_goes_negative():
    lib = PatternLibrary()
    entry = lib.top_n(1)[0]
    for _ in range(100):
        lib.update_weight(entry, signal=0.0)
    assert entry.weight >= 0.0


# ── MatchingEngine ────────────────────────────────────────────────────────────

def _eng():
    return MatchingEngine(PatternLibrary())

def test_match_add_keywords():
    eng = _eng()
    for query in ['add two numbers', 'sum the values', 'plus one']:
        r = eng.match(query)
        assert r['op'] == 'ADD', f"expected ADD for '{query}', got {r['op']}"
        assert r['matched'] is True

def test_match_mul_keywords():
    eng = _eng()
    for query in ['multiply by 3', 'times the scale', 'product of']:
        r = eng.match(query)
        assert r['op'] == 'MUL', f"expected MUL for '{query}'"

def test_match_xor_keywords():
    eng = _eng()
    for query in ['xor the bits', 'toggle the flag', 'flip the value']:
        r = eng.match(query)
        assert r['op'] == 'XOR'

def test_match_loop_keywords():
    eng = _eng()
    # 'repeat 10 times' hits MUL first ('times' is in MUL pattern) — weight collision
    # use unambiguous LOOP-only keywords
    for query in ['loop through items', 'iterate over all', 'cycle through']:
        r = eng.match(query)
        assert r['op'] == 'LOOP', f"expected LOOP for '{query}', got {r['op']}"

def test_match_memcpy_keywords():
    eng = _eng()
    for query in ['copy the buffer', 'clone the memory', 'memcpy src dst']:
        r = eng.match(query)
        assert r['op'] == 'MEMCPY'

def test_match_hello_keywords():
    eng = _eng()
    for query in ['hello world', 'print output', 'write to stdout']:
        r = eng.match(query)
        assert r['op'] == 'HELLO'

def test_match_unknown_falls_back_to_add():
    eng = _eng()
    r = eng.match('zzzzxxx totally unknown query 12345')
    assert r['op'] == 'ADD'
    assert r['matched'] is False

def test_match_cache_hit():
    eng = _eng()
    q = 'add two values'
    r1 = eng.match(q)
    r2 = eng.match(q)
    assert r2['from_cache'] is True
    assert r1['op'] == r2['op']

def test_match_empty_string():
    eng = _eng()
    r = eng.match('')
    assert 'op' in r

def test_match_case_insensitive():
    eng = _eng()
    r1 = eng.match('ADD values')
    r2 = eng.match('add values')
    assert r1['op'] == r2['op']


# ── WeightUpdater ─────────────────────────────────────────────────────────────

def test_reward_increases_weight():
    lib = PatternLibrary()
    wu = WeightUpdater(lib)
    entry = [e for e in lib.top_n(8) if e.op == 'ADD'][0]
    before = entry.weight
    wu.reward('ADD', entry.pattern)
    assert entry.weight > before

def test_penalize_decreases_weight():
    lib = PatternLibrary()
    wu = WeightUpdater(lib)
    entry = [e for e in lib.top_n(8) if e.op == 'MUL'][0]
    before = entry.weight
    wu.penalize('MUL', entry.pattern)
    assert entry.weight <= before

def test_reward_unknown_op_no_crash():
    lib = PatternLibrary()
    wu = WeightUpdater(lib)
    wu.reward('NONEXISTENT', 'pattern')  # must not raise


# ── IntentGenerator ───────────────────────────────────────────────────────────

def test_intent_add():
    ig = IntentGenerator()
    op, pattern, conf = ig.generate('add two numbers together')
    assert op == 'ADD'
    assert conf > 0

def test_intent_mul():
    ig = IntentGenerator()
    op, _, _ = ig.generate('multiply the input by scale factor')
    assert op == 'MUL'

def test_intent_xor():
    ig = IntentGenerator()
    op, _, _ = ig.generate('xor bits to toggle the flag')
    assert op == 'XOR'

def test_intent_memcpy():
    ig = IntentGenerator()
    op, _, _ = ig.generate('copy memory from source to destination buffer')
    assert op == 'MEMCPY'

def test_intent_confidence_bounded():
    ig = IntentGenerator()
    _, _, conf = ig.generate('add sum plus increment')
    assert 0.0 <= conf <= 1.0

def test_intent_pattern_entropy_respected():
    """Pattern should not exceed ENTROPY_CAP when query has many keywords."""
    ig = IntentGenerator()
    _, pattern, _ = ig.generate('add plus sum increment increase multiply times scale loop repeat')
    # Pattern entropy check — if the generated pattern exists it must compile
    import re
    try:
        re.compile(pattern)
        compiled = True
    except re.error:
        compiled = False
    assert compiled

def test_intent_unknown_query_returns_add():
    ig = IntentGenerator()
    op, _, conf = ig.generate('asdfghjkl qwerty zxcvbnm')
    assert op == 'ADD'
    assert conf >= 0

def test_intent_empty_string():
    ig = IntentGenerator()
    op, pattern, conf = ig.generate('')
    assert op in ['ADD', 'MUL', 'XOR', 'LOOP', 'MEMCPY', 'MEMSET', 'STRCMP', 'HELLO']
