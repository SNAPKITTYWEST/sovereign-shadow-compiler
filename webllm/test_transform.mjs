// test_transform.mjs
// 8 unit tests for the AST TransformEngine
// Run: node webllm/test_transform.mjs

import { TransformEngine } from './transform.mjs';

const engine = new TransformEngine();

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  PASS  ${name}`);
    passed++;
  } catch (e) {
    console.log(`  FAIL  ${name}`);
    console.log(`        ${e.message}`);
    failed++;
  }
}

function assert(condition, msg) {
  if (!condition) throw new Error(msg || 'assertion failed');
}

// ─── Tests ───────────────────────────────────────────────────────────────────

console.log('\nTransformEngine test suite\n');

// Test 1 — Double negation elimination
test('double-negation: NOT(NOT(x)) → x', () => {
  const xml = '<route><not><not><leaf op="ADD" weight="0.5" valid="true"/></not></not></route>';
  const { xml: out, log } = engine.transform(xml);
  assert(out.includes('<leaf op="ADD"'), `expected leaf in output, got: ${out}`);
  assert(!out.includes('<not>'), `expected no <not> in output, got: ${out}`);
  assert(log.some(e => e.rule === 'double-negation-elimination'), 'expected rule to fire');
});

// Test 2 — Idempotent AND
test('idempotent-and: AND(MUL, MUL) → single MUL leaf', () => {
  const xml = '<route><and><leaf op="MUL" weight="0.5" valid="true"/><leaf op="MUL" weight="0.5" valid="true"/></and></route>';
  const { xml: out, log } = engine.transform(xml);
  assert(out.includes('<leaf op="MUL"'), `expected MUL leaf in output, got: ${out}`);
  assert(!out.includes('<and>'), `expected no <and> wrapper in output, got: ${out}`);
  // Should appear only once
  const count = (out.match(/<leaf op="MUL"/g) || []).length;
  assert(count === 1, `expected exactly 1 MUL leaf, found ${count} in: ${out}`);
  assert(log.some(e => e.rule === 'idempotent-and'), 'expected idempotent-and rule to fire');
});

// Test 3 — AND short-circuit false
test('and-short-circuit-false: AND with valid=false leaf → invalid', () => {
  const xml = '<route><and><leaf op="ADD" weight="0.8" valid="false"/><leaf op="MUL" weight="0.3" valid="true"/></and></route>';
  const { xml: out, log } = engine.transform(xml);
  assert(out.includes('valid="false"'), `expected valid=false in output, got: ${out}`);
  assert(!out.includes('<and>'), `expected AND to be replaced, got: ${out}`);
  assert(log.some(e => e.rule === 'and-short-circuit-false'), 'expected and-short-circuit-false rule to fire');
});

// Test 4 — NOT(MEMSET) → XOR
test('not-memset-to-xor: NOT(MEMSET) emits XOR leaf', () => {
  const xml = '<route><not><leaf op="MEMSET" weight="0.5" valid="true"/></not></route>';
  const { xml: out, log } = engine.transform(xml);
  assert(out.includes('op="XOR"'), `expected XOR leaf in output, got: ${out}`);
  assert(!out.includes('<not>'), `expected no <not> wrapper in output, got: ${out}`);
  assert(!out.includes('op="MEMSET"'), `expected MEMSET to be replaced, got: ${out}`);
  assert(log.some(e => e.rule === 'not-memset-to-xor'), 'expected not-memset-to-xor rule to fire');
});

// Test 5 — AND(MEMCPY, MEMSET) → MEMCPY
test('and-memcpy-memset-to-memcpy: AND(MEMCPY, MEMSET) → single MEMCPY leaf', () => {
  const xml = '<route><and><leaf op="MEMCPY" weight="0.5" valid="true"/><leaf op="MEMSET" weight="0.3" valid="true"/></and></route>';
  const { xml: out, log } = engine.transform(xml);
  assert(out.includes('op="MEMCPY"'), `expected MEMCPY leaf in output, got: ${out}`);
  assert(!out.includes('<and>'), `expected AND to be replaced, got: ${out}`);
  assert(!out.includes('op="MEMSET"'), `expected MEMSET to be absorbed, got: ${out}`);
  assert(log.some(e => e.rule === 'and-memcpy-memset-to-memcpy'), 'expected and-memcpy-memset-to-memcpy rule to fire');
});

// Test 6 — Entropy reduction on depth-4 AST
test('entropyReduce: depth>3 AST flattens to <or> of all leaves', () => {
  // Depth: route(1) → and(2) → or(3) → not(4) → leaf  →  depth = 4
  const xml = [
    '<route>',
    '  <and>',
    '    <or>',
    '      <not>',
    '        <leaf op="ADD" weight="0.5" valid="true"/>',
    '      </not>',
    '      <leaf op="MUL" weight="0.3" valid="true"/>',
    '    </or>',
    '    <leaf op="XOR" weight="0.2" valid="true"/>',
    '  </and>',
    '</route>',
  ].join('\n');

  const { xml: out, reduced, original_depth } = engine.entropyReduce(xml);
  assert(reduced === true, `expected reduced=true, got ${reduced}`);
  assert(typeof original_depth === 'number' && original_depth > 3,
    `expected original_depth > 3, got ${original_depth}`);
  assert(out.includes('<or>'), `expected <or> in flattened output, got: ${out}`);
  assert(out.includes('<route>'), `expected <route> wrapper, got: ${out}`);
  // All three original leaves must be present
  assert(out.includes('op="ADD"'), `expected ADD leaf preserved`);
  assert(out.includes('op="MUL"'), `expected MUL leaf preserved`);
  assert(out.includes('op="XOR"'), `expected XOR leaf preserved`);
  // Should not contain deep nesting tags
  assert(!out.includes('<and>'), `expected no <and> after flattening`);
  assert(!out.includes('<not>'), `expected no <not> after flattening`);
});

// Test 7 — Transform log records which rules fired
test('transform log records fired rules', () => {
  // Two transformations in sequence: double-negation then not-memset-to-xor
  const xml = '<route><not><not><not><leaf op="MEMSET" weight="0.4" valid="true"/></not></not></not></route>';
  const { log } = engine.transform(xml);
  // double-negation should fire first (strips outer NOT(NOT(...))), leaving NOT(MEMSET)
  // then not-memset-to-xor should fire
  assert(log.length >= 2, `expected at least 2 log entries, got ${log.length}: ${JSON.stringify(log)}`);
  assert(log.some(e => e.rule === 'double-negation-elimination'), 'expected double-negation-elimination in log');
  assert(log.some(e => e.rule === 'not-memset-to-xor'), 'expected not-memset-to-xor in log');
  // Each log entry has pass and rule fields
  for (const entry of log) {
    assert(typeof entry.pass === 'number', 'log entry missing pass number');
    assert(typeof entry.rule === 'string', 'log entry missing rule name');
  }
});

// Test 8 — No-op: clean single leaf passes through unchanged with empty log
test('no-op: single valid leaf is unchanged with empty log', () => {
  const xml = '<route><leaf op="HELLO" weight="0.9" valid="true"/></route>';
  const { xml: out, log, passes } = engine.transform(xml);
  assert(out === xml, `expected identity transform, got: ${out}`);
  assert(log.length === 0, `expected empty log, got ${JSON.stringify(log)}`);
  assert(passes === 0, `expected 0 passes, got ${passes}`);
});

// ─── Summary ─────────────────────────────────────────────────────────────────

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
