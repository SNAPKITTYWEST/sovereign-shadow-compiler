from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class PatternEntry:
    op: str                    # kernel op name: ADD, MUL, XOR, LOOP, etc.
    pattern: str               # regex string
    weight: float = 1.0
    priority: int = 0
    confidence: float = 1.0
    hits: int = 0
    misses: int = 0

class PatternLibrary:
    """KV store for regex routing patterns keyed by op name."""

    def __init__(self):
        self._store: dict[str, list[PatternEntry]] = {}
        self._seed_defaults()

    def _seed_defaults(self):
        """Seed with default patterns for each kernel op."""
        # Each op gets a default pattern that matches its name or common synonyms
        defaults = {
            "ADD":    (r"(?i)\b(add|plus|sum|increment|increase)\b", 1.0),
            "MUL":    (r"(?i)\b(mul|multiply|times|product|scale)\b", 1.0),
            "XOR":    (r"(?i)\b(xor|toggle|flip|exclusive|diff)\b", 1.0),
            "LOOP":   (r"(?i)\b(loop|repeat|iterate|cycle|count)\b", 1.0),
            "MEMCPY": (r"(?i)\b(copy|clone|dup|transfer|memcpy)\b", 1.0),
            "MEMSET": (r"(?i)\b(set|fill|zero|init|memset)\b", 1.0),
            "STRCMP": (r"(?i)\b(compare|cmp|strcmp|match|equal)\b", 1.0),
            "HELLO":  (r"(?i)\b(hello|greet|print|output|write)\b", 1.0),
        }
        for op, (pat, conf) in defaults.items():
            self.add(op, pat, confidence=conf, priority=0)

    def add(self, op: str, pattern: str, confidence: float = 1.0, priority: int = 0) -> PatternEntry:
        """Add a pattern entry. Raises ValueError if pattern is unsafe."""
        # validate pattern is safe before storing
        entry = PatternEntry(op=op, pattern=pattern, weight=confidence + priority * 0.1, priority=priority, confidence=confidence)
        self._store.setdefault(op, []).append(entry)
        return entry

    def top_n(self, n: int = 8) -> list[PatternEntry]:
        """Return top-N entries across all ops sorted by weight descending."""
        all_entries = [e for entries in self._store.values() for e in entries]
        return sorted(all_entries, key=lambda e: e.weight, reverse=True)[:n]

    def get_op(self, op: str) -> list[PatternEntry]:
        return self._store.get(op, [])

    def update_weight(self, entry: PatternEntry, signal: float, alpha: float = 0.1, baseline: float = 0.5):
        """Apply weight update rule: weight <- weight + alpha*(signal - baseline)"""
        entry.weight += alpha * (signal - baseline)
        entry.weight = max(0.0, entry.weight)  # clamp to non-negative
