// xml_router.mjs
// Sovereign WebLLM NL-to-AST Routing Bridge
// Flow: natural language query -> LLM -> AST-structured <route> XML
// Internal nodes: <and>, <or>, <not>  |  Leaf nodes: <leaf op="" weight="" valid=""/>
// XXE hardening applies to the generated XML output before it enters the pipeline.

const INFERENCE_WEIGHT_CAP = 0.05;
const ENTROPY_CAP = 0.20;
const MAX_NEW_TOKENS = 30;
const TEMPERATURE = 0.1;

// Known kernel ops the routing expression can target
const VALID_OPS = ['ADD', 'MUL', 'XOR', 'LOOP', 'MEMCPY', 'MEMSET', 'STRCMP', 'HELLO'];

import { parseRoutingAST } from './ast_parser.mjs';

// --- Mock WebLLM (swap for real @mlc-ai/web-llm in browser) ---
// Takes a natural language query, returns an AST-structured <route> XML.
// Simple queries  → single <leaf>
// Complex queries → 2-level boolean tree
class MockWebLLM {
  async generate({ prompt, max_new_tokens, temperature }) {
    const q = prompt.toLowerCase();

    // Detect boolean connectives for a 2-level tree
    const hasAnd = q.includes(' and ') && !q.includes(' or ') && !q.includes('but not');
    const hasOr = q.includes(' or ');
    const hasButNot = q.includes('but not') || (q.includes(' not ') && q.includes(' and '));

    // Leaf op selection
    function pickOp(text) {
      if (text.includes('mul') || text.includes('multiply') || text.includes('times')) return 'MUL';
      if (text.includes('xor') || text.includes('toggle') || text.includes('flip')) return 'XOR';
      if (text.includes('loop') || text.includes('repeat') || text.includes('count')) return 'LOOP';
      if (text.includes('copy') || text.includes('memcpy')) return 'MEMCPY';
      if (text.includes('set') || text.includes('fill') || text.includes('zero')) return 'MEMSET';
      if (text.includes('compare') || text.includes('strcmp') || text.includes('equal')) return 'STRCMP';
      if (text.includes('hello') || text.includes('print') || text.includes('output')) return 'HELLO';
      if (text.includes('add') || text.includes('sum') || text.includes('plus')) return 'ADD';
      return 'ADD';
    }

    const primaryOp = pickOp(q);

    if (hasButNot) {
      // "X but not Y" → <and><leaf primary/><not><leaf secondary/></not></and>
      // Split on "but not" or "and not"
      const sep = q.includes('but not') ? 'but not' : 'and not';
      const parts = q.split(sep);
      const op1 = pickOp(parts[0] || '');
      const op2 = pickOp(parts[1] || 'xor');
      return `<route>
  <and>
    <leaf op="${op1}" weight="0.05" valid="true"/>
    <not>
      <leaf op="${op2}" weight="0.02" valid="true"/>
    </not>
  </and>
</route>`;
    }

    if (hasOr) {
      // Split on " or "
      const parts = q.split(' or ');
      const op1 = pickOp(parts[0] || '');
      const op2 = pickOp(parts[1] || '');
      return `<route>
  <or>
    <leaf op="${op1}" weight="0.05" valid="true"/>
    <leaf op="${op2}" weight="0.03" valid="true"/>
  </or>
</route>`;
    }

    if (hasAnd) {
      // Split on " and "
      const parts = q.split(' and ');
      const op1 = pickOp(parts[0] || '');
      const op2 = pickOp(parts[1] || '');
      return `<route>
  <and>
    <leaf op="${op1}" weight="0.05" valid="true"/>
    <leaf op="${op2}" weight="0.03" valid="true"/>
  </and>
</route>`;
    }

    // Default: single-leaf route
    return `<route>\n  <leaf op="${primaryOp}" weight="0.05" valid="true"/>\n</route>`;
  }
}

