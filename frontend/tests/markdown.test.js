import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import MessageContent, { normalizeMarkdown } from "../src/MessageContent.js";

const render = (content) => renderToStaticMarkup(createElement(MessageContent, { content }));

test("renders the supplied financial answer as a table with all ten observations", () => {
  const answer = readFileSync(new URL("./fixtures/financial-answer.md", import.meta.url), "utf8");
  const html = render(answer);
  assert.equal((html.match(/<table>/g) || []).length, 1);
  assert.equal((html.match(/<tr>/g) || []).length, 11);
  assert.equal((html.match(/<td>/g) || []).length, 30);
  assert.match(html, /<h3>Summary &amp; Recommendations<\/h3>/);
  assert.match(html, /<em>not<\/em>/);
  assert.match(html, /<ul>/);
  assert.match(html, /Answer table/);
});

test("renders headings, nested ordered lists, links, emphasis, quotes and code", () => {
  const html = render("## Results\n\n1. **Revenue** grew *steadily*.\n   1. [Filing](https://example.com)\n\n> Source note\n\n```js\nconst x = 1 < 2;\n```\n\n~~Removed~~ and `inline code`");
  assert.match(html, /<h2>Results<\/h2>/);
  assert.equal((html.match(/<ol>/g) || []).length, 2);
  assert.match(html, /<strong>Revenue<\/strong>/);
  assert.match(html, /<em>steadily<\/em>/);
  assert.match(html, /href="https:\/\/example.com"/);
  assert.match(html, /<blockquote>/);
  assert.match(html, /<pre><code class="language-js">/);
  assert.match(html, /1 &lt; 2/);
  assert.match(html, /<del>Removed<\/del>/);
  assert.match(html, /<code>inline code<\/code>/);
});

test("preserves valid multiline tables, empty cells and aligned columns", () => {
  const markdown = "| Metric | Value |\n| :--- | ---: |\n| Revenue | |\n| Profit | 20 |";
  assert.equal(normalizeMarkdown(markdown), markdown);
  const html = render(markdown);
  assert.equal((html.match(/<tr>/g) || []).length, 3);
  assert.match(html, /text-align:right/);
});

test("repairs collapsed tables without losing escaped pipe characters", () => {
  const html = render("| Label | Value | | --- | --- | | A \\| B | 12 | | C | 34 |");
  assert.equal((html.match(/<tr>/g) || []).length, 3);
  assert.match(html, /A \| B/);
});

test("does not reinterpret ordinary pipes or malformed rows as a table", () => {
  const prose = "Compare A | B and C | D.";
  const malformed = "| A | B | | --- | --- | | only one cell |";
  assert.equal(normalizeMarkdown(prose), prose);
  assert.equal(normalizeMarkdown(malformed), malformed);
  assert.doesNotMatch(render(prose), /<table>/);
});

test("does not repair table-like text inside fenced or indented code", () => {
  const table = "| A | B | | --- | --- | | 1 | 2 |";
  for (const markdown of [`\`\`\`text\n${table}\n\`\`\``, `~~~\n${table}\n~~~`, `    ${table}`]) {
    assert.equal(normalizeMarkdown(markdown), markdown);
    assert.doesNotMatch(render(markdown), /<table>/);
  }
});

test("does not execute raw HTML or unsafe links from model output", () => {
  const html = render('<script>alert(1)</script>\n\n<img src=x onerror="alert(1)">\n\n[Bad](javascript:alert%281%29)');
  assert.doesNotMatch(html, /<script|<img|onerror=|href="javascript:/);
});

test("handles empty answers and normalizes Windows line endings", () => {
  assert.doesNotThrow(() => render(null));
  assert.match(render("### Title\r\n\r\nParagraph"), /<h3>Title<\/h3>/);
});
