"""
engine package — exposes SovereignEntropyEngine with two call conventions:

  Legacy (kernel_map dict):
      eng = SovereignEntropyEngine(kernel_map)
      vec = eng.calculate_entropy_vector(tokens)
      raw = eng.compile_to_machine_intent(tokens)

  Pipeline adapter (input_strings list):
      eng = SovereignEntropyEngine(input_strings)   # list[str]
      vec = eng.calculate_entropy_vector()           # single complex
      raw = eng.compile_to_machine_intent()          # bytes

The pipeline adapter is auto-detected: if the first argument is a list,
the engine initialises with the full KERNEL_MAP and stores input_strings
for no-argument method calls.
"""

from __future__ import annotations

from typing import Union, List, Dict

from .shadow_node import ShadowNode
from .entropy_engine import SovereignEntropyEngine as _CoreEngine

try:
    from kernels.kernel_map import KERNEL_MAP as _KERNEL_MAP
except ImportError:
    # Fallback to the canonical four ops when running outside the package root
    _KERNEL_MAP = {
        "ADD":  "48 89 f8 48 01 f0 c3",
        "MUL":  "48 89 f8 48 0f af c6 c3",
        "XOR":  "48 89 f8 48 31 f0 c3",
        "LOOP": "48 31 c0 48 ff c0 48 39 f8 7c f8 c3",
    }


class SovereignEntropyEngine:
    """
    Unified adapter for SovereignEntropyEngine.

    Accepts either:
      - a dict (kernel_map)  → legacy mode; tokens passed per-call
      - a list (input_strings) → pipeline mode; tokens stored at init
    """

    def __init__(self, arg: Union[List[str], Dict[str, str]]) -> None:
        if isinstance(arg, dict):
            # Legacy mode
            self._kernel_map = arg
            self._tokens: List[str] = []
            self._pipeline_mode = False
        else:
            # Pipeline mode — arg is a list of input strings
            self._kernel_map = _KERNEL_MAP
            self._tokens = list(arg)
            self._pipeline_mode = True

        self._core = _CoreEngine(self._kernel_map)

    # ------------------------------------------------------------------
    # Pipeline-mode methods (no-argument)
    # ------------------------------------------------------------------

    def calculate_entropy_vector(self, tokens: List[str] | None = None) -> object:
        """
        Pipeline mode:  returns a single complex scalar (mean of per-token vectors).
        Legacy mode:    returns list[complex] exactly as _CoreEngine does.
        """
        toks = tokens if tokens is not None else self._tokens
        vec = self._core.calculate_entropy_vector(toks)

        if tokens is None and self._pipeline_mode:
            # Reduce to a single complex value for the pipeline
            if not vec:
                return complex(0.0, 0.0)
            return sum(vec) / len(vec)

        return vec

    def compile_to_machine_intent(self, tokens: List[str] | None = None) -> bytes:
        """
        Pipeline mode:  uses stored input_strings, returns bytes.
        Legacy mode:    delegates directly to _CoreEngine.
        """
        toks = tokens if tokens is not None else self._tokens
        return self._core.compile_to_machine_intent(toks)


__all__ = ["SovereignEntropyEngine", "ShadowNode"]
