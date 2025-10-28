// render-note.js
// Env: NOTE_WIDTH (pt), NOTE_HEIGHT (pt)
// Usage: NOTE_WIDTH=300 NOTE_HEIGHT=180 node render-note.js < note.md > note.pdf

const fs = require("fs");
const puppeteer = require("puppeteer");
const katex = require("katex");
const { marked } = require("marked");

const katexCSS = fs.readFileSync(require.resolve("katex/dist/katex.min.css"), "utf8");

function renderMath(md) {
  // $$...$$ (display)
  md = md.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) =>
    `\n<div class="katex-display">${katex.renderToString(expr, { displayMode: true, throwOnError: false })}</div>\n`
  );
  // $...$ (inline) — простая версия
  md = md.replace(/\$([^$]+?)\$/g, (_, expr) =>
    `<span class="katex-inline">${katex.renderToString(expr, { displayMode: false, throwOnError: false })}</span>`
  );
  return md;
}

function buildHTML(body, widthPx) {
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${katexCSS}
:root { color-scheme: light dark; --fs:16px; --lh:1.25; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }

#wrap {
  width: ${widthPx}px;
  margin: 0;
  transform-origin: top left;
}

body {
  font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Ubuntu,"Helvetica Neue",Arial,sans-serif;
  font-size: var(--fs);
  line-height: var(--lh);
  color: #111;
  hyphens: auto;
  overflow-wrap: anywhere;
}

body > * { width: 100%; max-width: none; }
img, svg, table, pre, code { max-width: 100%; }
table { width: 100%; border-collapse: collapse; }

h1,h2,h3 { margin: 0 0 0px; line-height: 1.25; }
p { margin: 0 0 0px; }
.katex-display { margin: 0px 0 0px; }
ul, ol { margin: 0 0 0px; padding-left: 1rem; }
li { margin: 0; }
</style>
</head>
<body>
  <div id="wrap">${body}</div>
</body>
</html>`;
}

async function measure(page) {
  return page.evaluate(() => {
    const w = document.getElementById('wrap');
    const r = w.getBoundingClientRect();
    return Math.max(w.scrollHeight, r.height);
  });
}

(async () => {
  // 1) read input markdown and convert to HTML with math
  const chunks = [];
  for await (const ch of process.stdin) chunks.push(ch);
  const md = Buffer.concat(chunks).toString("utf8").trim();

  const withMath = renderMath(md);
  const htmlBody = marked.parse(withMath, { mangle: false, headerIds: false });

  const ptToPx = (pt) => Math.round((pt * 96) / 72);
  const widthPx  = ptToPx(Number(process.env.NOTE_WIDTH  || 420));
  const heightPx = ptToPx(Number(process.env.NOTE_HEIGHT || 250));

  // 2) launch puppeteer and render HTML
  const browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: widthPx, height: 100, deviceScaleFactor: 1 });
  await page.setContent(buildHTML(htmlBody, widthPx), { waitUntil: "networkidle0" });
  await page.emulateMediaType("screen");
  await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready; });

  // 3) adjust font size to fit height using binary search
  const BASE = Number(process.env.NOTE_BASE_FONT_PX || 16);
  const MINF = Number(process.env.NOTE_MIN_FONT_PX  || 6);
  let low = MINF, high = BASE, best = BASE;

  // start with BASE
  await page.evaluate((px) => document.documentElement.style.setProperty('--fs', px + 'px'), BASE);
  let h = await measure(page);

  if (h > heightPx) {
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      await page.evaluate((px) => document.documentElement.style.setProperty('--fs', px + 'px'), mid);
      h = await measure(page);
      if (h <= heightPx) { best = mid; low = mid + 1; } else { high = mid - 1; }
    }
    await page.evaluate((px) => document.documentElement.style.setProperty('--fs', px + 'px'), best);
    h = await measure(page);
  }

  // 4) if still doesn't fit, scale down the whole content
  //    but keep final width equal to NOTE_WIDTH
  if (h > heightPx) {
    const s = heightPx / h;                       // 0 < s < 1
    const cssWidthForLayout = Math.round(widthPx / s);
    await page.setViewport({ width: cssWidthForLayout, height: 100, deviceScaleFactor: 1 });
    await page.evaluate(({ s, w }) => {
      const wrap = document.getElementById('wrap');
      wrap.style.width = w + 'px';
      wrap.style.transform = `scale(${s})`;
    }, { s, w: cssWidthForLayout });
  }

  // 5) export to PDF of exact size
  const pdf = await page.pdf({
    width:  `${widthPx}px`,
    height: `${heightPx}px`,
    margin: { top: '0px', right: '0px', bottom: '0px', left: '0px' },
    printBackground: true,
    pageRanges: "1"
  });

  await browser.close();
  process.stdout.write(pdf);
})().catch((e) => { console.error(e); process.exit(1); });


