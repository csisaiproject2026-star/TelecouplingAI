/**
 * Interactive Playwright runner.
 * Opens ONE browser window and stays open.
 * Reads commands from cmd.json every 500ms, executes them, then clears the file.
 *
 * Supported commands (write to cmd.json):
 *   { "action": "goto",    "url": "http://..." }
 *   { "action": "newChat" }
 *   { "action": "upload",  "files": ["path1", "path2", ...] }
 *   { "action": "send",    "text": "message text" }
 *   { "action": "waitDone" }   — polls for .bg-green-50 up to 15 min
 *   { "action": "screenshot", "name": "label" }
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

delete process.env.http_proxy; delete process.env.HTTP_PROXY;
delete process.env.https_proxy; delete process.env.HTTPS_PROXY;
process.env.no_proxy = '*'; process.env.NO_PROXY = '*';

const CMD_FILE = path.join(__dirname, 'cmd.json');
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'demo_screenshots');
if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

let browser, page;

async function execute(cmd) {
  console.log('[CMD]', JSON.stringify(cmd));
  try {
    if (cmd.action === 'goto') {
      await page.goto(cmd.url, { waitUntil: 'networkidle', timeout: 30000 });
      console.log('[OK] goto', cmd.url);

    } else if (cmd.action === 'newChat') {
      const btn = await page.waitForSelector('button:has-text("New Chat")', { timeout: 10000 });
      await btn.click();
      await page.waitForTimeout(800);
      console.log('[OK] new chat');

    } else if (cmd.action === 'upload') {
      const existing = cmd.files.filter(f => fs.existsSync(f));
      if (existing.length === 0) { console.log('[WARN] no files found'); return; }
      await page.setInputFiles('input[type="file"]', existing);
      await page.waitForTimeout(800);
      console.log('[OK] uploaded', existing.length, 'file(s)');

    } else if (cmd.action === 'send') {
      const input = await page.waitForSelector('input[placeholder="Enter a prompt here"]', { timeout: 10000 });
      await input.click();
      await input.fill(cmd.text);
      await page.waitForTimeout(300);
      await input.press('Enter');
      await page.waitForTimeout(800);
      console.log('[OK] sent message');

    } else if (cmd.action === 'fill') {
      // Fill the input box WITHOUT sending — user presses Enter manually
      const input = await page.waitForSelector('input[placeholder="Enter a prompt here"]', { timeout: 10000 });
      await input.click();
      await input.fill(cmd.text);
      console.log('[OK] prompt filled (not sent)');

    } else if (cmd.action === 'waitDone') {
      const timeoutMs = (cmd.timeoutMin || 15) * 60 * 1000;
      const start = Date.now();
      while (Date.now() - start < timeoutMs) {
        if (await page.$('.bg-green-50')) { console.log('[OK] tool done', Math.round((Date.now()-start)/1000)+'s'); return; }
        process.stdout.write('.');
        await page.waitForTimeout(3000);
      }
      console.log('\n[WARN] waitDone timeout');

    } else if (cmd.action === 'screenshot') {
      const name = cmd.name || ('shot_' + Date.now());
      const file = path.join(SCREENSHOTS_DIR, name + '.png');
      await page.screenshot({ path: file, fullPage: false });
      console.log('[OK] screenshot', file);

    } else {
      console.log('[WARN] unknown action:', cmd.action);
    }
  } catch (e) {
    console.error('[ERR]', e.message);
  }
}

(async () => {
  browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized', '--no-proxy-server', '--proxy-bypass-list=*'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  page = await ctx.newPage();

  await page.goto('http://34.42.83.50', { waitUntil: 'networkidle', timeout: 30000 });
  console.log('[READY] Browser open at http://34.42.83.50 — polling cmd.json');

  // Poll cmd.json
  while (true) {
    if (fs.existsSync(CMD_FILE)) {
      try {
        const raw = fs.readFileSync(CMD_FILE, 'utf-8').trim();
        if (raw) {
          fs.writeFileSync(CMD_FILE, '', 'utf-8'); // clear immediately
          const cmd = JSON.parse(raw);
          await execute(cmd);
          fs.writeFileSync(CMD_FILE + '.done', JSON.stringify({ ok: true, cmd: cmd.action }), 'utf-8');
        }
      } catch (e) {
        console.error('[PARSE ERR]', e.message);
        fs.writeFileSync(CMD_FILE, '', 'utf-8');
      }
    }
    await page.waitForTimeout(500);
  }
})();
