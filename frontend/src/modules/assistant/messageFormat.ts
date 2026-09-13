import MarkdownIt from "markdown-it";

// Keep model output as text: raw HTML is escaped and unsafe link protocols are rejected.
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false });
markdown.disable("image");
markdown.renderer.rules.table_open = () => '<div class="assistant-table-scroll" role="region" aria-label="业务数据表" tabindex="0"><table class="assistant-markdown-table">\n';
markdown.renderer.rules.table_close = () => "</table></div>\n";

export function renderBusinessMessage(source: string): string {
  // Newlines, indentation and blank lines define Markdown blocks. Never collapse \s here.
  return markdown.render(source.replace(/\r\n?/g, "\n"));
}

export function buildBusinessReport(source: string): string {
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>农牧业业务报告</title>
<style>body{font:14px/1.7 "Microsoft YaHei",sans-serif;color:#17211c;margin:32px}table{width:100%;border-collapse:collapse;margin:16px 0}th,td{border:1px solid #ccd8d0;padding:8px;text-align:left}th{background:#e9f3ed}p,ul,ol{margin:12px 0}pre{white-space:pre-wrap}h1,h2,h3{page-break-after:avoid}tr{page-break-inside:avoid}</style>
</head><body><h1>农牧业业务报告</h1>${renderBusinessMessage(source)}</body></html>`;
}
