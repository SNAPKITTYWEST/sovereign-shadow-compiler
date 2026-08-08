"""
tests/test_plasma.py
Hardened tests for PlasmaGate seal/validate/tamper detection.
"""

import pytest
from plasma.gate import PlasmaGate, PlasmaState


def _make_state(**kwargs) -> PlasmaState:
    defaults = dict(
        node_id='test_node',
        tensor_repr='(0.7071+0.2357j)',
        split='train',
        created_by='test',
        review_status='approved',
        weight=0.9,
        valid=True,
        route_from='input',
        route_to='ADD',
    )
    defaults.update(kwargs)
    return PlasmaState(**defaults)


gate = PlasmaGate()


# ── Seal + validate roundtrip ─────────────────────────────────────────────────

def test_seal_and_validate_roundtrip():
    xml = gate.seal(_make_state())
    r = gate.validate(xml)
    assert r['valid'] is True
    assert r['errors'] == []

def test_seal_produces_proof_hash():
    xml = gate.seal(_make_state())
    assert '<proof>' in xml
    assert '<hash>' in xml

def test_seal_produces_source_sha256():
    xml = gate.seal(_make_state())
    assert 'source_sha256' in xml

def test_validate_returns_state_id():
    xml = gate.seal(_make_state(node_id='my_node'))
    r = gate.validate(xml)
    assert r['state_id'] != ''  # state_id is a UUID prefix, not node_id

def test_validate_returns_weight():
    xml = gate.seal(_make_state(weight=0.42))
    r = gate.validate(xml)
    assert r['weight'] == pytest.approx(0.42)

def test_seal_is_deterministic():
    """Same state → same hash every time."""
    s = _make_state()
    xml1 = gate.seal(s)
    xml2 = gate.seal(s)
    # Extract hash from both
    def extract_hash(xml):
        import re
        m = re.search(r'<hash>([^<]+)</hash>', xml)
        return m.group(1) if m else ''
    assert extract_hash(xml1) == extract_hash(xml2)


# ── Tamper detection ──────────────────────────────────────────────────────────

def test_tamper_weight_fails_validation():
    xml = gate.seal(_make_state(weight=0.9))
    xml_tampered = xml.replace('<weight>0.9</weight>', '<weight>99.9</weight>')
    r = gate.validate(xml_tampered)
    assert r['valid'] is False

def test_tamper_tensor_fails_validation():
    xml = gate.seal(_make_state(tensor_repr='(0.5+0.5j)'))
    xml_tampered = xml.replace('(0.5+0.5j)', '(1.0+0.0j)')
    r = gate.validate(xml_tampered)
    assert r['valid'] is False

def test_tamper_route_fails_validation():
    xml = gate.seal(_make_state(route_to='ADD'))
    xml_tampered = xml.replace('"ADD"', '"MUL"')
    r = gate.validate(xml_tampered)
    assert r['valid'] is False

def test_tamper_hash_itself_fails():
    xml = gate.seal(_make_state())
    xml_tampered = xml.replace('<hash>', '<hash>TAMPERED')
    r = gate.validate(xml_tampered)
    assert r['valid'] is False


# ── Invalid state inputs ──────────────────────────────────────────────────────

def test_invalid_state_valid_false():
    xml = gate.seal(_make_state(valid=False))
    r = gate.validate(xml)
    # valid=false state → validation must report invalid
    assert r['valid'] is False

def test_validate_empty_string():
    r = gate.validate('')
    assert r['valid'] is False

def test_validate_garbage_xml():
    r = gate.validate('not xml at all')
    assert r['valid'] is False

def test_validate_missing_proof():
    xml = gate.seal(_make_state())
    import re
    xml_no_proof = re.sub(r'<proof>.*?</proof>', '', xml, flags=re.DOTALL)
    r = gate.validate(xml_no_proof)
    assert r['valid'] is False


# ── from_entropy factory ──────────────────────────────────────────────────────

def test_from_entropy_roundtrip():
    entropy = complex(0.7071, 0.2357)
    constraint = {'valid': True, 'magnitude': 0.74, 'phase': 0.32,
                  'warnings': [], 'force_op': None}
    state = gate.from_entropy(entropy, 'ADD', constraint)
    xml = gate.seal(state)
    r = gate.validate(xml)
    assert r['valid'] is True

def test_from_entropy_invalid_constraint():
    entropy = complex(0.0, 0.0)
    constraint = {'valid': False, 'magnitude': 0.0, 'phase': 0.0,
                  'warnings': ['zero magnitude'], 'force_op': None}
    state = gate.from_entropy(entropy, 'ADD', constraint)
    assert state.valid is False