// --- XXE hardening validator ---
// The LLM must only produce plain XML with no external entity references.
// Rejects DOCTYPE declarations, entity refs (&foo;), and external system identifiers.
function validateXXEOutput(raw) {
  if (typeof raw !== 'string') throw new Error('LLM output must be a string');
  if (/<!DOCTYPE/i.test(raw)) throw new Error('XXE: DOCTYPE forbidden in LLM output');
  if (/<!ENTITY/i.test(raw)) throw new Error('XXE: ENTITY declaration forbidden');
  if (/&[a-zA-Z][a-zA-Z0-9]*;/.test(raw)) throw new Error('XXE: entity reference forbidden in LLM output');
  if (/SYSTEM\s+["']/i.test(raw)) throw new Error('XXE: SYSTEM identifier forbidden');
  return raw;
}

// --- Safe streaming wrapper ---
// Wraps raw XML output in <root> and stops reading after </route>
function safeStreamExtract(xml) {
  const wrapped = '<root>' + xml + '</root>';
  const start = wrapped.indexOf('<route');
  if (start === -1) return null;
  // Verify it's really <route> and not <router> etc.
  const charAfter = wrapped[start + 6];
  if (charAfter !== '>' && charAfter !== ' ' && charAfter !== '\t' &&
      charAfter !== '\n' && charAfter !== '/') return null;
  const end = wrapped.indexOf('</route>', start);
  if (end === -1) return null;
  return wrapped.slice(start, end + '</route>'.length);
}

// --- Parse the routing AST XML into a plain object ---
// Delegates to the standalone ast_parser module.
// Returns { op, weight, valid, ast_depth, node_count, reason? }
function parseRoutingExpression(routeXml) {
  return parseRoutingAST(routeXml);
}

// --- Weight-aware scheduler ---
class InferenceScheduler {
  constructor() { this.totalWeight = 0; }
  canSchedule(weight) { return (this.totalWeight + weight) <= ENTROPY_CAP; }
  schedule(weight) {
    if (!this.canSchedule(weight)) {
      throw new Error(`Entropy cap exceeded: ${this.totalWeight + weight} > ${ENTROPY_CAP}`);
    }
    this.totalWeight += weight;
    return weight;
  }
  reset() { this.totalWeight = 0; }
}

// --- Main bridge ---
// Input: natural language query string
// Output: { op, weight, valid, ast_depth, node_count, total_entropy, raw_xxe }
export class XMLRoutingBridge {
  constructor(llm = null) {
    this.llm = llm || new MockWebLLM();
    this.scheduler = new InferenceScheduler();
  }

  async route(naturalLanguageQuery) {
    this.scheduler.schedule(INFERENCE_WEIGHT_CAP);

    const prompt = naturalLanguageQuery;
    const raw = await this.llm.generate({
      prompt,
      max_new_tokens: MAX_NEW_TOKENS,
      temperature: TEMPERATURE,
    });

    // Stop at </route> — stream-to-routing bridge
    const closingTag = '</route>';
    const closingIdx = raw.indexOf(closingTag);
    const trimmed = closingIdx !== -1 ? raw.slice(0, closingIdx + closingTag.length) : raw;

    // XXE hardening on the generated XML
    validateXXEOutput(trimmed);

    // Extract the <route> block safely
    const routeBlock = safeStreamExtract(trimmed);
    if (!routeBlock) {
      return { op: 'ADD', valid: false, reason: 'no <route> block in LLM output', raw_xxe: trimmed };
    }

    const parsed = parseRoutingExpression(routeBlock);
    return {
      ...parsed,
      total_entropy: this.scheduler.totalWeight,
      raw_xxe: routeBlock,
    };
  }

  resetScheduler() { this.scheduler.reset(); }
}

export {
  safeStreamExtract,
  validateXXEOutput,
  parseRoutingExpression,
  InferenceScheduler,
  INFERENCE_WEIGHT_CAP,
  ENTROPY_CAP,
  VALID_OPS,
};
