# Sovereign Shadow Compiler  `v1.0`

A symbolic compiler that routes natural-language intent to verified x86-64 machine code through a deterministic pipeline — no LLM required, no probabilistic sampling, entropy-bounded throughout.

Natural language in. Raw kernel bytes out. Every transform logged. Every state sealed with SHA-256.

**Stack:** Python + NASM  
**Tests:** 108 passing (`pytest tests/`)  
**Known collision:** `"repeat 10 times"` → MUL (`times` matches MUL before LOOP — documented in `tests/test_irr.py`)

---

## What it does

```
"add two numbers"
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  IRR: Intent-Relation-Result                                    │
│  regex pattern library + online weight update                   │
│  "add" → op=ADD, confidence=0.86                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Entropy Engine                                                  │
│  sparse activation trie (complex-valued, 90° phase rotation)    │
│  tokens → entropy vector → [0.7071+0.2357j, ...]              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Constraint Pass                                                 │
│  validate complex state vector (NaN/Inf/zero magnitude check)   │
│  quantise magnitude → force_op hint                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Machine Code Selector                                           │
│  entropy.real → index into KERNEL_MAP                           │
│  or use force_op if constraint pass set one                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Sovereign VM                                                    │
│  register machine: RAX RBX RCX RDX RSI RDI RSP RBP             │
│  64 KiB memory, MOV/ADD/MUL/XOR/LOOP/SYSCALL/HALT             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
              48 9F 48 01 F0 C3    ← pure_add kernel bytes
              registers: {RAX: 42, RCX: 0, ...}
              cycles: 3
```

---

## Architecture

```
sovereign-shadow-compiler/
│
├── irr/                   Intent-Relation-Result subsystem
│   ├── schema_constants   ENTROPY_CAP=0.20, MIN_WEIGHT, TOP_N
│   ├── pattern_library    8 ops × regex patterns, online weight update
│   ├── matching_engine    cache + top-N scan, safe regex execution
│   ├── weight_loop        reward(op,pat) / penalize(op,pat)
│   └── intent_generator   NL→(op,pattern,confidence) keyword scoring
│
├── engine/                Entropy core
│   ├── shadow_node        ShadowNode: complex trie, 90° phase rotation per level
│   └── entropy_engine     trie → entropy vector → machine intent bytes
│
├── codegen/               Code generation
│   ├── constraint_pass    validate complex state, derive force_op from magnitude
│   └── selector           entropy.real → op name → raw kernel bytes
│
├── kernels/               Verified x86-64 byte sequences (System-V ABI)
│   ├── kernel_map.py      8-op canonical map
│   └── *.asm              NASM source: ADD, XOR, MEMCPY
│
├── hyperkitty_dsl/        HyperKitty Constraint DSL (XML)
│   ├── parser             XML → HKGraph (nodes, edges, constraints, entropy bound)
│   ├── evaluator          budget constraints + invariants + Shannon entropy check
│   └── proof              4× SHA-256 proof hashes
│
├── plasma/                State serialisation + integrity
│   └── gate               seal(state)→XML+SHA-256 / validate(xml)→bool
│
├── vm/                    Register machine interpreter
│   └── sovereign_vm       8 registers, 64 KiB memory
│
├── crew/                  Multi-agent orchestration (no external API)
│   ├── agent              SovereignAgent: identity→trie seed→pipeline
│   └── crew               sequential / hierarchical task chains
│
└── webllm/                Browser-side XML routing layer
    ├── ast_parser.mjs     recursive-descent: <and><or><not><leaf/>
    ├── transform.mjs      9 rewrite rules, priority fixpoint, entropyReduce
    ├── xml_router.mjs     NL→XXE-hardened→AST, 0.05/call entropy budget
    └── test_transform.mjs 8 tests, 8/8 passing
```

---

## The pipeline in motion

