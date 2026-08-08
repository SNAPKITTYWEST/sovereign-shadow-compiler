// ast_parser.mjs
// XML boolean AST parser for sovereign routing expressions
// Handles: <route>, <and>, <or>, <not>, <leaf op="" weight="" valid=""/>
// No external XML parser — pure regex-based recursive descent

const BOOLEAN_TAGS = new Set(['and', 'or', 'not', 'route']);
const VALID_OPS = ['ADD', 'MUL', 'XOR', 'LOOP', 'MEMCPY', 'MEMSET', 'STRCMP', 'HELLO'];

// Parse a <leaf .../> element attributes
function parseLeafAttrs(tag) {
  const opMatch = tag.match(/op="([^"]+)"/);
  const weightMatch = tag.match(/weight="([^"]+)"/);
  const validMatch = tag.match(/valid="([^"]+)"/);
  return {
    op: opMatch ? opMatch[1].toUpperCase() : null,
    weight: weightMatch ? parseFloat(weightMatch[1]) : 0.05,
    valid: validMatch ? validMatch[1] === 'true' : false,
  };
}

// Find the next open tag <tagName with valid boundary char (>, space, /, newline, tab)
function findNextOpenTag(xml, tagName, start) {
  let i = start;
  const needle = '<' + tagName;
  while (i < xml.length) {
    const idx = xml.indexOf(needle, i);
    if (idx === -1) return -1;
    const charAfter = xml[idx + 1 + tagName.length];
    if (
      charAfter === '>' ||
      charAfter === ' ' ||
      charAfter === '\t' ||
      charAfter === '\n' ||
      charAfter === '/' ||
      charAfter === undefined
    ) {
      return idx;
    }
    i = idx + 1;
  }
  return -1;
}

// Extract direct children tags from an XML string (non-recursive, one level deep)
// Returns array of { tag, content, selfClosing, raw }
function extractChildren(xml) {
  const children = [];
  let i = 0;

  while (i < xml.length) {
    // Skip to next '<'
    while (i < xml.length && xml[i] !== '<') i++;
    if (i >= xml.length) break;

    // Skip HTML comments
    if (xml.slice(i, i + 4) === '<!--') {
      const end = xml.indexOf('-->', i);
      i = end === -1 ? xml.length : end + 3;
      continue;
    }

    // Skip closing tags
    if (xml[i + 1] === '/') {
      const end = xml.indexOf('>', i);
      i = end === -1 ? xml.length : end + 1;
      continue;
    }

    // Skip processing instructions
    if (xml[i + 1] === '?') {
      const end = xml.indexOf('?>', i);
      i = end === -1 ? xml.length : end + 2;
      continue;
    }

    const tagStart = i;
    const gtIdx = xml.indexOf('>', i);
    if (gtIdx === -1) { i++; continue; }

    // Everything between < and >
    const tagInner = xml.slice(i + 1, gtIdx);

    // Self-closing: ends with /
    if (tagInner.endsWith('/')) {
      const tagName = tagInner.split(/[\s/]/)[0];
      children.push({
        tag: tagName,
        content: '',
        selfClosing: true,
        raw: xml.slice(tagStart, gtIdx + 1),
      });
      i = gtIdx + 1;
      continue;
    }

    // Paired tag — find matching close, handling nesting of same tag
    const tagName = tagInner.split(/\s/)[0];
    const closeTag = '</' + tagName + '>';
    let depth = 1;
    let j = gtIdx + 1;

    while (j < xml.length && depth > 0) {
      const nextOpen = findNextOpenTag(xml, tagName, j);
      const nextClose = xml.indexOf(closeTag, j);

      if (nextClose === -1) {
        // Malformed — no matching close, skip this tag
        j = xml.length;
        break;
      }

      if (nextOpen !== -1 && nextOpen < nextClose) {
        depth++;
        j = nextOpen + 1;
      } else {
        depth--;
        if (depth === 0) {
          const closeEnd = nextClose + closeTag.length;
          children.push({
            tag: tagName,
            content: xml.slice(gtIdx + 1, nextClose),
            selfClosing: false,
            raw: xml.slice(tagStart, closeEnd),
          });
          i = closeEnd;
        } else {
          j = nextClose + 1;
        }
      }
    }

    if (depth > 0) {
      // Malformed paired tag, advance past the open tag
      i = gtIdx + 1;
    }
  }

  return children;
}

