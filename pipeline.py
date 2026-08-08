#!/usr/bin/env python3
"""
Sovereign Compiler Pipeline
Wires: SovereignEntropyEngine → ConstraintPass → MachineCodeSelector → SovereignVM
"""
from engine import SovereignEntropyEngine
from codegen import ConstraintPass, MachineCodeSelector
from vm.sovereign_vm import SovereignVM


def run_pipeline(input_strings: list) -> dict:
    engine = SovereignEntropyEngine(input_strings)
    entropy = engine.calculate_entropy_vector()
    raw_code = engine.compile_to_machine_intent()

    constraint = ConstraintPass()
    result = constraint.validate(entropy)

    selector = MachineCodeSelector()
    op = selector.select(entropy, result)
    kernel_bytes = selector.emit(op)

    vm = SovereignVM()
    program = [
        {"op": "MOV", "reg": "RDI", "imm": len(input_strings)},
        {"op": "LOOP", "count": len(input_strings)},
        {"op": "HALT"},
    ]
    vm_result = vm.run(program)

    return {
        "entropy": str(entropy),
        "constraint": result,
        "selected_op": op,
        "kernel_bytes_hex": kernel_bytes.hex(),
        "raw_intent_hex": raw_code.hex(),
        "vm": vm_result,
    }


if __name__ == "__main__":
    import json
    out = run_pipeline(["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"])
    print(json.dumps(out, indent=2))
