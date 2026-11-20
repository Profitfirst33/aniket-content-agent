// Capture a real web page for a deck card and locate text on it, using the content-agent Chrome.
// usage: node grab.mjs <url> <name> [--find "phrase one|phrase two"]
// Writes edit/assets/img/<name>.jpg (the page top, 1280 css px wide at 2x, at most 5000 css px tall) and
// edit/assets/img/<name>.json {url, title, height, lines: [{t, x, y, w, h}], found: {phrase: {x, y, w, h, lines}}}
// in css px of the page. Run from the job folder. `lines` lists the readable text blocks so marks can be picked;
// --find locates exact phrases (case-insensitive) so marks land on the spoken line.
import { chromium } from '/usr/lib/node_modules/@playwright/mcp/node_modules/playwright-core/index.mjs';
import fs from 'fs';

const args = process.argv.slice(2);
const fi = args.indexOf('--find');
const finds = fi >= 0 ? args[fi + 1].split('|').map(s => s.trim()).filter(Boolean) : [];
const [url, name] = args.filter((a, i) => i !== fi && i !== fi + 1);
if (!url || !/^[a-z0-9_-]+$/i.test(name || '')) { console.log('usage: node grab.mjs <url> <name> [--find "a|b"]'); process.exit(1); }
const dir = 'edit/assets/img';
fs.mkdirSync(dir, { recursive: true });
const MAXH = 5000;

const b = await chromium.connectOverCDP('http://127.0.0.1:9225');
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, locale: 'en-US' });
const p = await ctx.newPage();
try {
  await p.goto(url, { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
  await p.waitForTimeout(1500);
  // close cookie / consent banners
  for (const label of ['Reject all', 'Decline', 'Reject', 'Accept all', 'Accept', 'I agree', 'Got it', 'OK']) {
    const btn = p.getByRole('button', { name: label, exact: true });
    if (await btn.count().catch(() => 0)) { await btn.first().click({ timeout: 1500 }).catch(() => {}); await p.waitForTimeout(500); break; }
  }
  // scroll through once so lazy images load, then back to the top
  await p.evaluate(async (maxh) => {
    for (let y = 0; y < Math.min(document.body.scrollHeight, maxh); y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); }
    window.scrollTo(0, 0);
  }, MAXH);
  await p.addStyleTag({ content: 'html{scrollbar-width:none} ::-webkit-scrollbar{display:none}' }).catch(() => {});
  await p.waitForTimeout(800);
  const info = await p.evaluate(({ finds, maxh }) => {
    const vis = el => { const s = getComputedStyle(el); return s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0; };
    const r2 = r => ({ x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) });
    const lines = [];
    for (const el of document.querySelectorAll('h1,h2,h3,h4,p,li,td,th,code,pre,a,button,span,dt,dd,figcaption,blockquote,strong')) {
      const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
      if (!t || t.length < 3 || t.length > 140 || !vis(el)) continue;
      if ([...el.children].some(c => (c.innerText || '').replace(/\s+/g, ' ').trim() === t)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8 || r.top + scrollY > maxh || r.left < -5 || r.right > 1290) continue;
      lines.push({ t, ...r2(r) });
    }
    lines.sort((a, b) => a.y - b.y || a.x - b.x);
    const seen = new Set();
    const uniq = lines.filter(l => { const k = l.t + '|' + l.y; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 300);
    // exact phrase search over text nodes (handles phrases split over inline tags inside one block)
    const found = {};
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = []; let full = '';
    while (walker.nextNode()) { const n = walker.currentNode; if (!n.parentElement || !vis(n.parentElement)) continue; nodes.push([n, full.length]); full += n.data; }
    const norm = full.toLowerCase();
    const at = pos => { let lo = 0, hi = nodes.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (nodes[m][1] <= pos) lo = m; else hi = m - 1; } return nodes[lo]; };
    for (const ph of finds) {
      const want = ph.toLowerCase();
      let from = 0;
      while (true) {
        const i = norm.indexOf(want, from);
        if (i < 0) break;
        from = i + 1;
        const [n1, o1] = at(i), [n2, o2] = at(i + want.length - 1);
        const rg = document.createRange();
        rg.setStart(n1, i - o1); rg.setEnd(n2, i + want.length - o2);
        const rects = [...rg.getClientRects()].filter(r => r.width > 2 && r.height > 4);
        if (!rects.length) continue;
        const u = rg.getBoundingClientRect();
        if (u.top + scrollY > maxh || u.left < 0 || u.right > 1285) continue;
        // merge rects of the same text line
        const ls = [];
        for (const r of rects) { const l = ls.find(q => Math.abs(q.top - r.top) < r.height * .5); if (l) { l.left = Math.min(l.left, r.left); l.right = Math.max(l.right, r.right); l.bottom = Math.max(l.bottom, r.bottom); } else ls.push({ left: r.left, right: r.right, top: r.top, bottom: r.bottom }); }
        // the text block (paragraph, list item, cell) the phrase sits in, so a close-up never cuts its lines
        let blk = n1.parentElement;
        while (blk && blk !== document.body && !/^(block|list-item|table-cell|flex|grid)$/.test(getComputedStyle(blk).display)) blk = blk.parentElement;
        const br = (blk || n1.parentElement).getBoundingClientRect();
        found[ph] = { ...r2(u), block: r2(br), lines: ls.map(l => r2({ left: l.left, top: l.top, width: l.right - l.left, height: l.bottom - l.top })) };
        break;
      }
    }
    return { title: document.title, height: Math.min(document.documentElement.scrollHeight, maxh), lines: uniq, found };
  }, { finds, maxh: MAXH });
  const shotH = Math.max(900, info.height);
  await p.screenshot({ path: `${dir}/${name}.jpg`, type: 'jpeg', quality: 86, fullPage: true, clip: { x: 0, y: 0, width: 1280, height: shotH } });
  info.height = shotH;
  fs.writeFileSync(`${dir}/${name}.json`, JSON.stringify({ url: p.url(), ...info }, null, 1));
  const miss = finds.filter(f => !info.found[f]);
  console.log(`saved ${dir}/${name}.jpg (${info.height}px tall, ${info.lines.length} text lines) title: ${info.title}`);
  if (finds.length) console.log(`found ${finds.length - miss.length}/${finds.length}` + (miss.length ? `; not on page: ${JSON.stringify(miss)}` : ''));
} finally { await ctx.close().catch(() => {}); process.exit(0); }