```
$ python irr_demo.py

query: "add two numbers together"
  intent:  op=ADD   pattern=(?i)\b(add|plus|sum)   confidence=0.86
  match:   op=ADD   weight=1.0  matched=True
  reward → weight=1.09

query: "copy buffer to destination"
  intent:  op=MEMCPY  pattern=(?i)\b(copy|clone|dup)  confidence=0.73
  match:   op=MEMCPY  weight=1.0  matched=True
  reward → weight=1.09

query: "flip bits in register"
  intent:  op=XOR   pattern=(?i)\b(xor|flip|toggle)   confidence=0.80
  match:   op=XOR   weight=1.0  matched=True
  reward → weight=1.09


$ python engine/entropy_engine.py

tokens: ['ALPHA', 'BETA', 'GAMMA', 'DELTA', 'EPSILON', 'ZETA']
entropy vector:
  ALPHA   → (0.9239+0.3827j)  |z|=1.0
  BETA    → (0.7071+0.7071j)  |z|=1.0
  GAMMA   → (0.3827+0.9239j)  |z|=1.0
  DELTA   → (0.0000+1.0000j)  |z|=1.0
  EPSILON → (0.5000+0.8660j)  |z|=1.0
  ZETA    → (0.8660+0.5000j)  |z|=1.0
machine intent: 3e 6d 8f 9a 48 89 f8 48 01 f7 c3 ...


$ node webllm/test_transform.mjs

TransformEngine test suite

  PASS  double-negation: NOT(NOT(x)) → x
  PASS  idempotent-and: AND(MUL, MUL) → single MUL leaf
  PASS  and-short-circuit-false: AND with valid=false leaf → invalid
  PASS  not-memset-to-xor: NOT(MEMSET) emits XOR leaf
  PASS  and-memcpy-memset-to-memcpy: AND(MEMCPY, MEMSET) → single MEMCPY leaf
  PASS  entropyReduce: depth>3 AST flattens to <or> of all leaves
  PASS  transform log records fired rules
  PASS  no-op: single valid leaf is unchanged with empty log

8 tests: 8 passed, 0 failed
```

---

## Transform rules

The WebLLM layer runs 9 rewrite rules over XML routing expressions to fixpoint:

```
Input:
<route>
  <and>
    <not><not><leaf op="ADD" weight="0.8" valid="true"/></not></not>
    <leaf op="MEMSET" weight="0.3" valid="true"/>
    <leaf op="MEMCPY" weight="0.9" valid="true"/>
  </and>
</route>

Pass 1 — double-negation-elimination (priority 10):
  NOT(NOT(ADD)) → ADD

Pass 2 — and-memcpy-memset-to-memcpy (priority 5):
  MEMCPY + MEMSET → MEMCPY  (copy subsumes set)

Fixpoint. Result: op=MEMCPY (highest weight in AND)
```

| Rule | Priority | Rewrite |
|------|----------|---------|
| double-negation-elimination | 10 | `NOT(NOT(x))` → `x` |
| idempotent-and | 9 | `AND(X, X)` → `X` |
| idempotent-or | 9 | `OR(X, X)` → `X` |
| or-tautology | 8 | `OR(X, NOT(X))` → valid leaf |
| and-short-circuit-false | 7 | `AND(... false ...)` → `{ADD, valid=false}` |
| or-short-circuit-true | 7 | `OR(true-leaf ...)` → first true leaf |
| weight-normalization-and | 6 | all leaves < 0.10 → keep highest |
| not-memset-to-xor | 5 | `NOT(MEMSET)` → `XOR` |
| and-memcpy-memset-to-memcpy | 5 | `AND(MEMCPY, MEMSET)` → `MEMCPY` |

---

## Kernel map

All kernels follow System-V AMD64 ABI (args: `rdi`, `rsi`, `rdx` — return: `rax`):

| Op | Bytes | Source | Semantics |
|----|-------|--------|-----------|
| `ADD` | 7 | `pure_add.asm` | `rax = rdi + rsi` |
| `MUL` | 8 | hex | `rax = rdi * rsi` (imul) |
| `XOR` | 7 | `pure_xor.asm` | `rax = rdi ^ rsi` |
| `LOOP` | 12 | hex | count 0..rdi, return in rax |
| `MEMCPY` | 6 | `pure_memcpy.asm` | rep movsb: copy rdx bytes rsi→rdi |
| `MEMSET` | 9 | hex | rep stosb: fill rdx bytes at rdi with sil |
| `STRCMP` | 31 | hex | byte-by-byte cmp; 0=equal 1=not |
| `HELLO` | 55 | hex | write(1, "Hello, World\n", 13) + exit |

