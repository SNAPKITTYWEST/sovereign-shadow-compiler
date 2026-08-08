"""
transform.py
AST transformation ruleset for sovereign routing expressions.
Direct port of transform.mjs — same 9 rules, same priority fixpoint.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class TransformRule:
    name: str
    priority: int

    def match(self, xml: str) -> bool:
        raise NotImplementedError

    def apply(self, xml: str) -> str:
        raise NotImplementedError


class DoubleNegationElimination(TransformRule):
    """NOT(NOT(x)) → x"""
    name = "double-negation-elimination"
    priority = 10

    def __init__(self):
        super().__init__(self.name, self.priority)
        self._pat = re.compile(r'<not>\s*<not>([\s\S]*?)</not>\s*</not>')

    def match(self, xml: str) -> bool:
        return bool(self._pat.search(xml))

    def apply(self, xml: str) -> str:
        return self._pat.sub(r'\1', xml)


class IdempotentAnd(TransformRule):
    """AND(X, X) → X"""
    name = "idempotent-and"
    priority = 9

    def __init__(self):
        super().__init__(self.name, self.priority)
        self._pat = re.compile(
            r'<and>\s*(<leaf[^>]*op="([^"]+)"[^>]*/>\s*)<leaf[^>]*op="\2"[^>]*/>\s*</and>'
        )

    def match(self, xml: str) -> bool:
        return bool(self._pat.search(xml))

    def apply(self, xml: str) -> str:
        return self._pat.sub(r'\1', xml)


class IdempotentOr(TransformRule):
    """OR(X, X) → X"""
    name = "idempotent-or"
    priority = 9

    def __init__(self):
        super().__init__(self.name, self.priority)
        self._pat = re.compile(
            r'<or>\s*(<leaf[^>]*op="([^"]+)"[^>]*/>\s*)<leaf[^>]*op="\2"[^>]*/>\s*</or>'
        )

    def match(self, xml: str) -> bool:
        return bool(self._pat.search(xml))

    def apply(self, xml: str) -> str:
        return self._pat.sub(r'\1', xml)


class OrTautology(TransformRule):
    """OR(X, NOT(X)) → X with valid=true"""
    name = "or-tautology"
    priority = 8

    def __init__(self):
        super().__init__(self.name, self.priority)
        self._pat1 = re.compile(
            r'<or>\s*(<leaf[^>]*op="([^"]+)"[^>]*/>\s*)<not>\s*<leaf[^>]*op="\2"[^>]*/>\s*</not>\s*</or>'
        )
        self._pat2 = re.compile(
            r'<or>\s*<not>\s*<leaf[^>]*op="([^"]+)"[^>]*/>\s*</not>\s*(<leaf[^>]*op="\1"[^>]*/>\s*)</or>'
        )

    def _force_valid(self, leaf: str) -> str:
        if 'valid=' in leaf:
            return re.sub(r'valid="[^"]*"', 'valid="true"', leaf)
        return leaf.replace('/>', ' valid="true"/>')

    def match(self, xml: str) -> bool:
        return bool(self._pat1.search(xml) or self._pat2.search(xml))

    def apply(self, xml: str) -> str:
        def sub1(m):
            return self._force_valid(m.group(1).strip())
        def sub2(m):
            return self._force_valid(m.group(2).strip())
        result = self._pat1.sub(sub1, xml)
        result = self._pat2.sub(sub2, result)
        return result


class AndShortCircuitFalse(TransformRule):
    """AND containing any valid=false leaf → invalid leaf"""
    name = "and-short-circuit-false"
    priority = 7
    _outer = re.compile(r'<and>([\s\S]*?)</and>')
    _false_leaf = re.compile(r'<leaf[^>]*valid="false"[^>]*/>')

    def __init__(self):
        super().__init__(self.name, self.priority)

    def match(self, xml: str) -> bool:
        return bool(re.search(r'<and>[\s\S]*?<leaf[^>]*valid="false"[^>]*/>[\s\S]*?</and>', xml))

    def apply(self, xml: str) -> str:
        def replacer(m):
            inner = m.group(1)
            if self._false_leaf.search(inner):
                return '<leaf op="ADD" weight="0.0" valid="false"/>'
            return m.group(0)
        return self._outer.sub(replacer, xml)


class OrShortCircuitTrue(TransformRule):
    """OR where first child is valid=true → emit that leaf"""
    name = "or-short-circuit-true"
    priority = 7
    _pat = re.compile(r'<or>\s*(<leaf[^>]*valid="true"[^>]*/>)[\s\S]*?</or>')

    def __init__(self):
        super().__init__(self.name, self.priority)

    def match(self, xml: str) -> bool:
        return bool(self._pat.search(xml))

    def apply(self, xml: str) -> str:
        return self._pat.sub(r'\1', xml)


class WeightNormalizationAnd(TransformRule):
    """AND where all leaves < 0.10 weight → keep highest-weight leaf"""
    name = "weight-normalization-and"
    priority = 6
    _outer = re.compile(r'<and>([\s\S]*?)</and>')
    _leaf = re.compile(r'<leaf[^>]*/>')
    _weight = re.compile(r'weight="([^"]+)"')

    def __init__(self):
        super().__init__(self.name, self.priority)

    def _all_low(self, inner: str) -> bool:
        leaves = self._leaf.findall(inner)
        if not leaves:
            return False
        return all(
            float(m.group(1)) < 0.10
            for l in leaves
            for m in [self._weight.search(l)]
            if m
        )

    def match(self, xml: str) -> bool:
        return any(self._all_low(m.group(1)) for m in self._outer.finditer(xml))

    def apply(self, xml: str) -> str:
        def replacer(m):
            inner = m.group(1)
            if not self._all_low(inner):
                return m.group(0)
            leaves = self._leaf.findall(inner)
            best = leaves[0]
            best_w = -1.0
            for l in leaves:
                wm = self._weight.search(l)
                w = float(wm.group(1)) if wm else 0.0
                if w > best_w:
                    best_w = w
                    best = l
            return best
        return self._outer.sub(replacer, xml)


class NotMemsetToXor(TransformRule):
    """NOT(MEMSET) → XOR — XOR is semantic inverse of zero-fill"""
    name = "not-memset-to-xor"
    priority = 5
    _pat = re.compile(r'<not>\s*<leaf op="MEMSET"([^>]*?)/>\s*</not>')

    def __init__(self):
        super().__init__(self.name, self.priority)

    def match(self, xml: str) -> bool:
        return bool(self._pat.search(xml))

    def apply(self, xml: str) -> str:
        return self._pat.sub(lambda m: f'<leaf op="XOR"{m.group(1)}/>', xml)


class AndMemcpyMemsetToMemcpy(TransformRule):
    """AND(MEMCPY, MEMSET) → MEMCPY — copy subsumes set"""
    name = "and-memcpy-memset-to-memcpy"
    priority = 5
    _outer = re.compile(r'<and>([\s\S]*?)</and>')
    _weight = re.compile(r'weight="([^"]+)"')

    def __init__(self):
        super().__init__(self.name, self.priority)

    def match(self, xml: str) -> bool:
        return bool(
            re.search(r'<and>[\s\S]*?<leaf op="MEMCPY"[\s\S]*?<leaf op="MEMSET"[\s\S]*?</and>', xml) or
            re.search(r'<and>[\s\S]*?<leaf op="MEMSET"[\s\S]*?<leaf op="MEMCPY"[\s\S]*?</and>', xml)
        )

    def apply(self, xml: str) -> str:
        def replacer(m):
            inner = m.group(1)
            has_copy = 'op="MEMCPY"' in inner
            has_set = 'op="MEMSET"' in inner
            if has_copy and has_set:
                wm = self._weight.search(inner)
                w = wm.group(1) if wm else '0.05'
                return f'<leaf op="MEMCPY" weight="{w}" valid="true"/>'
            return m.group(0)
        return self._outer.sub(replacer, xml)


DEFAULT_RULES = [
    DoubleNegationElimination(),
    IdempotentAnd(),
    IdempotentOr(),
    OrTautology(),
    AndShortCircuitFalse(),
    OrShortCircuitTrue(),
    WeightNormalizationAnd(),
    NotMemsetToXor(),
    AndMemcpyMemsetToMemcpy(),
]


class TransformEngine:
    def __init__(self, rules=None, max_passes: int = 10):
        self.rules = sorted(rules or DEFAULT_RULES, key=lambda r: -r.priority)
        self.max_passes = max_passes

    def transform(self, xml: str) -> dict:
        current = xml
        log = []
        for pass_n in range(self.max_passes):
            fired = False
            for rule in self.rules:
                if rule.match(current):
                    nxt = rule.apply(current)
                    if nxt != current:
                        log.append({'pass': pass_n, 'rule': rule.name})
                        current = nxt
                        fired = True
                        break
            if not fired:
                break
        return {'xml': current, 'log': log, 'passes': len(log)}

    def entropy_reduce(self, xml: str, depth_threshold: int = 3) -> dict:
        depth = self._measure_depth(xml)
        if depth <= depth_threshold:
            return {'xml': xml, 'reduced': False}
        leaves = re.findall(r'<leaf[^>]*/>', xml)
        if not leaves:
            return {'xml': xml, 'reduced': False}
        flat = '<route>\n  <or>\n    ' + '\n    '.join(leaves) + '\n  </or>\n</route>'
        return {'xml': flat, 'reduced': True, 'original_depth': depth}

    def _measure_depth(self, xml: str) -> int:
        depth = 0
        max_depth = 0
        i = 0
        while i < len(xml):
            if xml[i] != '<':
                i += 1
                continue
            if xml[i:i+2] == '</':
                depth -= 1
                end = xml.find('>', i)
                i = end + 1 if end != -1 else i + 1
            elif xml[i:i+4] in ('<!--', '<?'):
                end = xml.find('>', i)
                i = end + 1 if end != -1 else i + 1
            else:
                end = xml.find('>', i)
                if end == -1:
                    i += 1
                    continue
                tag_content = xml[i:end]
                if not tag_content.rstrip().endswith('/'):
                    depth += 1
                    max_depth = max(max_depth, depth)
                i = end + 1
        return max_depth
