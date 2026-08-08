if __name__ == "__main__":
    import sys, os
    # Ensure the sovereign-shadow-compiler root is on sys.path
    # so `plasma` resolves whether invoked as `python plasma/demo.py`
    # from the project root or as a module.
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from plasma import PlasmaGate, PlasmaState
    gate = PlasmaGate()
    state = gate.from_entropy(
        entropy=complex(0.7071, 0.2357),
        op="ADD",
        constraint={"valid": True, "magnitude": 1.0, "phase": 0.785, "warnings": [], "force_op": "ADD"},
    )
    xml_str = gate.seal(state)
    print(xml_str)
    result = gate.validate(xml_str)
    print(result)
