import cmath
import math
import re
from .schema_constants import ENTROPY_CAP

class IntentGenerator:
    """
    Generates instructed regex templates from queries without an external LLM.
    Uses keyword extraction + entropy scoring to produce deterministic patterns.
    Enforces entropy cap of 0.20 per Ahmad's spec.
    """

    # Keyword -> op mapping (the 'instruction' layer)
    KEYWORD_MAP = {
        "ADD":    ["add", "plus", "sum", "increment", "increase", "append"],
        "MUL":    ["mul", "multiply", "times", "product", "scale", "factor"],
        "XOR":    ["xor", "toggle", "flip", "exclusive", "difference", "delta"],
        "LOOP":   ["loop", "repeat", "iterate", "cycle", "count", "for", "while"],
        "MEMCPY": ["copy", "clone", "duplicate", "transfer", "move", "memcpy"],
        "MEMSET": ["set", "fill", "zero", "initialize", "clear", "reset", "memset"],
        "STRCMP": ["compare", "match", "equal", "strcmp", "check", "verify", "diff"],
        "HELLO":  ["hello", "greet", "print", "output", "write", "display", "show"],
    }

    def generate(self, query: str) -> tuple[str, str, float]:
        """
        Generate (op, regex_pattern, confidence) from a query string.
        Applies entropy cap -- patterns with entropy > ENTROPY_CAP are simplified.
        Returns (op, pattern, confidence).
        """
        query_lower = query.lower()

        scores = {}
        for op, keywords in self.KEYWORD_MAP.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[op] = score

        if not scores:
            return ("ADD", r"(?i)\b\w+\b", 0.3)

        best_op = max(scores, key=scores.get)
        keywords = self.KEYWORD_MAP[best_op]

        # Build regex from matched keywords
        matched_kws = [kw for kw in keywords if kw in query_lower]
        pattern = r"(?i)\b(" + "|".join(re.escape(kw) for kw in matched_kws) + r")\b"

        # Compute pattern entropy and enforce cap
        entropy = self._pattern_entropy(pattern)
        if entropy > ENTROPY_CAP:
            # Simplify: use only the top keyword
            pattern = r"(?i)\b" + re.escape(matched_kws[0]) + r"\b"

        confidence = min(1.0, scores[best_op] / len(keywords) + 0.3)
        return (best_op, pattern, confidence)

    def _pattern_entropy(self, pattern: str) -> float:
        """Shannon entropy of the pattern character distribution, normalized to [0,1]."""
        if not pattern:
            return 0.0
        from collections import Counter
        counts = Counter(pattern)
        total = len(pattern)
        entropy = -sum((c/total) * math.log2(c/total) for c in counts.values())
        # Normalize by max possible entropy (log2 of unique chars)
        max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
        return entropy / max_entropy
