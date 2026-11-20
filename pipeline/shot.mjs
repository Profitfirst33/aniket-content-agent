// Screenshot the open Google Flow tab of the content-agent Chrome. usage: node shot.mjs <out.png>
import { chromium } from '/usr/lib/node_modules/@playwright/mcp/node_modules/playwright-core/index.mjs';
const b = await chromium.connectOverCDP('http://127.0.0.1:9225');
const pages = b.contexts().flatMap(c => c.pages());
const p = pages.find(x => x.url().includes('flow.google.com')) || pages[0];
await p.screenshot({ path: process.argv[2] });
console.log('saved', p.url());
process.exit(0);
