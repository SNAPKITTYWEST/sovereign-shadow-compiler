from typing import Dict, List

class ShadowNode:
    def __init__(self, key: str, shadow_val: complex):
        self.key = key
        self.shadow_val = shadow_val
        self.children: Dict[str, 'ShadowNode'] = {}
        self.activated = False

    def insert(self, path: List[str], shadow_val: complex) -> None:
        if not path:
            return
        head = path[0]
        if head not in self.children:
            self.children[head] = ShadowNode(head, shadow_val)
        self.children[head].activated = True
        self.children[head].insert(path[1:], shadow_val * 1j)
