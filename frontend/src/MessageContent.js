import { createElement } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

function restoreTableRows(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) {
    return line;
  }

  // Some model answers flatten a complete table into one line: "... | | ...".
  // Repair only when a header, delimiter row, and equally wide data rows agree.
  const rows = trimmed.split(/\|[ \t]+\|/);
  if (rows.length < 3) {
    return line;
  }
  const cells = rows.map((row) =>
    row.replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim()),
  );
  const columns = cells[0].length;
  if (
    columns < 2 ||
    !cells.every((row) => row.length === columns) ||
    !cells[1].every((cell) => /^:?-{3,}:?$/.test(cell))
  ) {
    return line;
  }
  return cells.map((row) => `| ${row.join(" | ")} |`).join("\n");
}

export function normalizeMarkdown(content) {
  let fence = null;
  return String(content ?? "").replace(/\r\n?/g, "\n").split("\n").map((line) => {
    const match = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line);
    if (fence) {
      if (match && match[1][0] === fence.character && match[1].length >= fence.length && !match[2].trim()) {
        fence = null;
      }
      return line;
    }
    if (match) {
      fence = { character: match[1][0], length: match[1].length };
      return line;
    }
    return /^(?: {4}|\t)/.test(line) ? line : restoreTableRows(line);
  }).join("\n");
}

function ScrollableTable({ children }) {
  return createElement(
    "div",
    { className: "markdown-table", role: "region", "aria-label": "Answer table", tabIndex: 0 },
    createElement("table", null, children),
  );
}

const components = { table: ScrollableTable };
const remarkPlugins = [remarkGfm];

export default function MessageContent({ content }) {
  return createElement(
    "div",
    { className: "message-content" },
    createElement(Markdown, { remarkPlugins, components, skipHtml: true }, normalizeMarkdown(content)),
  );
}
