#!/usr/bin/env python3
from hyperkitty_dsl import HKDSLParser, HKConstraintEvaluator, HKProofGenerator
import json

SOVEREIGN_COMPUTE_GRAPH = """<HyperKittyConstraintDSL version="1.0">
  <Meta>
    <System>HK-OS</System>
    <Mode>DETERMINISTIC-CONSTRAINT-BUILD</Mode>
    <Output>PROOF_BACKED_ARTIFACT</Output>
    <TruthPolicy>STATIC_DECLARATION_ONLY</TruthPolicy>
  </Meta>
  <GlyphTypeSystem>
    <Unit symbol="CA" name="Country_CA"/>
    <Unit symbol="UK" name="Country_UK"/>
    <Unit symbol="US" name="Country_US"/>
    <Unit symbol="CN" name="Country_CN"/>
    <Unit symbol="FUND" name="Funding"/>
    <Unit symbol="COMP" name="Compute_Node"/>
    <Unit symbol="SEC" name="Security"/>
    <Unit symbol="MKT" name="Market"/>
  </GlyphTypeSystem>
  <Node id="CA_CANADA" type="Country_CA" label="Canada Sovereign AI" budget_ca="300000000"/>
  <Node id="UK_UK" type="Country_UK" label="UK Stargate" budget_uk="100000000000"/>
  <Node id="US_US" type="Country_US" label="US AWS Rainier" budget_us="500000000"/>
  <Node id="CN_CHINA" type="Country_CN" label="China State Compute" budget_cn="0"/>
  <Node id="FUND_CA" type="Funding" label="CA 300M SME Fund"/>
  <Node id="FUND_UK" type="Funding" label="UK AI Compute Grant"/>
  <Node id="COMP_CA" type="Compute_Node" label="CA Sovereign Supercomputer" capacity="5000000000"/>
  <Node id="COMP_UK" type="Compute_Node" label="UK Stargate Supercomputer"/>
  <Node id="COMP_US" type="Compute_Node" label="AWS Project Rainier"/>
  <Node id="SEC" type="Security" label="National Security Policy"/>
  <Node id="MKT" type="Market" label="Sovereign AI Market 2040" trend="rapid_growth"/>
  <Edge from="CA_CANADA" to="FUND_CA"/>
  <Edge from="UK_UK" to="FUND_UK"/>
  <Edge from="COMP_CA" to="SEC"/>
  <Edge from="COMP_UK" to="SEC"/>
  <Edge from="COMP_US" to="SEC"/>
  <Edge from="COMP_CA" to="MKT"/>
  <Edge from="COMP_UK" to="MKT"/>
  <Edge from="COMP_US" to="MKT"/>
  <Edge from="MKT" to="CA_CANADA"/>
  <Edge from="MKT" to="UK_UK"/>
  <Edge from="MKT" to="US_US"/>
  <Edge from="MKT" to="CN_CHINA"/>
  <Constraint name="budget_upper_bound">
    budget_ca &lt;= 300000000
    AND
    budget_uk &lt;= 100000000000
    AND
    budget_us &lt;= 500000000
  </Constraint>
  <Invariant>active(node) =&gt; trusted(node)</Invariant>
  <QuantumConstraintLayer>
    <Entropy>
      <Metric>Shannon_Nats</Metric>
      <Formula>H = - sum(p ln p)</Formula>
      <Bound>H &lt;= 0.20</Bound>
    </Entropy>
  </QuantumConstraintLayer>
  <ProofOutput>
    <Required>ConstraintGraph RuleHash TransformHash ValidationResult</Required>
  </ProofOutput>
</HyperKittyConstraintDSL>"""

if __name__ == "__main__":
    parser = HKDSLParser()
    graph = parser.parse(SOVEREIGN_COMPUTE_GRAPH)

    print(f"Parsed: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    print(f"Constraints: {[c.name for c in graph.constraints]}")
    print(f"Entropy bound: {graph.entropy_bound.bound if graph.entropy_bound else 'none'}")

    evaluator = HKConstraintEvaluator()
    result = evaluator.evaluate(graph)
    print(f"\nEvaluation: valid={result['valid']}")
    for cr in result['constraint_results']:
        print(f"  Constraint '{cr['name']}': passed={cr['passed']} — {cr['detail']}")
    print(f"  Entropy: actual={result['entropy_check']['actual']:.4f} bound={result['entropy_check']['bound']} passed={result['entropy_check']['passed']}")

    prover = HKProofGenerator()
    proof = prover.generate(graph, result)
    print(f"\nProof:")
    for k, v in proof.items():
        print(f"  {k}: {v}")