// Recursive AST evaluator
// counters = { nodeCount: 0, maxDepth: 0 } — mutated in place for final totals
function evalNode(xml, currentDepth = 0, counters = { nodeCount: 0, maxDepth: 0 }) {
  counters.nodeCount++;
  if (currentDepth > counters.maxDepth) counters.maxDepth = currentDepth;

  const trimmed = xml.trim();

  // --- Self-closing leaf: <leaf op="..." weight="..." valid="..."/> ---
  if (/^<leaf\s[^>]*\/>$/.test(trimmed)) {
    const attrs = parseLeafAttrs(trimmed);
    if (!attrs.op || !VALID_OPS.includes(attrs.op)) {
      return { op: 'ADD', weight: attrs.weight, valid: false, depth: currentDepth, reason: `unknown op: ${attrs.op}` };
    }
    return { op: attrs.op, weight: attrs.weight, valid: attrs.valid, depth: currentDepth };
  }

  // --- Determine outer tag ---
  const tagMatch = trimmed.match(/^<(\w+)[\s>]/);
  if (!tagMatch) {
    return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: 'malformed tag' };
  }
  const tagName = tagMatch[1].toLowerCase();

  // Get inner content between open and close tag
  const openTagEnd = trimmed.indexOf('>');
  const closeTag = '</' + tagName + '>';
  const closeTagIdx = trimmed.lastIndexOf(closeTag);
  if (openTagEnd === -1 || closeTagIdx === -1) {
    return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: `malformed ${tagName} tag` };
  }
  const inner = trimmed.slice(openTagEnd + 1, closeTagIdx);

  // --- <leaf op="..."></leaf> (paired, unusual but handle) ---
  if (tagName === 'leaf') {
    const attrs = parseLeafAttrs(trimmed);
    if (!attrs.op || !VALID_OPS.includes(attrs.op)) {
      return { op: 'ADD', weight: attrs.weight, valid: false, depth: currentDepth, reason: `unknown op: ${attrs.op}` };
    }
    return { op: attrs.op, weight: attrs.weight, valid: attrs.valid, depth: currentDepth };
  }

  // --- <route> — evaluate the single root child ---
  if (tagName === 'route') {
    const children = extractChildren(inner);
    if (children.length === 0) {
      return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: 'empty route' };
    }
    return evalNode(children[0].raw, currentDepth + 1, counters);
  }

  // --- <and> — ALL children must be valid; return highest-weight leaf ---
  if (tagName === 'and') {
    const children = extractChildren(inner);
    if (children.length === 0) {
      return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: 'and: no children' };
    }
    let best = null;
    for (const child of children) {
      const result = evalNode(child.raw, currentDepth + 1, counters);
      if (!result.valid) {
        return { op: result.op, weight: result.weight, valid: false, depth: currentDepth, reason: 'and: child invalid' };
      }
      if (!best || result.weight > best.weight) best = result;
    }
    return { ...best, depth: currentDepth };
  }

  // --- <or> — return the FIRST valid child ---
  if (tagName === 'or') {
    const children = extractChildren(inner);
    for (const child of children) {
      const result = evalNode(child.raw, currentDepth + 1, counters);
      if (result.valid) return { ...result, depth: currentDepth };
    }
    return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: 'or: no valid child' };
  }

  // --- <not> — negate validity of its single child ---
  if (tagName === 'not') {
    const children = extractChildren(inner);
    if (children.length === 0) {
      return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: 'not: no child' };
    }
    const result = evalNode(children[0].raw, currentDepth + 1, counters);
    return { ...result, valid: !result.valid, depth: currentDepth };
  }

  return { op: 'ADD', weight: 0, valid: false, depth: currentDepth, reason: `unknown tag: ${tagName}` };
}

// Entry point — strips to <route>...</route>, walks the AST
// Returns { op, weight, valid, ast_depth, node_count, reason? }
export function parseRoutingAST(xml) {
  const routeStart = xml.indexOf('<route');
  if (routeStart === -1) {
    // Allow a bare self-closing leaf as a degenerate case
    const leafTrimmed = xml.trim();
    if (/^<leaf\s[^>]*\/>$/.test(leafTrimmed)) {
      const counters = { nodeCount: 0, maxDepth: 0 };
      const result = evalNode(leafTrimmed, 0, counters);
      return { ...result, ast_depth: counters.maxDepth, node_count: counters.nodeCount };
    }
    return { op: 'ADD', weight: 0, valid: false, ast_depth: 0, node_count: 0, reason: 'no <route> element' };
  }

  // Verify boundary char after '<route' so we don't match '<router>'
  const charAfterRoute = xml[routeStart + 6]; // '<route' is 6 chars
  if (charAfterRoute !== '>' && charAfterRoute !== ' ' && charAfterRoute !== '\t' &&
      charAfterRoute !== '\n' && charAfterRoute !== '/' && charAfterRoute !== undefined) {
    return { op: 'ADD', weight: 0, valid: false, ast_depth: 0, node_count: 0, reason: 'no <route> element' };
  }

  const routeEnd = xml.lastIndexOf('</route>');
  if (routeEnd === -1) {
    return { op: 'ADD', weight: 0, valid: false, ast_depth: 0, node_count: 0, reason: 'unclosed <route>' };
  }
  const routeXml = xml.slice(routeStart, routeEnd + '</route>'.length);

  const counters = { nodeCount: 0, maxDepth: 0 };
  const result = evalNode(routeXml, 0, counters);
  return { ...result, ast_depth: counters.maxDepth, node_count: counters.nodeCount };
}

export { VALID_OPS, BOOLEAN_TAGS };
