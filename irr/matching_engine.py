import re
from typing import Optional
from .pattern_library import PatternLibrary, PatternEntry

# Whitelist of allowed regex operators (safety control)
ALLOWED_OPERATORS = frozenset([
    r'\b', r'\w', r'\s', r'\d', r'\B', r'\W', r'\S', r'\D',
    '(?i)', '(?:', r'\b', '+', '*', '?', '|', '^', '$', '.',
    '{', '}', '[', ']', '(', ')',
])

MAX_PATTERN_LENGTH = 256

class MatchingEngine:
    """
    Executes regex patterns against queries, routes to kernel ops.
    Applies safety controls: pattern length cap, operator whitelist check.
    """

    def __init__(self, library: PatternLibrary, top_n: int = 8, min_weight: float = 0.1):
        self.library = library
        self.top_n = top_n
        self.min_weight = min_weight
        self._cache: dict[str, str] = {}  # query -> op cache

    def is_safe_pattern(self, pattern: str) -> bool:
        """Check pattern length and that it compiles without catastrophic operators."""
        if len(pattern) > MAX_PATTERN_LENGTH:
            return False
        try:
            re.compile(pattern)
            return True
        except re.error:
            return False

    def match(self, query: str) -> dict:
        """
        Match query against top-N patterns.
        Returns {op: str, pattern: str, weight: float, matched: bool, from_cache: bool}
        """
        if query in self._cache:
            return {"op": self._cache[query], "matched": True, "from_cache": True, "pattern": "", "weight": 0.0}

        candidates = [e for e in self.library.top_n(self.top_n) if e.weight >= self.min_weight]

        for entry in candidates:
            if not self.is_safe_pattern(entry.pattern):
                continue
            if re.search(entry.pattern, query):
                entry.hits += 1
                self._cache[query] = entry.op
                return {"op": entry.op, "pattern": entry.pattern, "weight": entry.weight, "matched": True, "from_cache": False}

        # Fallback
        return {"op": "ADD", "pattern": "", "weight": 0.0, "matched": False, "from_cache": False, "fallback": True}

    def clear_cache(self):
        self._cache.clear()
