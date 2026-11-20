// Read a public reel's caption + likes from its embed page, using the content-agent Chrome. usage: node reel_read.mjs <reel url>
import { chromium } from '/usr/lib/node_modules/@playwright/mcp/node_modules/playwright-core/index.mjs';
const m = process.argv[2].match(/instagram\.com\/(?:p|reel|reels)\/([A-Za-z0-9_-]+)/);
if (!m) { console.log(JSON.stringify({ error: 'not an instagram post/reel link' })); process.exit(1); }
const b = await chromium.connectOverCDP('http://127.0.0.1:9225');
const ctx = b.contexts()[0];
const p = await ctx.newPage();
try {
  await p.goto(`https://www.instagram.com/p/${m[1]}/embed/captioned/`, { waitUntil: 'networkidle', timeout: 45000 });
  const text = await p.evaluate(() => document.body.innerText);
  const author = (text.match(/^\s*([A-Za-z0-9._]+)\s*\n/) || [])[1] || '';
  const likes = (text.match(/([\d,.]+[KM]?) likes/) || [])[1] || '';
  const cap = text.split(/\n/).map(s => s.trim()).filter(Boolean);
  console.log(JSON.stringify({ code: m[1], author, likes, text: cap.join('\n').slice(0, 4000) }));
} finally { await p.close(); process.exit(0); }
