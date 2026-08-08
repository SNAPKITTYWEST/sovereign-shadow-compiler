from .pattern_library import PatternLibrary, PatternEntry

class WeightUpdater:
    """
    Online weight update loop.
    Applies: weight <- weight + alpha*(signal - baseline)
    """
    def __init__(self, library: PatternLibrary, alpha: float = 0.1, baseline: float = 0.5):
        self.library = library
        self.alpha = alpha
        self.baseline = baseline

    def update(self, op: str, pattern: str, signal: float) -> float:
        """Find the matching entry and apply update. Returns new weight."""
        for entry in self.library.get_op(op):
            if entry.pattern == pattern:
                self.library.update_weight(entry, signal, self.alpha, self.baseline)
                return entry.weight
        return 0.0

    def reward(self, op: str, pattern: str) -> float:
        """Signal=1.0 (correct routing)"""
        return self.update(op, pattern, signal=1.0)

    def penalize(self, op: str, pattern: str) -> float:
        """Signal=0.0 (wrong routing)"""
        return self.update(op, pattern, signal=0.0)
