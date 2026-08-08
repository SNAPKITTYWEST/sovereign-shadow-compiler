# Sovereign Shadow-State Compiler

Three-layer architecture: an x86-64 primitive kernel layer provides verified byte sequences for eight fundamental operations (add, mul, xor, loop, memcpy, memset, strcmp, hello_world). A sparse activation tree (shadow-state frontend) encodes each symbolic token as a complex-valued path through a trie seeded by phase-rotated unit vectors, producing a normalized entropy projection per token. The entropy-to-machine-code pipeline maps each activated token to its kernel byte sequence via `kernel_map.py`, prepends a 4-byte float header carrying the real part of the entropy weight for VM-side priority scheduling, and concatenates the result into a flat machine-intent buffer.

## Kernels

| Operation | File | Bytes |
|-----------|------|-------|
| ADD | pure_add.asm | 7 |
| MUL | pure_mul.asm | 8 |
| XOR | pure_xor.asm | 7 |
| LOOP | pure_loop.asm | 12 |
| MEMCPY | pure_memcpy.asm | 6 |
| MEMSET | pure_memset.asm | 9 |
| STRCMP | pure_strcmp.asm | 31 |
| HELLO | hello_world.asm | 55 |

## Running

```
python engine/entropy_engine.py
```
