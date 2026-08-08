"""
SovereignVM — Register-based virtual machine for the Sovereign Shadow Compiler.

Registers: RAX RBX RCX RDX RSI RDI RSP RBP (all int, initialised to 0)
Memory:    64 KiB bytearray
KERNEL_MAP: verified hex blobs for ADD / MUL / XOR / LOOP primitives
"""

import math

KERNEL_MAP: dict[str, str] = {
    "ADD":  "48 89 f8 48 01 f0 c3",
    "MUL":  "48 89 f8 48 0f af c6 c3",
    "XOR":  "48 89 f8 48 31 f0 c3",
    "LOOP": "48 31 c0 48 ff c0 48 39 f8 7c f8 c3",
}

REGISTER_NAMES = ("RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RSP", "RBP")


class SovereignVM:
    """Simple register-based VM executing a list of instruction dicts."""

    def __init__(self) -> None:
        self.registers: dict[str, int] = {r: 0 for r in REGISTER_NAMES}
        self.memory: bytearray = bytearray(65536)
        self.ip: int = 0
        self._output_buf: list[str] = []
        self._halted: bool = False

    # ------------------------------------------------------------------
    # Kernel helpers
    # ------------------------------------------------------------------

    def load_kernel(self, op: str) -> bytes:
        """Return raw bytes for *op* from KERNEL_MAP (op is upper-cased)."""
        hex_str = KERNEL_MAP.get(op.upper(), "")
        if not hex_str:
            return b""
        return bytes(int(b, 16) for b in hex_str.split())

    def verify_kernel(self, op: str) -> bool:
        """Return True when *op* has non-empty bytes of valid (>0) length."""
        raw = self.load_kernel(op)
        return len(raw) > 0

    # ------------------------------------------------------------------
    # Individual opcode handlers
    # ------------------------------------------------------------------

    def _mov(self, reg: str, imm: int) -> None:
        reg = reg.upper()
        if reg not in self.registers:
            raise ValueError(f"Unknown register: {reg}")
        self.registers[reg] = imm

    def _add(self, reg_a: str, reg_b: str) -> None:
        a = self.registers[reg_a.upper()]
        b = self.registers[reg_b.upper()]
        self.registers["RAX"] = a + b

    def _mul(self, reg_a: str, reg_b: str) -> None:
        a = self.registers[reg_a.upper()]
        b = self.registers[reg_b.upper()]
        self.registers["RAX"] = a * b

    def _xor(self, reg_a: str, reg_b: str) -> None:
        a = self.registers[reg_a.upper()]
        b = self.registers[reg_b.upper()]
        self.registers["RAX"] = a ^ b

    def _loop(self, count: int) -> int:
        """Iterate *count* times, return final counter value."""
        counter = 0
        for _ in range(count):
            counter += 1
        self.registers["RCX"] = counter
        return counter

    def _syscall(self, op: str) -> None:
        op = op.lower()
        if op == "write":
            addr = self.registers["RSI"]
            length = self.registers["RDX"]
            raw = self.memory[addr : addr + length]
            text = raw.decode("utf-8", errors="replace")
            self._output_buf.append(text)
        elif op == "exit":
            self._halted = True
        else:
            raise ValueError(f"Unknown syscall op: {op!r}")

    # ------------------------------------------------------------------
    # Main execution loop
    # ------------------------------------------------------------------

    def run(self, program: list) -> dict:
        """
        Execute a list of instruction dicts.

        Each dict must have an "op" key plus opcode-specific keys:
          {"op": "MOV", "reg": "RDI", "imm": 42}
          {"op": "ADD", "reg_a": "RAX", "reg_b": "RBX"}
          {"op": "MUL", "reg_a": "RAX", "reg_b": "RBX"}
          {"op": "XOR", "reg_a": "RAX", "reg_b": "RBX"}
          {"op": "LOOP", "count": 5}
          {"op": "SYSCALL", "syscall_op": "write"}
          {"op": "HALT"}

        Returns {"registers": {...}, "output": str, "cycles": int}.
        """
        self._output_buf = []
        self._halted = False
        cycles = 0

        for instr in program:
            if self._halted:
                break
            op = instr["op"].upper()
            cycles += 1
            self.ip = cycles

            if op == "MOV":
                self._mov(instr["reg"], instr["imm"])

            elif op == "ADD":
                self._add(instr.get("reg_a", "RAX"), instr.get("reg_b", "RBX"))

            elif op == "MUL":
                self._mul(instr.get("reg_a", "RAX"), instr.get("reg_b", "RBX"))

            elif op == "XOR":
                self._xor(instr.get("reg_a", "RAX"), instr.get("reg_b", "RBX"))

            elif op == "LOOP":
                self._loop(int(instr.get("count", 1)))

            elif op == "SYSCALL":
                self._syscall(instr.get("syscall_op", "write"))

            elif op == "HALT":
                self._halted = True

            else:
                raise ValueError(f"Unknown opcode: {op!r}")

        return {
            "registers": dict(self.registers),
            "output": "".join(self._output_buf),
            "cycles": cycles,
        }
