// transform.mjs
// AST transformation ruleset for sovereign routing expressions
// Applies rewrite rules to <route> XML before evaluation
// Rules fire in priority order; engine runs until no rule fires (fixpoint)

import { VALID_OPS } from './ast_parser.mjs';

// Each rule: { name, match(xml), apply(xml) → xml, priority }
// match returns true if the rule applies to this XML string
// apply returns the transformed XML string

const RULES = [
  // ── priority 10 ─────────────────────────────────────────────────────────────
  {
    name: 'double-negation-elimination',
    priority: 10,
    // NOT(NOT(x)) → x
    match(xml) { return /<not>\s*<not>[\s\S]*?<\/not>\s*<\/not>/.test(xml); },
    apply(xml) {
      return xml.replace(/<not>\s*<not>([\s\S]*?)<\/not>\s*<\/not>/g, '$1');
    },
  },

  // ── priority 9 ──────────────────────────────────────────────────────────────
  {
    name: 'idempotent-and',
    priority: 9,
    // AND(x, x) → x  — two leaf children with the same op value
    match(xml) {
      return /<and>\s*<leaf[^>]*op="([^"]+)"[^>]*\/>\s*<leaf[^>]*op="\1"[^>]*\/>\s*<\/and>/.test(xml);
    },
    apply(xml) {
      // Keeps the first leaf; both are identical in op so either is correct
      return xml.replace(
        /<and>\s*(<leaf[^>]*op="([^"]+)"[^>]*\/>)\s*<leaf[^>]*op="\2"[^>]*\/>\s*<\/and>/g,
        '$1'
      );
    },
  },
  {
    name: 'idempotent-or',
    priority: 9,
    // OR(x, x) → x  — two leaf children with the same op value
    match(xml) {
      return /<or>\s*<leaf[^>]*op="([^"]+)"[^>]*\/>\s*<leaf[^>]*op="\1"[^>]*\/>\s*<\/or>/.test(xml);
    },
    apply(xml) {
      return xml.replace(
        /<or>\s*(<leaf[^>]*op="([^"]+)"[^>]*\/>)\s*<leaf[^>]*op="\2"[^>]*\/>\s*<\/or>/g,
        '$1'
      );
    },
  },

  // ── priority 8 ──────────────────────────────────────────────────────────────
  {
    name: 'or-tautology',
    priority: 8,
    // OR(x, NOT(x)) → TRUE  — emit the leaf forced to valid="true"
    // Matches both orderings: leaf-then-NOT and NOT-then-leaf
    match(xml) {
      return (
        /<or>\s*<leaf[^>]*op="([^"]+)"[^>]*\/>\s*<not>\s*<leaf[^>]*op="\1"[^>]*\/>\s*<\/not>\s*<\/or>/.test(xml) ||
        /<or>\s*<not>\s*<leaf[^>]*op="([^"]+)"[^>]*\/>\s*<\/not>\s*<leaf[^>]*op="\1"[^>]*\/>\s*<\/or>/.test(xml)
      );
    },
    apply(xml) {
      const forceValid = (leaf) =>
        leaf.includes('valid=')
          ? leaf.replace(/valid="[^"]*"/, 'valid="true"')
          : leaf.replace('/>', ' valid="true"/>');

      // Case 1: <leaf op="X".../> then <not><leaf op="X".../>...</not>
      let result = xml.replace(
        /<or>\s*(<leaf[^>]*op="([^"]+)"[^>]*\/>)\s*<not>\s*<leaf[^>]*op="\2"[^>]*\/>\s*<\/not>\s*<\/or>/g,
        (_, leaf) => forceValid(leaf)
      );
      // Case 2: <not><leaf op="X".../>...</not> then <leaf op="X".../>
      result = result.replace(
        /<or>\s*<not>\s*<leaf[^>]*op="([^"]+)"[^>]*\/>\s*<\/not>\s*(<leaf[^>]*op="\1"[^>]*\/>)\s*<\/or>/g,
        (_, _op, leaf) => forceValid(leaf)
      );
      return result;
    },
  },

  // ── priority 7 ──────────────────────────────────────────────────────────────
  {
    name: 'and-short-circuit-false',
    priority: 7,
    // AND containing any valid="false" leaf → replace whole AND with an invalid leaf
    match(xml) {
      return /<and>[\s\S]*?<leaf[^>]*valid="false"[^>]*\/>[\s\S]*?<\/and>/.test(xml);
    },
    apply(xml) {
      return xml.replace(/<and>([\s\S]*?)<\/and>/g, (match, inner) => {
        if (/<leaf[^>]*valid="false"[^>]*\/>/.test(inner)) {
          return '<leaf op="ADD" weight="0.0" valid="false"/>';
        }
        return match;
      });
    },
  },
  {
    name: 'or-short-circuit-true',
    priority: 7,
    // OR where the first direct child is a valid="true" leaf → emit that leaf
    match(xml) {
      return /<or>\s*<leaf[^>]*valid="true"[^>]*\/>/.test(xml);
    },
    apply(xml) {
      return xml.replace(
        /<or>\s*(<leaf[^>]*valid="true"[^>]*\/>)[\s\S]*?<\/or>/g,
        '$1'
      );
    },
  },

  // ── priority 6 ──────────────────────────────────────────────────────────────
  {
    name: 'weight-normalization-and',
    priority: 6,
    // All leaves in an AND have weight < 0.10 → collapse to single highest-weight leaf
    match(xml) {
      const andRe = /<and>([\s\S]*?)<\/and>/g;
      let m;
      while ((m = andRe.exec(xml)) !== null) {
        const inner = m[1];
        const leaves = [...inner.matchAll(/<leaf[^>]*\/>/g)].map(lm => lm[0]);
        if (leaves.length === 0) continue;
        const allLow = leaves.every(l => {
          const wm = l.match(/weight="([^"]+)"/);
          return wm ? parseFloat(wm[1]) < 0.10 : true;
        });
        if (allLow) return true;
      }
      return false;
    },
    apply(xml) {
      return xml.replace(/<and>([\s\S]*?)<\/and>/g, (match, inner) => {
        const leaves = [...inner.matchAll(/<leaf[^>]*\/>/g)].map(lm => lm[0]);
        if (leaves.length === 0) return match;
        const allLow = leaves.every(l => {
          const wm = l.match(/weight="([^"]+)"/);
          return wm ? parseFloat(wm[1]) < 0.10 : true;
        });
        if (!allLow) return match;
        // Find highest-weight leaf
        let bestLeaf = leaves[0];
        let bestWeight = -1;
        for (const l of leaves) {
          const wm = l.match(/weight="([^"]+)"/);
          const w = wm ? parseFloat(wm[1]) : 0;
          if (w > bestWeight) { bestWeight = w; bestLeaf = l; }
        }
        return bestLeaf;
      });
    },
  },

  // ── priority 5 ──────────────────────────────────────────────────────────────
  {
    name: 'not-memset-to-xor',
    priority: 5,
    // NOT(MEMSET) → XOR  — XOR is the semantic inverse of MEMSET (zero vs toggle)
    match(xml) {
      return /<not>\s*<leaf op="MEMSET"[^>]*\/>[\s\S]*?<\/not>/.test(xml) ||
             /<not><leaf op="MEMSET"[^>]*\/><\/not>/.test(xml);
    },
    apply(xml) {
      return xml.replace(
        /<not>\s*<leaf op="MEMSET"([^>]*?)\/>\s*<\/not>/g,
        (_, attrs) => `<leaf op="XOR"${attrs}/>`
      );
    },
  },
  {
    name: 'and-memcpy-memset-to-memcpy',
    priority: 5,
    // AND(MEMCPY, MEMSET) → MEMCPY  — copy subsumes set (either order)
    match(xml) {
      return (
        /<and>[\s\S]*?<leaf op="MEMCPY"[\s\S]*?<leaf op="MEMSET"[\s\S]*?<\/and>/.test(xml) ||
        /<and>[\s\S]*?<leaf op="MEMSET"[\s\S]*?<leaf op="MEMCPY"[\s\S]*?<\/and>/.test(xml)
      );
    },
    apply(xml) {
      return xml.replace(/<and>([\s\S]*?)<\/and>/g, (match, inner) => {
        const hasCopy = /op="MEMCPY"/.test(inner);
        const hasSet  = /op="MEMSET"/.test(inner);
        if (hasCopy && hasSet) {
          // Use the weight from the first leaf encountered
          const wMatch = inner.match(/weight="([^"]+)"/);
          const w = wMatch ? wMatch[1] : '0.05';
          return `<leaf op="MEMCPY" weight="${w}" valid="true"/>`;
        }
        return match;
      });
    },
  },
];

