# Sovereign Shadow Compiler  `v1.0`

A symbolic compiler that routes natural-language intent to verified x86-64 machine code.
No neural network inference in the hot path. No probabilistic sampling. No JavaScript.
Entropy bounded at 0.20 nats throughout. Every state sealed with SHA-256.

**Stack:** Python + NASM  
**Tests:** 108 passing — `pytest tests/`

---

## Routing flow

Three subsystems resolve the same natural-language query independently and agree on the op.

```
"copy buffer to destination"
          │
          ├─── Path 1: WebLLM XML bridge ────────────────────────────────────────┐
          │    LLM.generate(query)                                                │
          │      → raw XML string                                                 │
          │      → validate_xxe_output()    blocks DOCTYPE/ENTITY/&ref;/SYSTEM   │
          │      → safe_stream_extract()    isolates <route>...</route>           │
          │      → transform rules          9 rewrites to fixpoint                │
          │      → parse_routing_ast()      recursive XML bool evaluator          │
          │    result: op=MEMCPY  valid=True  weight=0.05                         │
          │                                                                       │
          ├─── Path 2: IRR direct ────────────────────────────────────────────────┤
          │    IntentGenerator   keyword scoring                                  │
          │      → op=MEMCPY  conf=0.73  pattern=(?i)\b(copy|clone|memcpy)\b     │
          │    MatchingEngine   top-N regex scan                                  │
          │      → op=MEMCPY  matched=True  weight=1.0                            │
          │                                                                       │
          └─── Path 3: Entropy pipeline ──────────────────────────────────────────┘
               SovereignEntropyEngine   sparse complex trie, 90° phase rotation
                 "MEMCPY" → (0.3827+0.9239j)  |z|=1.0
               ConstraintPass   NaN/Inf/zero check → force_op hint
               MachineCodeSelector   entropy.real → kernel index
                 op=MEMCPY → 48 89 F9 48 89 F0 F3 A4 C3
               SovereignVM   register machine
                 RAX=0 RCX=0  cycles=2
               PlasmaGate   SHA-256 seal
                 <proof><hash>7d2f1a...</hash></proof>
```

**Verified agreement across 10 query types:**

```
"add two numbers"              ADD     ADD     ADD
"multiply by scale factor"     MUL     MUL     MUL
"xor the bits"                 XOR     XOR     XOR
"copy buffer to destination"   MEMCPY  MEMCPY  MEMCPY
"set memory to zero"           MEMSET  MEMSET  MEMSET
"compare two strings"          STRCMP  STRCMP  STRCMP
"hello world"                  HELLO   HELLO   HELLO
"add and multiply"             ADD     ADD     ADD    (AND tree, ADD wins)
"copy but not set"             MEMCPY  MEMCPY  MEMCPY (AND+NOT tree)
"unknown garbage xyz"          ADD     ADD     ADD    (fallback)
                               route   intent  match
```

---

## XXE guard

The LLM output is an untrusted XML string. `validate_xxe_output` inspects it before the string reaches the AST parser.

```
LLM.generate() → raw string
                      │
                      ▼  validate_xxe_output()
                      │
         BLOCKED ◄────┤  '<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
         BLOCKED ◄────┤  '<route>&shell;</route>'
         BLOCKED ◄────┤  'SYSTEM "/etc/shadow"'
         BLOCKED ◄────┤  '<!ENTITY xxe "evil">'
                      │
         ALLOWED ─────┘  '<route><leaf op="ADD" weight="0.05" valid="true"/></route>'
                      │
                      ▼  safe_stream_extract() → transform rules → parse_routing_ast()
```

---

## Transform rules

Nine rewrite rules run to fixpoint on the `<route>` XML before dispatch. Rules fire highest-priority first; after each firing the scan restarts.

```
NOT(NOT(AND(MEMCPY, MEMSET)))

pass 1  double-negation-elimination  (priority 10)
  NOT(NOT(x)) → x  →  AND(MEMCPY, MEMSET)

pass 2  and-memcpy-memset-to-memcpy  (priority 5)
  AND(MEMCPY, MEMSET) → MEMCPY

fixpoint  op=MEMCPY  valid=true  passes=2
```

