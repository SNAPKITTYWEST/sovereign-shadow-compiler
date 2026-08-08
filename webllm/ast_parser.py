"""
ast_parser.py
XML boolean AST parser for sovereign routing expressions.
Direct port of ast_parser.mjs — no external XML library, pure regex recursion.
Handles: <route>, <and>, <or>, <not>, <leaf op="" weight="" valid=""/>
"""

import re
from typing import Optional

BOOLEAN_TAGS = frozenset(['and', 'or', 'not', 'route'])
VALID_OPS = ['ADD', 'MUL', 'XOR', 'LOOP', 'MEMCPY', 'MEMSET', 'STRCMP', 'HELLO']

_OP_RE     = re.compile(r'op="([^"]+)"')
_WEIGHT_RE = re.compile(r'weight="([^"]+)"')
_VALID_RE  = re.compile(r'valid="([^"]+)"')


def _parse_leaf_attrs(tag: str) -> dict:
    op_m     = _OP_RE.search(tag)
    weight_m = _WEIGHT_RE.search(tag)
    valid_m  = _VALID_RE.search(tag)
    return {
        'op':     op_m.group(1).upper() if op_m else None,
        'weight': float(weight_m.group(1)) if weight_m else 0.05,
        'valid':  valid_m.group(1) == 'true' if valid_m else False,
    }


def _find_next_open_tag(xml: str, tag_name: str, start: int) -> int:
    needle = '<' + tag_name
    i = start
    while i < len(xml):
        idx = xml.find(needle, i)
        if idx == -1:
            return -1
        char_after = xml[idx + 1 + len(tag_name)] if idx + 1 + len(tag_name) < len(xml) else None
        if char_after in ('>', ' ', '\t', '\n', '/', None):
            return idx
        i = idx + 1
    return -1


def _extract_children(xml: str) -> list:
    children = []
    i = 0
    while i < len(xml):
        while i < len(xml) and xml[i] != '<':
            i += 1
        if i >= len(xml):
            break
        if xml[i:i+4] == '<!--':
            end = xml.find('-->', i)
            i = end + 3 if end != -1 else len(xml)
            continue
        if xml[i+1:i+2] == '/':
            end = xml.find('>', i)
            i = end + 1 if end != -1 else len(xml)
            continue
        if xml[i+1:i+2] == '?':
            end = xml.find('?>', i)
            i = end + 2 if end != -1 else len(xml)
            continue

        tag_start = i
        gt_idx = xml.find('>', i)
        if gt_idx == -1:
            i += 1
            continue
        tag_inner = xml[i+1:gt_idx]

        # Self-closing
        if tag_inner.rstrip().endswith('/'):
            tag_name = re.split(r'[\s/]', tag_inner)[0]
            children.append({
                'tag': tag_name,
                'content': '',
                'self_closing': True,
                'raw': xml[tag_start:gt_idx+1],
            })
            i = gt_idx + 1
            continue

        # Paired tag
        tag_name = re.split(r'\s', tag_inner)[0]
        close_tag = '</' + tag_name + '>'
        depth = 1
        j = gt_idx + 1
        found = False
        while j < len(xml) and depth > 0:
            next_open  = _find_next_open_tag(xml, tag_name, j)
            next_close = xml.find(close_tag, j)
            if next_close == -1:
                j = len(xml)
                break
            if next_open != -1 and next_open < next_close:
                depth += 1
                j = next_open + 1
            else:
                depth -= 1
                if depth == 0:
                    close_end = next_close + len(close_tag)
                    children.append({
                        'tag': tag_name,
                        'content': xml[gt_idx+1:next_close],
                        'self_closing': False,
                        'raw': xml[tag_start:close_end],
                    })
                    i = close_end
                    found = True
                    break
                else:
                    j = next_close + 1
        if not found:
            i = gt_idx + 1
    return children


