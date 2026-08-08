"""
xml_router.py
Sovereign NL-to-AST Routing Bridge.
Direct port of xml_router.mjs — same flow, same entropy budget, same XXE hardening.
"""

import re
from typing import Optional
from webllm.ast_parser import parse_routing_ast, VALID_OPS

INFERENCE_WEIGHT_CAP = 0.05
ENTROPY_CAP = 0.20
MAX_NEW_TOKENS = 30
TEMPERATURE = 0.1


# ── Mock LLM (swap for a real model call in production) ─────────────────────

class MockWebLLM:
    """
    Pattern-based NL→XML generator.
    Recognises 'and', 'or', 'but not' connectives.
    Produces a <route> XML string — no external API.
    """

    _OP_KEYWORDS = {
        'MUL':    ['mul', 'multiply', 'times'],
        'XOR':    ['xor', 'toggle', 'flip'],
        'LOOP':   ['loop', 'repeat', 'count'],
        'MEMCPY': ['copy', 'memcpy'],
        'MEMSET': ['set', 'fill', 'zero'],
        'STRCMP': ['compare', 'strcmp', 'equal'],
        'HELLO':  ['hello', 'print', 'output'],
        'ADD':    ['add', 'sum', 'plus'],
    }

    def _pick_op(self, text: str) -> str:
        t = text.lower()
        for op, keywords in self._OP_KEYWORDS.items():
            if any(k in t for k in keywords):
                return op
        return 'ADD'

    def generate(self, prompt: str) -> str:
        q = prompt.lower()

        has_but_not = 'but not' in q or (' not ' in q and ' and ' in q)
        has_or = ' or ' in q
        has_and = ' and ' in q and not has_or and not has_but_not

        primary = self._pick_op(q)

        if has_but_not:
            sep = 'but not' if 'but not' in q else 'and not'
            parts = q.split(sep, 1)
            op1 = self._pick_op(parts[0])
            op2 = self._pick_op(parts[1] if len(parts) > 1 else 'xor')
            return (
                f'<route>\n'
                f'  <and>\n'
                f'    <leaf op="{op1}" weight="0.05" valid="true"/>\n'
                f'    <not>\n'
                f'      <leaf op="{op2}" weight="0.02" valid="true"/>\n'
                f'    </not>\n'
                f'  </and>\n'
                f'</route>'
            )

        if has_or:
            parts = q.split(' or ', 1)
            op1 = self._pick_op(parts[0])
            op2 = self._pick_op(parts[1] if len(parts) > 1 else '')
            return (
                f'<route>\n'
                f'  <or>\n'
                f'    <leaf op="{op1}" weight="0.05" valid="true"/>\n'
                f'    <leaf op="{op2}" weight="0.03" valid="true"/>\n'
                f'  </or>\n'
                f'</route>'
            )

        if has_and:
            parts = q.split(' and ', 1)
            op1 = self._pick_op(parts[0])
            op2 = self._pick_op(parts[1] if len(parts) > 1 else '')
            return (
                f'<route>\n'
                f'  <and>\n'
                f'    <leaf op="{op1}" weight="0.05" valid="true"/>\n'
                f'    <leaf op="{op2}" weight="0.03" valid="true"/>\n'
                f'  </and>\n'
                f'</route>'
            )

        return f'<route>\n  <leaf op="{primary}" weight="0.05" valid="true"/>\n</route>'


# ── XXE hardening ────────────────────────────────────────────────────────────

def validate_xxe_output(raw: str) -> str:
    """Reject any LLM output containing XXE vectors."""
    if not isinstance(raw, str):
        raise ValueError('LLM output must be a string')
    if re.search(r'<!DOCTYPE', raw, re.IGNORECASE):
        raise ValueError('XXE: DOCTYPE forbidden in LLM output')
    if re.search(r'<!ENTITY', raw, re.IGNORECASE):
        raise ValueError('XXE: ENTITY declaration forbidden')
    if re.search(r'&[a-zA-Z][a-zA-Z0-9]*;', raw):
        raise ValueError('XXE: entity reference forbidden in LLM output')
    if re.search(r'SYSTEM\s+["\']', raw, re.IGNORECASE):
        raise ValueError('XXE: SYSTEM identifier forbidden')
    return raw


def safe_stream_extract(xml: str) -> Optional[str]:
    """Extract the first complete <route>...</route> block."""
    wrapped = '<root>' + xml + '</root>'
    start = wrapped.find('<route')
    if start == -1:
        return None
    char_after = wrapped[start + 6] if start + 6 < len(wrapped) else None
    if char_after not in ('>', ' ', '\t', '\n', '/', None):
        return None
    end = wrapped.find('</route>', start)
    if end == -1:
        return None
    return wrapped[start:end + len('</route>')]


def parse_routing_expression(route_xml: str) -> dict:
    return parse_routing_ast(route_xml)


# ── Inference scheduler ──────────────────────────────────────────────────────

class InferenceScheduler:
    def __init__(self):
        self.total_weight = 0.0

    def can_schedule(self, weight: float) -> bool:
        return (self.total_weight + weight) <= ENTROPY_CAP

    def schedule(self, weight: float) -> float:
        if not self.can_schedule(weight):
            raise RuntimeError(
                f'Entropy cap exceeded: {self.total_weight + weight:.3f} > {ENTROPY_CAP}'
            )
        self.total_weight += weight
        return weight

    def reset(self):
        self.total_weight = 0.0


# ── Main bridge ──────────────────────────────────────────────────────────────

class XMLRoutingBridge:
    """
    Route a natural-language query to a kernel op via XML AST.
    Input:  str — natural language query
    Output: dict — {op, weight, valid, ast_depth, node_count, total_entropy, raw_xxe}
    """

    def __init__(self, llm=None):
        self.llm = llm or MockWebLLM()
        self.scheduler = InferenceScheduler()

    def route(self, query: str) -> dict:
        self.scheduler.schedule(INFERENCE_WEIGHT_CAP)

        raw = self.llm.generate(query)

        # Trim at </route>
        closing = '</route>'
        idx = raw.find(closing)
        trimmed = raw[:idx + len(closing)] if idx != -1 else raw

        validate_xxe_output(trimmed)

        route_block = safe_stream_extract(trimmed)
        if route_block is None:
            return {
                'op': 'ADD', 'valid': False,
                'reason': 'no <route> block in LLM output',
                'raw_xxe': trimmed,
            }

        parsed = parse_routing_expression(route_block)
        return {
            **parsed,
            'total_entropy': self.scheduler.total_weight,
            'raw_xxe': route_block,
        }

    def reset_scheduler(self):
        self.scheduler.reset()
