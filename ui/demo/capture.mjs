// Screenshot tool for the demo: drives a real (headless) Chrome through PesoWeb's own login page and the AI dashboard, and saves PNGs.
//   node ui/demo/capture.mjs <shots.json> <out dir>
// Uses only Node 22 built-ins (global WebSocket and fetch) and the Chrome that is already installed: nothing to download.
// shots.json: { "base": "http://127.0.0.1:4200", "size": [1440, 900], "steps": [ ...steps ] } where a step is one of
//   { "login": {"email": "...", "password": "..."}, "shot": "01-login-page" }   (the login page is shot before typing, so no secrets appear)
//   { "go": "/settings/warehouses", "wait": 2500, "shot": "05-branches", "caption": "...", "height": 1100 }
//   { "go": "http://127.0.0.1:8080/ui/dashboard/index.html", ... }   (an absolute URL is used as is)
//   { "click": "css selector", "wait": 800, "shot": "..." }
//   { "logout": true }
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const [shotsFile, outDir] = process.argv.slice(2);
if (!shotsFile || !outDir) { console.error('usage: node capture.mjs <shots.json> <out dir>'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(shotsFile, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const CHROME = cfg.browser || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9333;
const [W, H] = cfg.size || [1440, 900];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'mc-capture-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, `--window-size=${W},${H}`,
  '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });

async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* browser still starting */ }
    await sleep(500);
  }
  throw new Error('could not reach Chrome');
}

const ws = new WebSocket(await connect());
await new Promise((r) => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
ws.addEventListener('message', (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const mid = ++id;
  pending.set(mid, (msg) => (msg.error ? reject(new Error(`${method}: ${msg.error.message}`)) : resolve(msg.result)));
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  return r.result ? r.result.value : undefined;
};
async function waitFor(expr, ms = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await evaluate(expr)) return true; await sleep(300); }
  return false;
}
async function setViewport(height) {
  await send('Emulation.setDeviceMetricsOverride', { width: W, height, deviceScaleFactor: 1, mobile: false });
}
async function go(url) {
  const full = /^(https?|file):/.test(url) ? url : cfg.base + '/#' + url;          // PesoWeb uses hash routes: /#/dashboard
  await send('Page.navigate', { url: full });
  await waitFor('document.readyState === "complete"');
}
async function shot(name, height) {
  await setViewport(height || H);
  await sleep(400);
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(outDir, `${name}.png`), Buffer.from(data, 'base64'));
  console.log('saved', name);
}


const byText = (text) => `(function(){var r=document.evaluate('//*[contains(text(), ' + JSON.stringify(${JSON.stringify(text)}) + ')]',document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;return r;})()`;

await send('Page.enable');
await send('Runtime.enable');
await setViewport(H);
const manifest = [];

for (const step of cfg.steps) {
  if (step.logout) {
    await go('/auth/login');
    await evaluate('localStorage.clear(); sessionStorage.clear(); true');
  }
  if (step.login) {
    await go('/auth/login');
    await evaluate('localStorage.clear(); sessionStorage.clear(); true');
    await go('/auth/login');
    await waitFor('!!document.querySelector("#email")');
    await sleep(1200);
    if (step.shot) { await shot(step.shot, step.height); manifest.push({ name: step.shot, caption: step.caption || '', url: '/auth/login' }); }
    const fill = (sel, val) => `(function(){var e=document.querySelector(${JSON.stringify(sel)});var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;s.call(e,${JSON.stringify(val)});e.dispatchEvent(new Event("input",{bubbles:true}));return true;})()`;
    await evaluate(fill('#email', step.login.email));
    await evaluate(fill('#password', step.login.password));
    await evaluate('document.querySelector("#frm button[type=submit]").click(); true');
    const ok = await waitFor('!location.pathname.startsWith("/auth/login")', 25000);
    if (!ok) throw new Error('login did not complete for ' + step.login.email);
    await sleep(2500);
    continue;
  }
  if (step.go) await go(step.go);
  if (step.click) {
    await waitFor(`!!document.querySelector(${JSON.stringify(step.click)})`, 8000);
    await evaluate(`document.querySelector(${JSON.stringify(step.click)}).click(); true`);
  }
  // PesoWeb pages (served from cfg.base) show a spinner until Angular has rendered; wait for the real content, not a fixed time.
  const pesoPage = step.go && !/^(https?|file):/.test(step.go);
  const readyExpr = step.waitFor || (pesoPage ? '!!document.querySelector(".main-content")' : null);
  if (readyExpr) {
    const ok = await waitFor(readyExpr, 60000);
    if (!ok) console.warn('WARNING: content not ready for', step.shot || step.go);
  }
  if (step.clickText) {
    const ok = await waitFor(`!!${byText(step.clickText)}`, 10000);
    if (!ok) console.warn('WARNING: text not found to click:', step.clickText);
    await evaluate(`(function(){var e=${byText(step.clickText)};if(e){e.click();return true}return false})()`);
    await sleep(900);
  }
  if (step.scrollToText) {
    await evaluate(`(function(){var e=${byText(step.scrollToText)};if(e){e.scrollIntoView({block:"start"});return true}return false})()`);
    await sleep(500);
  }
  // hide a floating widget that is not part of the page being shown (for example the offline-hub status chip)
  if (step.hideText) {
    await evaluate(`(function(){var e=${byText(step.hideText)};while(e&&e!==document.body){var s=getComputedStyle(e);if(s.position==="fixed"||s.position==="absolute"){e.style.display="none";return true}e=e.parentElement}return false})()`);
  }
  if (step.wait) await sleep(step.wait);
  if (step.eval) console.log('eval:', JSON.stringify(await evaluate(step.eval)));
  if (step.shot) {
    await shot(step.shot, step.height);
    manifest.push({ name: step.shot, caption: step.caption || '', url: step.go || '' });
  }
}
fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
ws.close();
chrome.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* the profile may still be locked; the OS temp cleaner takes it */ }
process.exit(0);
