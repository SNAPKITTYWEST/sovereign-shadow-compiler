import cmath
import math
import struct
import sys
import os
from typing import Dict, List, Optional

# Support both package import and direct `python engine/entropy_engine.py` execution
try:
    from .shadow_node import ShadowNode
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shadow_node import ShadowNode


class SovereignEntropyEngine:
    """
    Entropy-driven sparse activation compiler.

    Converts a sequence of symbolic tokens into a machine-intent byte sequence
    by routing each token through a sparse shadow-state activation tree and
    computing a normalized entropy vector over the activated nodes.
    """

    def __init__(self, kernel_map: Dict[str, str]):
        self.kernel_map = kernel_map
        self.root = ShadowNode("ROOT", complex(1.0, 0.0))
        self._build_sparse_tree(list(kernel_map.keys()))

    def _build_sparse_tree(self, ops: List[str]) -> None:
        """
        Seed the shadow tree with one path per kernel op.
        Each character of the op name becomes a node in the path;
        the initial shadow value is derived from the op's position index.
        """
        for idx, op in enumerate(ops):
            phase = cmath.exp(complex(0, 2 * math.pi * idx / len(ops)))
            path = list(op)
            self.root.insert(path, phase)

    def calculate_entropy_vector(self, tokens: List[str]) -> List[complex]:
        """
        Walk the shadow tree for each token and accumulate complex activation
        weights. Returns one complex value per token representing its entropy
        projection in the activation space.
        """
        result: List[complex] = []
        for token in tokens:
            node = self.root
            accumulated = complex(1.0, 0.0)
            for char in token:
                if char in node.children:
                    child = node.children[char]
                    if child.activated:
                        accumulated *= child.shadow_val
                    node = child
                else:
                    accumulated *= complex(0.5, 0.5)
                    break
            magnitude = abs(accumulated)
            if magnitude > 0:
                accumulated = accumulated / magnitude
            result.append(accumulated)
        return result

    def compile_to_machine_intent(self, tokens: List[str]) -> bytes:
        """
        Map each token to its kernel byte sequence via the kernel_map.
        Tokens not present in the map are dropped silently.
        Returns the concatenated byte sequence for all matched tokens.
        """
        entropy_vec = self.calculate_entropy_vector(tokens)
        output = bytearray()
        for token, ev in zip(tokens, entropy_vec):
            op = token.upper()
            if op in self.kernel_map:
                hex_str = self.kernel_map[op]
                byte_seq = bytes(int(b, 16) for b in hex_str.split())
                # Pack the real part of the entropy value as a 4-byte float
                # header (little-endian) prepended to each kernel block so the
                # VM layer can weight execution priority at runtime.
                header = struct.pack("<f", ev.real)
                output.extend(header)
                output.extend(byte_seq)
        return bytes(output)


if __name__ == "__main__":
    # Allow running as a standalone script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from kernels.kernel_map import KERNEL_MAP

    tokens = ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"]

    engine = SovereignEntropyEngine(KERNEL_MAP)

    entropy_vec = engine.calculate_entropy_vector(tokens)
    print("=== Entropy State ===")
    for token, ev in zip(tokens, entropy_vec):
        print(f"  {token:10s}  re={ev.real:+.6f}  im={ev.imag:+.6f}  |z|={abs(ev):.6f}")

    result = engine.compile_to_machine_intent(tokens)
    print("\n=== Machine Intent (hex) ===")
    hex_out = result.hex(" ")
    print(f"  {hex_out}")
    print(f"\n=== Instruction Length ===")
    print(f"  {len(result)} bytes total")
