import {
  XMLRoutingBridge,
  validateXXEOutput,
  parseRoutingExpression,
  InferenceScheduler,
  ENTROPY_CAP,
} from './xml_router.mjs';

let passed = 0;
let failed = 0;

async function test(name, fn) {
  try {
    await fn();
    console.log(`  PASS  ${name}`);
    passed++;
  } catch(e) {
    console.log(`  FAIL  ${name}: ${e.message}`);
    failed++;
  }
}

function assert(cond, msg) { if (!cond) throw new Error(msg); }

console.log('=== WebLLM AST Routing Tests ===\n');

// --- Test 1: Simple NL → single leaf → ADD ---
await test('NL "add two numbers" → single leaf → ADD', async () => {
  const bridge = new XMLRoutingBridge();
  const result = await bridge.route('add two numbers together');
  assert(result.op === 'ADD', `expected ADD got ${result.op}`);
  assert(result.valid === true, 'should be valid');
  assert(result.node_count >= 1, 'should have at least 1 node');
});

// --- Test 2: Simple NL → single leaf → MUL ---
await test('NL "multiply" → routes to MUL', async () => {
  const bridge = new XMLRoutingBridge();
  const result = await bridge.route('multiply the input by a scale factor');
  assert(result.op === 'MUL', `expected MUL got ${result.op}`);
  assert(result.valid === true, 'should be valid');
});

// --- Test 3: Simple NL → single leaf → STRCMP ---
await test('NL "compare strings" → routes to STRCMP', async () => {
  const bridge = new XMLRoutingBridge();
  const result = await bridge.route('compare these two strings for equality');
  assert(result.op === 'STRCMP', `expected STRCMP got ${result.op}`);
  assert(result.valid === true, 'should be valid');
});

// --- Test 4: Direct AST — AND picks highest-weight valid leaf ---
await test('AND combinator picks highest-weight valid leaf (ADD 0.8 vs MUL 0.5)', async () => {
  const xml = `<route><and><leaf op="ADD" weight="0.8" valid="true"/><leaf op="MUL" weight="0.5" valid="true"/></and></route>`;
  const result = parseRoutingExpression(xml);
  assert(result.valid === true, `expected valid, got: ${result.reason || 'unknown'}`);
  assert(result.op === 'ADD', `expected ADD (highest weight 0.8) got ${result.op}`);
  assert(result.node_count >= 3, `expected ≥3 nodes got ${result.node_count}`);
});

// --- Test 5: Direct AST — OR picks first valid leaf ---
await test('OR combinator picks first valid leaf (XOR invalid, LOOP valid)', async () => {
  const xml = `<route><or><leaf op="XOR" weight="0.1" valid="false"/><leaf op="LOOP" weight="0.9" valid="true"/></or></route>`;
  const result = parseRoutingExpression(xml);
  assert(result.valid === true, `expected valid, got: ${result.reason || 'unknown'}`);
  assert(result.op === 'LOOP', `expected LOOP (first valid) got ${result.op}`);
});

// --- Test 6: Direct AST — NOT negates child validity ---
await test('NOT negates child leaf validity (MUL valid → NOT → invalid)', async () => {
  const xml = `<route><not><leaf op="MUL" weight="0.5" valid="true"/></not></route>`;
  const result = parseRoutingExpression(xml);
  assert(result.valid === false, `expected valid=false after NOT, got valid=${result.valid}`);
  assert(result.op === 'MUL', `op should still propagate as MUL got ${result.op}`);
});

// --- Test 7: XXE hardening rejects DOCTYPE ---
await test('XXE hardening rejects DOCTYPE in LLM output', async () => {
  let threw = false;
  try {
    validateXXEOutput('<!DOCTYPE foo SYSTEM "file:///etc/passwd"><route><leaf op="ADD" weight="0.05" valid="true"/></route>');
  } catch(e) {
    threw = true;
    assert(e.message.includes('DOCTYPE'), `wrong error: ${e.message}`);
  }
  assert(threw, 'should have thrown on DOCTYPE');
});

// --- Test 8: Scheduler enforces entropy cap at 0.20 ---
await test('Scheduler enforces entropy cap at 0.20', async () => {
  const sched = new InferenceScheduler();
  sched.schedule(0.05);
  sched.schedule(0.05);
  sched.schedule(0.05);
  sched.schedule(0.05);
  let threw = false;
  try { sched.schedule(0.05); } catch(e) { threw = true; }
  assert(threw, '5th schedule at 0.05 should exceed ENTROPY_CAP=0.20');
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
