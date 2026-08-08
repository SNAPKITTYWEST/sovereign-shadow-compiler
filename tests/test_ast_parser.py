"""
tests/test_ast_parser.py
Hardened tests for the XML boolean AST parser.
"""

import pytest
from webllm.ast_parser import parse_routing_ast, VALID_OPS


# ── Basic leaf evaluation ─────────────────────────────────────────────────────

def test_single_valid_leaf():
    xml = '<route><leaf op="ADD" weight="0.5" valid="true"/></route>'
    r = parse_routing_ast(xml)
    assert r['op'] == 'ADD'
    assert r['valid'] is True
    assert r['weight'] == 0.5

def test_single_invalid_leaf():
    xml = '<route><leaf op="XOR" weight="0.3" valid="false"/></route>'
    r = parse_routing_ast(xml)
    assert r['op'] == 'XOR'
    assert r['valid'] is False

def test_all_valid_ops_parse():
    for op in VALID_OPS:
        xml = f'<route><leaf op="{op}" weight="0.1" valid="true"/></route>'
        r = parse_routing_ast(xml)
        assert r['op'] == op
        assert r['valid'] is True

def test_unknown_op_returns_invalid():
    xml = '<route><leaf op="UNKNOWN" weight="0.5" valid="true"/></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is False
    assert 'reason' in r

def test_op_case_insensitive():
    """op attribute is normalised to uppercase."""
    xml = '<route><leaf op="add" weight="0.5" valid="true"/></route>'
    r = parse_routing_ast(xml)
    assert r['op'] == 'ADD'

def test_default_weight_when_missing():
    xml = '<route><leaf op="ADD" valid="true"/></route>'
    r = parse_routing_ast(xml)
    assert r['weight'] == 0.05

def test_default_valid_false_when_missing():
    xml = '<route><leaf op="ADD" weight="0.5"/></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is False


# ── AND node ──────────────────────────────────────────────────────────────────

def test_and_all_valid_returns_highest_weight():
    xml = (
        '<route><and>'
        '<leaf op="ADD" weight="0.3" valid="true"/>'
        '<leaf op="MUL" weight="0.9" valid="true"/>'
        '</and></route>'
    )
    r = parse_routing_ast(xml)
    assert r['op'] == 'MUL'
    assert r['valid'] is True

def test_and_one_invalid_propagates():
    xml = (
        '<route><and>'
        '<leaf op="ADD" weight="0.9" valid="true"/>'
        '<leaf op="XOR" weight="0.1" valid="false"/>'
        '</and></route>'
    )
    r = parse_routing_ast(xml)
    assert r['valid'] is False

def test_and_empty_returns_invalid():
    xml = '<route><and></and></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is False

def test_and_three_children_all_valid():
    xml = (
        '<route><and>'
        '<leaf op="ADD" weight="0.1" valid="true"/>'
        '<leaf op="MUL" weight="0.5" valid="true"/>'
        '<leaf op="XOR" weight="0.9" valid="true"/>'
        '</and></route>'
    )
    r = parse_routing_ast(xml)
    assert r['op'] == 'XOR'
    assert r['valid'] is True


# ── OR node ───────────────────────────────────────────────────────────────────

def test_or_first_valid_returned():
    xml = (
        '<route><or>'
        '<leaf op="ADD" weight="0.9" valid="true"/>'
        '<leaf op="MUL" weight="0.1" valid="true"/>'
        '</or></route>'
    )
    r = parse_routing_ast(xml)
    assert r['op'] == 'ADD'
    assert r['valid'] is True

def test_or_skips_invalid_returns_valid():
    xml = (
        '<route><or>'
        '<leaf op="ADD" weight="0.9" valid="false"/>'
        '<leaf op="MUL" weight="0.1" valid="true"/>'
        '</or></route>'
    )
    r = parse_routing_ast(xml)
    assert r['op'] == 'MUL'
    assert r['valid'] is True

