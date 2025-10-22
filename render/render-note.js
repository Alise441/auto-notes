// render/render-note.js
// Render Markdown with $...$/$$...$$ math to a vector PDF using KaTeX + Puppeteer.
// Env knobs: NOTE_WIDTH (px), NOTE_PAD (px, default 8), NOTE_DPR (default 2)

const fs = require("fs");
const katex = require("katex");
const { marked } = require("marked");
const puppeteer = require("puppeteer");

// inline KaTeX CSS
const katexCSS = fs.readFileSync(require.resolve("katex/dist/katex.min.css"), "utf8");

// 1) preprocess: replace math delimiters with KaTeX HTML (no-throw)
function renderMath(md) {
  // display $$...$$
  md = md.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
    const html = katex.renderToString(expr, { displayMode: true, throwOnError: false });
    return `\n<div class="katex-display">${html}</div>\n`;
  });
  // inline $...$
  md = md.replace(/\$([^$]+?)\$/g, (_, expr) => {
    const html = katex.renderToString(expr, { displayMode: false, throwOnError: false });
    return `<span class="katex-inline">${html}</span>`;
  });
  return md;
}

function wrapHTML(body, padPx) {
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${katexCSS}
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: ${padPx}px;
  font: 16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Ubuntu,"Helvetica Neue",Arial,sans-serif;
  color: #111;
}
body {
  text-align: left;
  max-width: 100%;
  margin: 0;
}
h1,h2,h3 { margin: 0 0 12px; line-height: 1.25; }
p { margin: 0 0 8px; }
.katex-display { margin: 10px 0 12px; }
hr { border: 0; border-top: 1px solid #e5e5e5; margin: 12px 0; }
.section-title { font-weight: 600; margin: 12px 0 6px; }
.small { opacity: .8; }
</style>
</head>
<body>
${body}
</body>
</html>`;
}

async function main() {
  const chunks = [];
  for await (const ch of process.stdin) chunks.push(ch);
  const md = Buffer.concat(chunks).toString("utf8").trim();

  const withMath = renderMath(md);
  const htmlBody = marked.parse(withMath, { mangle: false, headerIds: false });
  const widthPx = Number(process.env.NOTE_WIDTH || 1000);
  const padPx = Number(process.env.NOTE_PAD || 8);
  const dpr = Number(process.env.NOTE_DPR || 2);

  const html = wrapHTML(htmlBody, padPx);

  const browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: widthPx, height: 10, deviceScaleFactor: dpr });
  await page.setContent(html, { waitUntil: "networkidle0" });

  const heightPx = await page.evaluate(() => Math.ceil(document.body.getBoundingClientRect().height));

  const pdf = await page.pdf({
    width: `${widthPx}px`,
    height: `${heightPx}px`,
    printBackground: true,
    pageRanges: "1",
    preferCSSPageSize: true
  });

  await browser.close();
  process.stdout.write(pdf);
}

main().catch((e) => { console.error(e); process.exit(1); });
