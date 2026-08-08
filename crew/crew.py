from typing import List, Optional, Dict, Any
from .agent import SovereignAgent


class SovereignCrew:
    """
    Sovereign drop-in for CrewAI Crew.
    Chains agents sequentially or hierarchically with context inheritance.
    No external API. Pure sovereign pipeline.
    """

    def __init__(
        self,
        agents: List[SovereignAgent],
        tasks: List[Any],
        verbose: bool = True,
        process: str = "sequential",
    ):
        self.agents = agents
        self.tasks = tasks
        self.verbose = verbose
        self.process = process

    def kickoff(self, inputs: Optional[Dict[str, Any]] = None) -> dict:
        if self.verbose:
            print(f"\n=== SovereignCrew kickoff [{self.process}] ===")

        results = []
        context_output = str(inputs) if inputs else None

        if self.process == "sequential":
            for i, task in enumerate(self.tasks):
                agent = self.agents[i % len(self.agents)]
                if self.verbose:
                    print(f"  Task {i+1}/{len(self.tasks)} -> {agent.role}")
                result = agent.execute_task(str(task), context=context_output)
                context_output = result["output"]
                results.append(result)

        elif self.process == "hierarchical":
            # Manager agent (index 0) plans, sub-agents execute
            manager = self.agents[0]
            sub_agents = self.agents[1:] or [manager]
            for i, task in enumerate(self.tasks):
                # Manager evaluates task first
                mgr_result = manager.execute_task(f"PLAN:{str(task)}", context=context_output)
                context_output = mgr_result["output"]
                # Sub-agent executes with manager context
                worker = sub_agents[i % len(sub_agents)]
                result = worker.execute_task(str(task), context=context_output)
                context_output = result["output"]
                results.append({"manager": mgr_result, "worker": result})

        return {
            "process": self.process,
            "steps": len(results),
            "results": results,
            "final_output": context_output,
        }
