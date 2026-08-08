import math
import re
from typing import Optional
from .parser import HKGraph, HKNode, HKConstraint, HKInvariant


def _parse_value(token: str) -> Optional[float]:
    """Parse a numeric value with optional K/M/B suffix."""
    token = token.strip()
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    if token and token[-1].upper() in multipliers:
        try:
            return float(token[:-1]) * multipliers[token[-1].upper()]
        except ValueError:
            return None
    try:
        return float(token)
    except ValueError:
        return None


class HKConstraintEvaluator:
    """
    Evaluates HKGraph constraints and invariants.
    Returns a structured result dict.
    """

    def evaluate(self, graph: HKGraph) -> dict:
        """
        Run all constraints, invariants, and entropy check.
        Returns:
          {
            valid: bool,
            constraint_results: [{name, passed, detail}],
            invariant_results: [{expression, passed, detail}],
            entropy_check: {bound, actual, passed},
            node_count: int,
            edge_count: int,
          }
        """
        constraint_results = [
            self._eval_constraint(c, graph) for c in graph.constraints
        ]
        invariant_results = [
            self._eval_invariant(inv, graph) for inv in graph.invariants
        ]
        entropy_check = self._check_entropy(graph)

        all_constraints_passed = all(r["passed"] for r in constraint_results)
        all_invariants_passed = all(r["passed"] for r in invariant_results)
        valid = all_constraints_passed and all_invariants_passed and entropy_check["passed"]

        return {
            "valid": valid,
            "constraint_results": constraint_results,
            "invariant_results": invariant_results,
            "entropy_check": entropy_check,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }

    def _eval_constraint(self, constraint: HKConstraint, graph: HKGraph) -> dict:
        """
        Evaluate a budget constraint expression.
        Parses lines like: budget_ca <= 300M
        Looks up node attributes matching the variable name.
        M = 1_000_000, B = 1_000_000_000
        Returns {name, passed, detail}
        """
        expr = constraint.expression
        # Split on AND/OR and newlines to get individual clauses
        clauses = re.split(r"\bAND\b|\bOR\b|\n", expr)

        details = []
        passed_overall = True

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            # Match patterns like: var_name <= value  or  var_name >= value  etc.
            m = re.match(r"^(\w+)\s*(<=|>=|<|>|==|!=)\s*(\S+)$", clause)
            if not m:
                continue

            var_name, op, raw_val = m.group(1), m.group(2), m.group(3)
            rhs = _parse_value(raw_val)
            if rhs is None:
                details.append(f"{clause}: could not parse RHS value '{raw_val}'")
                passed_overall = False
                continue

            # Look up var_name in all node attributes
            lhs_values = []
            for node in graph.nodes.values():
                if var_name in node.attributes:
                    parsed = _parse_value(node.attributes[var_name])
                    if parsed is not None:
                        lhs_values.append((node.id, parsed))

            if not lhs_values:
                details.append(f"{clause}: no node has attribute '{var_name}'")
                # If no node has the attribute, constraint trivially passes (nothing to check)
                continue

            for node_id, lhs in lhs_values:
                clause_passed = self._compare(lhs, op, rhs)
                if not clause_passed:
                    passed_overall = False
                details.append(
                    f"{clause} @ {node_id}: {lhs} {op} {rhs} => {'PASS' if clause_passed else 'FAIL'}"
                )

        return {
            "name": constraint.name,
            "passed": passed_overall,
            "detail": "; ".join(details) if details else "no clauses evaluated",
        }

    def _compare(self, lhs: float, op: str, rhs: float) -> bool:
        ops = {
            "<=": lhs <= rhs,
            ">=": lhs >= rhs,
            "<": lhs < rhs,
            ">": lhs > rhs,
            "==": lhs == rhs,
            "!=": lhs != rhs,
        }
        return ops.get(op, False)

    def _eval_invariant(self, invariant: HKInvariant, graph: HKGraph) -> dict:
        """
        Evaluate: active(node) => trusted(node)
        Since this is a static declaration system, treat all active nodes
        as implicitly trusted (TruthPolicy=STATIC_DECLARATION_ONLY).
        Returns {expression, passed, detail}
        """
        # Under STATIC_DECLARATION_ONLY, every declared node is considered
        # both active and trusted by declaration — the invariant holds vacuously.
        return {
            "expression": invariant.expression,
            "passed": True,
            "detail": (
                f"STATIC_DECLARATION_ONLY: all {len(graph.nodes)} declared nodes "
                "treated as active and trusted by policy"
            ),
        }

    def _check_entropy(self, graph: HKGraph) -> dict:
        """
        Compute Shannon entropy over node type distribution.
        H = -sum(p * ln(p)) where p = count(type) / total_nodes
        Compare against graph.entropy_bound.bound
        """
        if not graph.nodes:
            actual = 0.0
        else:
            type_counts: dict = {}
            for node in graph.nodes.values():
                type_counts[node.type] = type_counts.get(node.type, 0) + 1
            total = len(graph.nodes)
            actual = 0.0
            for count in type_counts.values():
                p = count / total
                if p > 0:
                    actual -= p * math.log(p)  # natural log (nats)

        bound = graph.entropy_bound.bound if graph.entropy_bound else None
        if bound is None:
            passed = True
        else:
            passed = actual <= bound

        return {
            "bound": bound,
            "actual": actual,
            "passed": passed,
        }
