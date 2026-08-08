KERNEL_MAP = {
    "ADD":     "48 89 f8 48 01 f0 c3",
    "MUL":     "48 89 f8 48 0f af c6 c3",
    "XOR":     "48 89 f8 48 31 f0 c3",
    "LOOP":    "48 31 c0 48 ff c0 48 39 f8 7c f8 c3",
    "MEMCPY":  "48 89 d1 f3 a4 c3",
    "MEMSET":  "48 89 d1 40 88 f0 f3 aa c3",
    "STRCMP":  "48 31 c0 8a 0f 8a 16 38 d1 75 0c 84 c9 74 0a 48 ff c7 48 ff c6 eb ee 48 19 c0 48 83 c8 01 c3",
    "HELLO":   "48 c7 c0 01 00 00 00 48 c7 c7 01 00 00 00 48 8d 35 0e 00 00 00 48 c7 c2 0d 00 00 00 0f 05 48 c7 c0 3c 00 00 00 48 31 ff 0f 05 48 65 6c 6c 6f 2c 20 57 6f 72 6c 64 0a",
}

def bytes_for(op: str) -> bytes:
    return bytes(int(b, 16) for b in KERNEL_MAP[op].split())
