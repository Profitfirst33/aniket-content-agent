// Screenshot a real web page (GitHub repo, product site, docs) for a demo card, using the content-agent Chrome.
// usage: node capture.mjs <url> <out.png>
import { chromium } from '/usr/lib/node_modules/@playwright/mcp/node_modules/playwright-core/index.mjs';
const [url, out] = process.argv.slice(2);
const b = await chromium.connectOverCDP('http://127.0.0.1:9225');
const p = await b.contexts()[0].newPage();
try {
  await p.setViewportSize({ width: 1280, height: 860 });
  await p.goto(url, { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
  await p.waitForTimeout(2000);
  await p.screenshot({ path: out });
  console.log('saved', out, p.url());
} finally { await p.close(); process.exit(0); }