// ─── Transform Engine ────────────────────────────────────────────────────────

export class TransformEngine {
  constructor(rules = RULES, maxPasses = 10) {
    this.rules = [...rules].sort((a, b) => b.priority - a.priority);
    this.maxPasses = maxPasses;
  }

  /**
   * Run rules to fixpoint (no rule fires) or maxPasses, whichever comes first.
   * Returns { xml, log, passes }
   *   log   — array of { pass, rule } for every firing
   *   passes — total number of firings
   */
  transform(xml) {
    let current = xml;
    const log = [];

    for (let pass = 0; pass < this.maxPasses; pass++) {
      let fired = false;
      for (const rule of this.rules) {
        if (rule.match(current)) {
          const next = rule.apply(current);
          if (next !== current) {
            log.push({ pass, rule: rule.name });
            current = next;
            fired = true;
            break; // restart rule scan from highest priority after each firing
          }
        }
      }
      if (!fired) break;
    }

    return { xml: current, log, passes: log.length };
  }

  /**
   * Entropy reduction: if AST depth > depthThreshold, flatten all leaves
   * into a single <route><or>…</or></route> at depth 2.
   * Returns { xml, reduced, original_depth? }
   */
  entropyReduce(xml, depthThreshold = 3) {
    const depth = this._measureDepth(xml);
    if (depth <= depthThreshold) return { xml, reduced: false };

    const leaves = [...xml.matchAll(/<leaf[^>]*\/>/g)].map(m => m[0]);
    if (leaves.length === 0) return { xml, reduced: false };

    const flat = `<route>\n  <or>\n    ${leaves.join('\n    ')}\n  </or>\n</route>`;
    return { xml: flat, reduced: true, original_depth: depth };
  }

  /**
   * Measure the maximum nesting depth of the XML tree.
   * Self-closing tags do not increase depth.
   */
  _measureDepth(xml) {
    let depth = 0;
    let max = 0;
    let i = 0;

    while (i < xml.length) {
      if (xml[i] !== '<') { i++; continue; }

      const next = xml[i + 1];

      if (next === '/') {
        // Closing tag — decrease depth
        depth--;
        const end = xml.indexOf('>', i);
        i = end !== -1 ? end + 1 : i + 1;
      } else if (next === '!' || next === '?') {
        // Comment / processing instruction — skip
        const end = xml.indexOf('>', i);
        i = end !== -1 ? end + 1 : i + 1;
      } else {
        // Opening or self-closing tag
        const end = xml.indexOf('>', i);
        if (end === -1) { i++; continue; }

        // Self-closing if the character before '>' (ignoring whitespace) is '/'
        const tagContent = xml.slice(i, end); // excludes the '>'
        const isSelfClosing = tagContent.trimEnd().endsWith('/');

        if (!isSelfClosing) {
          depth++;
          if (depth > max) max = depth;
        }
        i = end + 1;
      }
    }

    return max;
  }
}

export { RULES };