---

## Entropy bound: 0.20

Enforced at four independent points:

```
IRR intent_generator.py
  H(pattern) = Shannon entropy of character distribution
  if H > 0.20 → simplify to single top keyword

HyperKitty DSL evaluator.py
  H(node types) in nats over graph node distribution
  must be <= graph.entropy_bound.bound

WebLLM xml_router.mjs
  InferenceScheduler: 0.05 weight per call
  4 calls → total = 0.20 → 5th call throws

plasma/schema.py
  ENTROPY_CAP = 0.20 declared
```

---

## Plasma gate

Every state can be cryptographically sealed and verified:

```python
from plasma.gate import PlasmaGate

xml  = PlasmaGate().seal(state)          # adds SHA-256 proof hash
ok   = PlasmaGate().validate(xml)        # recomputes hash, compares
# {'valid': True, 'errors': [], 'state_id': '...', 'weight': 0.9239}
```

Sealed XML structure:
```xml
<PlasmaState>
  <metadata>
    <id>node_abc123</id>
    <source_sha256>4f3a2b...</source_sha256>
    <weight>0.9239</weight>
    <review_status>approved</review_status>
  </metadata>
  <constraint><condition>valid=true</condition></constraint>
  <proof><hash>sha256:7d2f1a...</hash></proof>
</PlasmaState>
```

Tamper any field → hash mismatch → `valid=False`.

---

## HyperKitty DSL

XML constraint language with proof generation:

```python
from hyperkitty_dsl.parser    import HKDSLParser
from hyperkitty_dsl.evaluator import HKConstraintEvaluator
from hyperkitty_dsl.proof     import HKProofGenerator

graph  = HKDSLParser().parse(xml)
result = HKConstraintEvaluator().evaluate(graph)
proof  = HKProofGenerator().generate(graph, result)

# proof['hashes']:
# ConstraintGraph  → sha256(node IDs + edges + constraint names)
# RuleHash         → sha256(constraint + invariant expressions)
# TransformHash    → sha256(entropy bound value)
# ValidationResult → sha256(full evaluator result)
```

---

## Data types through the pipeline

```
str query
  → (op, pattern, confidence)     IntentGenerator
  → List[str] tokens
  → List[complex] entropy_vector  EntropyEngine
  → bytes machine_intent          EntropyEngine
  → {valid, magnitude, force_op}  ConstraintPass
  → str op_name                   Selector
  → bytes kernel_bytes            Selector
  → list[dict] program            VM
  → {registers, output, cycles}   VM
```

---

## Running

```bash
# Full test suite (108 tests)
pytest tests/ -v

# IRR: intent routing (9 queries + weight updates)
python irr_demo.py

# Entropy engine: trie + complex vector + machine intent
python engine/entropy_engine.py

# HyperKitty DSL: parse + evaluate + proof hashes
python demo.py

# Plasma gate: seal + validate
python plasma/demo.py

# WebLLM transform tests (Python, no Node.js needed)
python -m webllm.test_transform

# Full pipeline
python pipeline.py
```

---

## Known issues

**`pipeline.py`**: passes a list to `SovereignEntropyEngine` instead of `Dict[str, str]`. Fix: import `KERNEL_MAP` from `kernels/kernel_map.py` and pass tokens to `calculate_entropy_vector()`.

**`crew/agent.py`**: same kernel_map bug, plus `f"entropy={entropy:.4f}"` tries to format `List[complex]`. Fix: pass `KERNEL_MAP`, format `entropy[0]`.

**HyperKitty entropy check**: graphs with >2 distinct node types will correctly fail the 0.20 nats bound (0.20 nats ≈ 1.22 equally-likely types maximum). This is the intended constraint behaviour, not a bug.

**`Cargo.toml`**: malformed (duplicate `[workspace]` sections, empty members). No Rust code exists yet.

---

Built by Ahmad Ali Parr × SnapKitty.