def test_or_all_invalid_returns_invalid():
    xml = (
        '<route><or>'
        '<leaf op="ADD" weight="0.5" valid="false"/>'
        '<leaf op="XOR" weight="0.3" valid="false"/>'
        '</or></route>'
    )
    r = parse_routing_ast(xml)
    assert r['valid'] is False

def test_or_empty_returns_invalid():
    xml = '<route><or></or></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is False


# ── NOT node ──────────────────────────────────────────────────────────────────

def test_not_flips_valid_to_invalid():
    xml = '<route><not><leaf op="ADD" weight="0.5" valid="true"/></not></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is False
    assert r['op'] == 'ADD'

def test_not_flips_invalid_to_valid():
    xml = '<route><not><leaf op="XOR" weight="0.3" valid="false"/></not></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is True
    assert r['op'] == 'XOR'

def test_not_empty_returns_invalid():
    xml = '<route><not></not></route>'
    r = parse_routing_ast(xml)
    assert r['valid'] is False


# ── Nesting + depth tracking ──────────────────────────────────────────────────

def test_nested_and_or():
    xml = (
        '<route><and>'
        '<leaf op="ADD" weight="0.5" valid="true"/>'
        '<or>'
        '<leaf op="XOR" weight="0.3" valid="false"/>'
        '<leaf op="MUL" weight="0.8" valid="true"/>'
        '</or>'
        '</and></route>'
    )
    r = parse_routing_ast(xml)
    assert r['valid'] is True
    assert r['ast_depth'] >= 2

def test_node_count_accurate():
    xml = (
        '<route><and>'
        '<leaf op="ADD" weight="0.5" valid="true"/>'
        '<leaf op="MUL" weight="0.3" valid="true"/>'
        '</and></route>'
    )
    r = parse_routing_ast(xml)
    # route + and + leaf + leaf = 4 nodes
    assert r['node_count'] == 4

def test_ast_depth_single_leaf():
    xml = '<route><leaf op="ADD" weight="0.5" valid="true"/></route>'
    r = parse_routing_ast(xml)
    assert r['ast_depth'] >= 1


# ── Error/malformed inputs ────────────────────────────────────────────────────

def test_no_route_tag():
    r = parse_routing_ast('<and><leaf op="ADD" weight="0.5" valid="true"/></and>')
    assert r['valid'] is False
    assert 'reason' in r

def test_unclosed_route():
    r = parse_routing_ast('<route><leaf op="ADD" weight="0.5" valid="true"/>')
    assert r['valid'] is False

def test_empty_string():
    r = parse_routing_ast('')
    assert r['valid'] is False

def test_garbage_xml():
    r = parse_routing_ast('not xml at all <<<>>>')
    assert r['valid'] is False

def test_route_tag_boundary_check():
    """<router> must not be confused with <route>."""
    r = parse_routing_ast('<router><leaf op="ADD" weight="0.5" valid="true"/></router>')
    assert r['valid'] is False

def test_bare_leaf_without_route():
    """A bare self-closing leaf (no route wrapper) is handled."""
    r = parse_routing_ast('<leaf op="ADD" weight="0.5" valid="true"/>')
    assert r['op'] == 'ADD'
    assert r['valid'] is True


# ── XXE hardening ─────────────────────────────────────────────────────────────

def test_xxe_doctype_rejected():
    from webllm.xml_router import validate_xxe_output
    with pytest.raises((ValueError, Exception)):
        validate_xxe_output('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>')

def test_xxe_entity_ref_rejected():
    from webllm.xml_router import validate_xxe_output
    with pytest.raises((ValueError, Exception)):
        validate_xxe_output('<route>&xxe;</route>')

def test_xxe_system_identifier_rejected():
    from webllm.xml_router import validate_xxe_output
    with pytest.raises((ValueError, Exception)):
        validate_xxe_output('SYSTEM "/etc/passwd"')

def test_clean_xml_passes_xxe():
    from webllm.xml_router import validate_xxe_output
    xml = '<route><leaf op="ADD" weight="0.05" valid="true"/></route>'
    assert validate_xxe_output(xml) == xml