| Rule | Priority | Rewrite |
|------|----------|---------|
| double-negation-elimination | 10 | `NOT(NOT(x))` → `x` |
| idempotent-and | 9 | `AND(X, X)` → `X` |
| idempotent-or | 9 | `OR(X, X)` → `X` |
| or-tautology | 8 | `OR(X, NOT(X))` → valid leaf |
| and-short-circuit-false | 7 | `AND(... false ...)` → `{ADD, valid=false}` |
| or-short-circuit-true | 7 | `OR(true ...)` → first true leaf |
| weight-normalization-and | 6 | all leaves < 0.10 → keep highest |
| not-memset-to-xor | 5 | `NOT(MEMSET)` → `XOR` |
| and-memcpy-memset-to-memcpy | 5 | `AND(MEMCPY, MEMSET)` → `MEMCPY` |

---

## Entropy cap: 0.20

Four independent enforcement points, each measuring something different:

| Where | What it measures | Effect of breach |
|-------|-----------------|-----------------|
| `irr/intent_generator.py` | Shannon entropy of the regex pattern's character distribution | Simplify pattern to single top keyword |
| `hyperkitty_dsl/evaluator.py` | Shannon entropy (nats) of node-type distribution in graph | `entropy_check.passed = False` |
| `webllm/xml_router.py` | Cumulative inference weight (0.05 per call) | `RuntimeError` on call 5 |
| `plasma/schema.py` | Schema contract constant | Declared boundary |

---

## Kernel map

System-V AMD64 ABI — args: `rdi`, `rsi`, `rdx` — return: `rax`

| Op | Bytes | Semantics |
|----|-------|-----------|
| `ADD` | 7 | `rax = rdi + rsi` |
| `MUL` | 8 | `rax = rdi * rsi` |
| `XOR` | 7 | `rax = rdi ^ rsi` |
| `LOOP` | 12 | count 0→rdi into rax |
| `MEMCPY` | 6 | `rep movsb` copy rdx bytes rsi→rdi |
| `MEMSET` | 9 | `rep stosb` fill rdx bytes at rdi |
| `STRCMP` | 31 | byte-by-byte compare; 0=equal 1=not |
| `HELLO` | 55 | `write(1, "Hello, World\n", 13)` + `exit` |

NASM source: `pure_add.asm`, `pure_xor.asm`, `pure_memcpy.asm`. Others are hex-only in `kernels/kernel_map.py`.

---

## Architecture

```
sovereign-shadow-compiler/
│
├── irr/              Intent-Relation-Result
│   ├── schema_constants  ENTROPY_CAP=0.20, MIN_WEIGHT, TOP_N
│   ├── pattern_library   8 ops × regex, online weight update
│   ├── matching_engine   cache + top-N scan, safe regex
│   ├── weight_loop       reward() / penalize()
│   └── intent_generator  NL → (op, pattern, confidence)
│
├── engine/           Entropy core
│   ├── shadow_node   complex trie, 90° phase rotation per level
│   └── entropy_engine trie → |z|=1.0 vector → machine bytes
│
├── codegen/          Code generation
│   ├── constraint_pass  validate complex state, derive force_op
│   └── selector         entropy.real → kernel, or force_op
│
├── kernels/          Verified x86-64 byte sequences
│   └── kernel_map.py    ADD MUL XOR LOOP MEMCPY MEMSET STRCMP HELLO
│
├── hyperkitty_dsl/   Constraint DSL (XML)
│   ├── parser        XML → HKGraph
│   ├── evaluator     budget constraints + entropy check
│   └── proof         4× SHA-256 hashes
│
├── plasma/           State integrity
│   └── gate          seal() / validate() with SHA-256
│
├── vm/               Register machine
│   └── sovereign_vm  8 regs, 64 KiB, MOV/ADD/MUL/XOR/LOOP/SYSCALL/HALT
│
├── crew/             Agent orchestration
│   ├── agent         identity → trie seed → pipeline
│   └── crew          sequential / hierarchical chains
│
├── webllm/           XML routing layer
│   ├── ast_parser.py recursive: <route><and><or><not><leaf/>
│   ├── transform.py  9 rewrite rules, fixpoint, entropy_reduce
│   └── xml_router.py LLM + XXE guard + InferenceScheduler
│
└── tests/            108 tests
    ├── test_transform.py   36
    ├── test_ast_parser.py  31
    ├── test_irr.py         27
    └── test_plasma.py      16
```

---

## Running

```bash
pytest tests/ -v               # 108 tests

python irr_demo.py             # IRR routing demo
python engine/entropy_engine.py  # entropy trie output
python demo.py                 # HyperKitty DSL + proof hashes
python plasma/demo.py          # seal + validate
python -m webllm.test_transform  # 8 transform rule tests
```

---

Built by Ahmad Ali Parr × SnapKitty.