def _eval_node(xml: str, current_depth: int = 0, counters: Optional[dict] = None) -> dict:
    if counters is None:
        counters = {'node_count': 0, 'max_depth': 0}
    counters['node_count'] += 1
    counters['max_depth'] = max(counters['max_depth'], current_depth)

    trimmed = xml.strip()

    # Self-closing leaf
    if re.match(r'^<leaf\s[^>]*/>$', trimmed):
        attrs = _parse_leaf_attrs(trimmed)
        if not attrs['op'] or attrs['op'] not in VALID_OPS:
            return {'op': 'ADD', 'weight': attrs['weight'], 'valid': False,
                    'depth': current_depth, 'reason': f"unknown op: {attrs['op']}"}
        return {'op': attrs['op'], 'weight': attrs['weight'], 'valid': attrs['valid'],
                'depth': current_depth}

    tag_m = re.match(r'^<(\w+)[\s>]', trimmed)
    if not tag_m:
        return {'op': 'ADD', 'weight': 0, 'valid': False,
                'depth': current_depth, 'reason': 'malformed tag'}
    tag_name = tag_m.group(1).lower()

    open_tag_end = trimmed.find('>')
    close_tag = '</' + tag_name + '>'
    close_tag_idx = trimmed.rfind(close_tag)
    if open_tag_end == -1 or close_tag_idx == -1:
        return {'op': 'ADD', 'weight': 0, 'valid': False,
                'depth': current_depth, 'reason': f'malformed {tag_name} tag'}
    inner = trimmed[open_tag_end+1:close_tag_idx]

    if tag_name == 'leaf':
        attrs = _parse_leaf_attrs(trimmed)
        if not attrs['op'] or attrs['op'] not in VALID_OPS:
            return {'op': 'ADD', 'weight': attrs['weight'], 'valid': False,
                    'depth': current_depth, 'reason': f"unknown op: {attrs['op']}"}
        return {'op': attrs['op'], 'weight': attrs['weight'], 'valid': attrs['valid'],
                'depth': current_depth}

    if tag_name == 'route':
        children = _extract_children(inner)
        if not children:
            return {'op': 'ADD', 'weight': 0, 'valid': False,
                    'depth': current_depth, 'reason': 'empty route'}
        return _eval_node(children[0]['raw'], current_depth + 1, counters)

    if tag_name == 'and':
        children = _extract_children(inner)
        if not children:
            return {'op': 'ADD', 'weight': 0, 'valid': False,
                    'depth': current_depth, 'reason': 'and: no children'}
        best = None
        for child in children:
            result = _eval_node(child['raw'], current_depth + 1, counters)
            if not result['valid']:
                return {'op': result['op'], 'weight': result['weight'], 'valid': False,
                        'depth': current_depth, 'reason': 'and: child invalid'}
            if best is None or result['weight'] > best['weight']:
                best = result
        return {**best, 'depth': current_depth}

    if tag_name == 'or':
        children = _extract_children(inner)
        for child in children:
            result = _eval_node(child['raw'], current_depth + 1, counters)
            if result['valid']:
                return {**result, 'depth': current_depth}
        return {'op': 'ADD', 'weight': 0, 'valid': False,
                'depth': current_depth, 'reason': 'or: no valid child'}

    if tag_name == 'not':
        children = _extract_children(inner)
        if not children:
            return {'op': 'ADD', 'weight': 0, 'valid': False,
                    'depth': current_depth, 'reason': 'not: no child'}
        result = _eval_node(children[0]['raw'], current_depth + 1, counters)
        return {**result, 'valid': not result['valid'], 'depth': current_depth}

    return {'op': 'ADD', 'weight': 0, 'valid': False,
            'depth': current_depth, 'reason': f'unknown tag: {tag_name}'}


def parse_routing_ast(xml: str) -> dict:
    route_start = xml.find('<route')
    if route_start == -1:
        leaf_trimmed = xml.strip()
        if re.match(r'^<leaf\s[^>]*/>$', leaf_trimmed):
            counters = {'node_count': 0, 'max_depth': 0}
            result = _eval_node(leaf_trimmed, 0, counters)
            return {**result, 'ast_depth': counters['max_depth'],
                    'node_count': counters['node_count']}
        return {'op': 'ADD', 'weight': 0, 'valid': False,
                'ast_depth': 0, 'node_count': 0, 'reason': 'no <route> element'}

    char_after = xml[route_start + 6] if route_start + 6 < len(xml) else None
    if char_after not in ('>', ' ', '\t', '\n', '/', None):
        return {'op': 'ADD', 'weight': 0, 'valid': False,
                'ast_depth': 0, 'node_count': 0, 'reason': 'no <route> element'}

    route_end = xml.rfind('</route>')
    if route_end == -1:
        return {'op': 'ADD', 'weight': 0, 'valid': False,
                'ast_depth': 0, 'node_count': 0, 'reason': 'unclosed <route>'}

    route_xml = xml[route_start:route_end + len('</route>')]
    counters = {'node_count': 0, 'max_depth': 0}
    result = _eval_node(route_xml, 0, counters)
    return {**result, 'ast_depth': counters['max_depth'],
            'node_count': counters['node_count']}
