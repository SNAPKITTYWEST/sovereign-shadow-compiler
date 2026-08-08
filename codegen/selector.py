"""
MachineCodeSelector — maps a complex entropy state + constraint result
to a concrete x86-64 kernel op, then emits its raw bytes.

Selection algorithm
-------------------
1. If constraints['force_op'] is set, use it directly (constraint override).
2. Otherwise use the real part magnitude to index into sorted KERNEL_MAP keys:
       idx = int(floor(abs(real(entropy)))) % len(keys)
3. Emit the raw bytes for the chosen op via KERNEL_MAP.
"""

import math

try:
    from kernels.kernel_map import KERNEL_MAP
except ImportError:
    from vm.sovereign_vm import KERNEL_MAP

_SORTED_OPS: list[str] = sorted(KERNEL_MAP.keys())


class MachineCodeSelector:
    """Select an x86-64 kernel op from the entropy state and emit its bytes."""

    def select(self, entropy: complex, constraints: dict) -> str:
        """
        Return the op name (e.g. "ADD") for the given *entropy* state.

        Parameters
        ----------
        entropy     : complex state vector from SovereignEntropyEngine
        constraints : result dict from ConstraintPass.validate()

        Returns
        -------
        str — one of the KERNEL_MAP keys
        """
        # Constraint override takes priority
        force = constraints.get("force_op")
        if force and force in KERNEL_MAP:
            return force

        # Fallback: use magnitude of real part
        real_mag = abs(entropy.real)
        if math.isnan(real_mag) or math.isinf(real_mag) or not _SORTED_OPS:
            return _SORTED_OPS[0] if _SORTED_OPS else "ADD"

        idx = int(math.floor(real_mag)) % len(_SORTED_OPS)
        return _SORTED_OPS[idx]

    def emit(self, op: str) -> bytes:
        """
        Return the raw machine-code bytes for *op*.

        Raises ValueError for unknown ops.
        """
        op = op.upper()
        hex_str = KERNEL_MAP.get(op)
        if not hex_str:
            raise ValueError(
                f"Unknown kernel op: {op!r}. "
                f"Valid ops: {sorted(KERNEL_MAP.keys())}"
            )
        return bytes(int(b, 16) for b in hex_str.split())
