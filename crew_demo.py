#!/usr/bin/env python3
"""
Sovereign Crew Demo
Shows the full stack: CrewAI-style interface → sovereign entropy engine → VM
No external API. No tokens. Pure sovereign.
"""
import json
from crew import SovereignAgent, AgentConfig, SovereignCrew


def main():
    researcher = SovereignAgent(AgentConfig(
        role="Senior Research Analyst",
        goal="Uncover cutting-edge data points",
        backstory="Expert at parsing technical ecosystems",
        verbose=True,
    ))

    writer = SovereignAgent(AgentConfig(
        role="Technical Writer",
        goal="Produce clear technical documentation",
        backstory="Specialist in distilling complex systems",
        verbose=True,
    ))

    auditor = SovereignAgent(AgentConfig(
        role="Sovereign Auditor",
        goal="Verify integrity and correctness of all outputs",
        backstory="Formal verification and constraint checking",
        verbose=True,
    ))

    tasks = [
        "Analyze the sovereign compiler architecture and identify key components",
        "Write a technical summary of the sparse activation tree mechanism",
        "Audit the entropy vector pipeline for constraint violations",
    ]

    # Sequential crew
    print("\n--- Sequential Process ---")
    crew = SovereignCrew(
        agents=[researcher, writer, auditor],
        tasks=tasks,
        verbose=True,
        process="sequential",
    )
    seq_result = crew.kickoff(inputs={"domain": "sovereign-compiler"})
    print(f"\nFinal output: {seq_result['final_output']}")
    print(f"Steps completed: {seq_result['steps']}")

    # Hierarchical crew
    print("\n--- Hierarchical Process ---")
    crew2 = SovereignCrew(
        agents=[auditor, researcher, writer],
        tasks=tasks[:2],
        verbose=True,
        process="hierarchical",
    )
    hier_result = crew2.kickoff(inputs={"domain": "sovereign-compiler"})
    print(f"\nFinal output: {hier_result['final_output']}")


if __name__ == "__main__":
    main()
