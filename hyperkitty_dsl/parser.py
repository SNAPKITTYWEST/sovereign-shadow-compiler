from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from xml.etree import ElementTree as ET
import re


@dataclass
class HKMeta:
    system: str
    mode: str
    output: str
    truth_policy: str


@dataclass
class HKGlyphUnit:
    symbol: str
    name: str


@dataclass
class HKNode:
    id: str
    type: str
    label: str
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class HKEdge:
    from_node: str
    to_node: str


@dataclass
class HKConstraint:
    name: str
    expression: str  # raw text of the constraint body


@dataclass
class HKInvariant:
    expression: str


@dataclass
class HKEntropyBound:
    metric: str
    formula: str
    bound: float  # parsed from "H <= 0.20"


@dataclass
class HKGraph:
    meta: HKMeta
    glyphs: Dict[str, HKGlyphUnit]   # keyed by symbol
    nodes: Dict[str, HKNode]          # keyed by id
    edges: List[HKEdge]
    constraints: List[HKConstraint]
    invariants: List[HKInvariant]
    entropy_bound: Optional[HKEntropyBound]
    proof_required: List[str]         # list of required proof fields


class HKDSLParser:
    def parse(self, xml_str: str) -> HKGraph:
        """Parse HyperKittyConstraintDSL XML into HKGraph."""
        root = ET.fromstring(xml_str)

        # Parse Meta
        meta_el = root.find("Meta")
        meta = HKMeta(
            system=meta_el.findtext("System", ""),
            mode=meta_el.findtext("Mode", ""),
            output=meta_el.findtext("Output", ""),
            truth_policy=meta_el.findtext("TruthPolicy", ""),
        )

        # Parse GlyphTypeSystem
        glyphs: Dict[str, HKGlyphUnit] = {}
        glyph_el = root.find("GlyphTypeSystem")
        if glyph_el is not None:
            for unit in glyph_el.findall("Unit"):
                symbol = unit.get("symbol", "")
                name = unit.get("name", "")
                glyphs[symbol] = HKGlyphUnit(symbol=symbol, name=name)

        # Parse all Node elements
        nodes: Dict[str, HKNode] = {}
        for node_el in root.findall("Node"):
            node_id = node_el.get("id", "")
            node_type = node_el.get("type", "")
            node_label = node_el.get("label", "")
            # Collect all attributes except id, type, label
            attrs = {
                k: v
                for k, v in node_el.attrib.items()
                if k not in ("id", "type", "label")
            }
            nodes[node_id] = HKNode(
                id=node_id,
                type=node_type,
                label=node_label,
                attributes=attrs,
            )

        # Parse all Edge elements
        edges: List[HKEdge] = []
        for edge_el in root.findall("Edge"):
            edges.append(
                HKEdge(
                    from_node=edge_el.get("from", ""),
                    to_node=edge_el.get("to", ""),
                )
            )

        # Parse all Constraint elements
        constraints: List[HKConstraint] = []
        for c_el in root.findall("Constraint"):
            name = c_el.get("name", "")
            expr = (c_el.text or "").strip()
            constraints.append(HKConstraint(name=name, expression=expr))

        # Parse all Invariant elements
        invariants: List[HKInvariant] = []
        for inv_el in root.findall("Invariant"):
            expr = (inv_el.text or "").strip()
            invariants.append(HKInvariant(expression=expr))

        # Parse QuantumConstraintLayer/Entropy
        entropy_bound: Optional[HKEntropyBound] = None
        qcl = root.find("QuantumConstraintLayer")
        if qcl is not None:
            ent = qcl.find("Entropy")
            if ent is not None:
                metric = ent.findtext("Metric", "")
                formula = ent.findtext("Formula", "")
                bound_text = (ent.findtext("Bound") or "").strip()
                # Parse "H <= 0.20" → 0.20
                bound_val = 0.0
                m = re.search(r"<=\s*([\d.]+)", bound_text)
                if m:
                    bound_val = float(m.group(1))
                entropy_bound = HKEntropyBound(
                    metric=metric,
                    formula=formula,
                    bound=bound_val,
                )

        # Parse ProofOutput/Required
        proof_required: List[str] = []
        po_el = root.find("ProofOutput")
        if po_el is not None:
            req_text = (po_el.findtext("Required") or "").strip()
            proof_required = req_text.split() if req_text else []

        return HKGraph(
            meta=meta,
            glyphs=glyphs,
            nodes=nodes,
            edges=edges,
            constraints=constraints,
            invariants=invariants,
            entropy_bound=entropy_bound,
            proof_required=proof_required,
        )
