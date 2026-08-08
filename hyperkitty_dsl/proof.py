import hashlib
import json
from .parser import HKGraph


class HKProofGenerator:
    """
    Generates the ProofOutput block for a HKGraph.
    Produces: ConstraintGraph hash, RuleHash, TransformHash, ValidationResult hash.
    All SHA-256.
    """

    def generate(self, graph: HKGraph, eval_result: dict) -> dict:
        """
        Returns {
          ConstraintGraph: hex_hash,
          RuleHash: hex_hash,
          TransformHash: hex_hash,
          ValidationResult: hex_hash,
          proof_complete: bool,
        }
        """
        constraint_graph = {
            "nodes": [n.id for n in graph.nodes.values()],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in graph.edges],
            "constraints": [c.name for c in graph.constraints],
        }
        rules = [c.expression for c in graph.constraints] + [
            i.expression for i in graph.invariants
        ]
        transforms = [
            {"entropy_bound": graph.entropy_bound.bound if graph.entropy_bound else None}
        ]

        cg_hash = hashlib.sha256(
            json.dumps(constraint_graph, sort_keys=True).encode()
        ).hexdigest()
        rule_hash = hashlib.sha256(
            json.dumps(rules, sort_keys=True).encode()
        ).hexdigest()
        transform_hash = hashlib.sha256(
            json.dumps(transforms).encode()
        ).hexdigest()
        validation_hash = hashlib.sha256(
            json.dumps(eval_result, sort_keys=True, default=str).encode()
        ).hexdigest()

        proof_complete = all(
            f in graph.proof_required
            for f in ["ConstraintGraph", "RuleHash", "TransformHash", "ValidationResult"]
        )

        return {
            "ConstraintGraph": cg_hash,
            "RuleHash": rule_hash,
            "TransformHash": transform_hash,
            "ValidationResult": validation_hash,
            "proof_complete": proof_complete,
        }
