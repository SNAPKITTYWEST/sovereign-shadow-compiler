"""
ConstraintPass — Validates the complex state vector produced by the
SovereignEntropyEngine before it reaches the MachineCodeSelector.

Checks:
  - magnitude > 0
  - no NaN / Inf in real or imaginary parts
  - maps the magnitude to a known kernel op (force_op) when the
    quantised index lands exactly on one of the sorted KERNEL_MAP keys
"""

import cmath
import math

try:
    from kernels.kernel_map import KERNEL_MAP
except ImportError:
    from vm.sovereign_vm import KERNEL_MAP

_SORTED_OPS: list[str] = sorted(KERNEL_MAP.keys())


class ConstraintPass:
    """Validate a complex state vector and produce a constraint result dict."""

    def validate(self, state_vector: complex) -> dict:
        """
        Validate *state_vector*.

        Returns
        -------
        dict with keys:
          valid      : bool   — True iff magnitude > 0 and finite
          magnitude  : float  — abs(state_vector)
          phase      : float  — phase angle in radians  (-π … +π)
          warnings   : list[str]
          force_op   : str | None — kernel op name if magnitude maps cleanly,
                                    else None
        """
        warnings: list[str] = []

        real = state_vector.real
        imag = state_vector.imag

        # NaN / Inf guards
        if math.isnan(real) or math.isnan(imag):
            return {
                "valid": False,
                "magnitude": float("nan"),
                "phase": float("nan"),
                "warnings": ["state_vector contains NaN"],
                "force_op": None,
            }

        if math.isinf(real) or math.isinf(imag):
            return {
                "valid": False,
                "magnitude": float("inf"),
                "phase": float("inf"),
                "warnings": ["state_vector contains Inf"],
                "force_op": None,
            }

        magnitude: float = abs(state_vector)
        phase: float = cmath.phase(state_vector)

        if magnitude == 0.0:
            warnings.append("zero magnitude — no entropy signal")
            return {
                "valid": False,
                "magnitude": magnitude,
                "phase": phase,
                "warnings": warnings,
                "force_op": None,
            }

        # Magnitude is valid — attempt to derive a force_op
        force_op: str | None = None
        n = len(_SORTED_OPS)
        if n > 0:
            # Quantise: map magnitude into [0, n) by taking floor(magnitude) mod n
            idx = int(math.floor(magnitude)) % n
            candidate = _SORTED_OPS[idx]
            # Only set force_op when magnitude lands within 0.1 of an integer
            if abs(magnitude - round(magnitude)) < 0.1:
                force_op = candidate
            else:
                warnings.append(
                    f"magnitude {magnitude:.4f} is between kernel boundaries; "
                    f"selector will interpolate"
                )

        return {
            "valid": True,
            "magnitude": magnitude,
            "phase": phase,
            "warnings": warnings,
            "force_op": force_op,
        }
