from typing import List, Any, Optional
from pydantic import BaseModel, Field
from engine import SovereignEntropyEngine
from codegen import ConstraintPass, MachineCodeSelector
from vm.sovereign_vm import SovereignVM


class AgentConfig(BaseModel):
    role: str
    goal: str
    backstory: str
    verbose: bool = False
    memory: bool = True
    max_iter: int = 25
    tools: List[Any] = Field(default_factory=list)


class SovereignAgent:
    """
    Sovereign drop-in for CrewAI Agent.
    Routes through entropy engine + VM instead of external LLM API.
    """

    def __init__(self, config: AgentConfig):
        self.role = config.role
        self.goal = config.goal
        self.backstory = config.backstory
        self.verbose = config.verbose
        self.memory = config.memory
        self.max_iter = config.max_iter
        self.tools = config.tools
        self._engine = None
        self._vm = SovereignVM()

    def execute_task(self, task_description: str, context: Optional[str] = None) -> dict:
        """
        Builds 6-string input from agent identity + task + context,
        runs sovereign pipeline, returns structured result dict.
        """
        # Build the 6-string activation domain from agent identity + task
        # Pad or truncate context to always produce exactly 6 strings
        ctx_token = (context or "NULL")[:16].replace(" ", "_").upper()
        domain = [
            self.role.upper()[:16].replace(" ", "_"),
            self.goal.upper()[:16].replace(" ", "_"),
            self.backstory.upper()[:16].replace(" ", "_"),
            task_description.upper()[:16].replace(" ", "_"),
            ctx_token,
            "SOVEREIGN",
        ]

        engine = SovereignEntropyEngine(domain)
        entropy = engine.calculate_entropy_vector()
        raw_bytes = engine.compile_to_machine_intent()

        constraint = ConstraintPass()
        c_result = constraint.validate(entropy)

        selector = MachineCodeSelector()
        op = selector.select(entropy, c_result)
        kernel_bytes = selector.emit(op)

        program = [
            {"op": "MOV", "reg": "RDI", "imm": len(domain)},
            {"op": "LOOP", "count": len(domain)},
            {"op": "HALT"},
        ]
        vm_result = self._vm.run(program)

        result = {
            "agent": self.role,
            "task": task_description,
            "entropy": str(entropy),
            "op": op,
            "kernel_hex": kernel_bytes.hex(),
            "constraint": c_result,
            "vm": vm_result,
            "output": f"[{self.role}] op={op} entropy={entropy:.4f} cycles={vm_result['cycles']}",
        }

        if self.verbose:
            print(f"  [{self.role}] entropy={entropy:.4f} op={op} kernel={kernel_bytes.hex()}")

        return result
