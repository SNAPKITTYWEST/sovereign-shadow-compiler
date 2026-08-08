import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom


@dataclass
class PlasmaState:
    node_id: str
    tensor_repr: str          # string representation of the state tensor/vector
    split: str = "train"
    created_by: str = "sovereign_pipeline"
    review_status: str = "pending"
    weight: float = 1.0
    valid: bool = True
    route_from: str = "input"
    route_to: str = "transform"
    state_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    source_sha256: str = ""   # computed automatically if empty
    proof_hash: str = ""      # computed automatically if empty


class PlasmaGate:
    """
    Serializes sovereign pipeline states to the Plasma Gate XML schema.
    Computes SHA-256 proof hash over the full serialized state.
    Validates incoming state XML against the schema.
    """

    def _build_tree(self, state: PlasmaState, include_proof: bool = False, proof_hash: str = "") -> ET.Element:
        """Build the XML ElementTree for a PlasmaState."""
        root = ET.Element("state")

        # <node id="..."><tensor>...</tensor></node>
        node_el = ET.SubElement(root, "node", id=state.node_id)
        tensor_el = ET.SubElement(node_el, "tensor")
        tensor_el.text = state.tensor_repr

        # <metadata>
        meta_el = ET.SubElement(root, "metadata")
        id_el = ET.SubElement(meta_el, "id")
        id_el.text = state.state_id
        sha_el = ET.SubElement(meta_el, "source_sha256")
        sha_el.text = state.source_sha256
        split_el = ET.SubElement(meta_el, "split")
        split_el.text = state.split
        cb_el = ET.SubElement(meta_el, "created_by")
        cb_el.text = state.created_by
        rs_el = ET.SubElement(meta_el, "review_status")
        rs_el.text = state.review_status
        w_el = ET.SubElement(meta_el, "weight")
        w_el.text = str(state.weight)

        # <constraint>
        constraint_el = ET.SubElement(root, "constraint")
        cond_el = ET.SubElement(constraint_el, "condition")
        cond_el.text = f"valid={'true' if state.valid else 'false'}"

        # <route>
        route_el = ET.SubElement(root, "route")
        ET.SubElement(route_el, "edge", **{"from": state.route_from, "to": state.route_to})

        # <proof> (optional)
        if include_proof:
            proof_el = ET.SubElement(root, "proof")
            hash_el = ET.SubElement(proof_el, "hash")
            hash_el.text = proof_hash

        return root

    def _serialize_to_bytes(self, root: ET.Element) -> bytes:
        """Serialize an Element to canonical UTF-8 bytes (no XML declaration, no pretty-print)."""
        return ET.tostring(root, encoding="unicode").encode("utf-8")

    def _pretty_print(self, root: ET.Element) -> str:
        """Return a pretty-printed XML string with declaration."""
        raw = ET.tostring(root, encoding="unicode")
        reparsed = minidom.parseString(raw)
        return reparsed.toprettyxml(indent="    ", encoding=None)

    def _strip_whitespace(self, element: ET.Element) -> None:
        """Strip leading/trailing whitespace from all text and tail nodes.

        minidom pretty-printing embeds indentation/newlines into text nodes;
        stripping them lets validate() rebuild the same canonical byte stream
        that seal() hashed.
        """
        if element.text is not None:
            stripped = element.text.strip()
            element.text = stripped if stripped else None
        if element.tail is not None:
            stripped = element.tail.strip()
            element.tail = stripped if stripped else None
        for child in element:
            self._strip_whitespace(child)

    def seal(self, state: PlasmaState) -> str:
        """Serialize state to XML, compute + embed proof hash, return XML string."""
        # Compute source_sha256 from tensor_repr bytes if not already set
        if not state.source_sha256:
            state.source_sha256 = hashlib.sha256(state.tensor_repr.encode("utf-8")).hexdigest()

        # Build tree WITHOUT proof block
        root_no_proof = self._build_tree(state, include_proof=False)
        raw_bytes = self._serialize_to_bytes(root_no_proof)

        # SHA-256 of the content without proof → proof_hash
        proof_hash = hashlib.sha256(raw_bytes).hexdigest()
        state.proof_hash = proof_hash

        # Build full tree WITH proof hash
        root_full = self._build_tree(state, include_proof=True, proof_hash=proof_hash)

        return self._pretty_print(root_full)

    def validate(self, xml_str: str) -> dict:
        """
        Parse XML string, verify:
        - All required fields present (id, source_sha256, split, created_by, review_status, weight)
        - constraint condition is valid=true
        - proof hash matches SHA-256 of the state content (excluding the <proof> block itself)
        Returns dict: {valid: bool, errors: list[str], state_id: str, weight: float}
        """
        errors = []
        state_id = ""
        weight = 0.0

        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            return {"valid": False, "errors": [f"XML parse error: {exc}"], "state_id": "", "weight": 0.0}

        # Check required metadata fields
        from .schema import REQUIRED_METADATA
        meta = root.find("metadata")
        if meta is None:
            errors.append("Missing <metadata> block")
        else:
            for field_name in REQUIRED_METADATA:
                el = meta.find(field_name)
                if el is None or el.text is None or el.text.strip() == "":
                    errors.append(f"Missing or empty metadata field: {field_name}")
            id_el = meta.find("id")
            if id_el is not None and id_el.text:
                state_id = id_el.text.strip()
            weight_el = meta.find("weight")
            if weight_el is not None and weight_el.text:
                try:
                    weight = float(weight_el.text.strip())
                except ValueError:
                    errors.append("Invalid weight value (not a float)")

        # Check constraint condition
        constraint = root.find("constraint")
        if constraint is None:
            errors.append("Missing <constraint> block")
        else:
            cond = constraint.find("condition")
            if cond is None or cond.text is None:
                errors.append("Missing <condition> in <constraint>")
            elif cond.text.strip() != "valid=true":
                errors.append(f"Constraint condition is not valid=true: '{cond.text.strip()}'")

        # Extract stored proof hash
        proof_el = root.find("proof")
        stored_hash = ""
        if proof_el is None:
            errors.append("Missing <proof> block")
        else:
            hash_el = proof_el.find("hash")
            if hash_el is None or hash_el.text is None:
                errors.append("Missing <hash> in <proof>")
            else:
                stored_hash = hash_el.text.strip()

        # Recompute proof hash: rebuild state WITHOUT the <proof> block.
        # We must strip pretty-print whitespace so the byte stream matches
        # what seal() hashed (seal() hashes the compact, non-pretty form).
        if proof_el is not None and stored_hash:
            root_copy = ET.fromstring(xml_str)
            proof_copy = root_copy.find("proof")
            if proof_copy is not None:
                root_copy.remove(proof_copy)
            self._strip_whitespace(root_copy)
            recomputed_bytes = ET.tostring(root_copy, encoding="unicode").encode("utf-8")
            recomputed_hash = hashlib.sha256(recomputed_bytes).hexdigest()
            if recomputed_hash != stored_hash:
                errors.append(
                    f"Proof hash mismatch: stored={stored_hash!r}, recomputed={recomputed_hash!r}"
                )

        is_valid = len(errors) == 0
        return {"valid": is_valid, "errors": errors, "state_id": state_id, "weight": weight}

    def from_entropy(self, entropy: complex, op: str, constraint: dict) -> PlasmaState:
        """
        Convenience: build a PlasmaState from the entropy engine output.
        tensor_repr = str(entropy)
        weight = constraint['magnitude']
        valid = constraint['valid']
        route_from = 'input', route_to = op (the selected kernel op)
        """
        return PlasmaState(
            node_id="input",
            tensor_repr=str(entropy),
            weight=float(constraint.get("magnitude", 1.0)),
            valid=bool(constraint.get("valid", True)),
            route_from="input",
            route_to=op,
        )
