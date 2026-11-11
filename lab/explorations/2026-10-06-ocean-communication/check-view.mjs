import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { writeFile } from 'node:fs/promises';
const require = createRequire(resolve('threemind-ui/package.json'));
const { chromium } = require('playwright');
const file = process.argv[2] || '.work/ocean-communication-20261006/replay-scout.html';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const errors = [], results = [];
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({viewport: {width, height: 1000}});
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(pathToFileURL(resolve(file)).href);
    await page.waitForFunction(() => document.querySelector('#case').options.length > 0 && !document.querySelector('#play').disabled);
    await page.locator('#seek').evaluate(e => {e.value = Math.min(25, +e.max); e.dispatchEvent(new Event('input'));});
    await page.locator('#links').uncheck();
    await page.locator('#links').check();
    const before = await page.locator('#seek').inputValue();
    await page.locator('#play').click();
    await page.waitForTimeout(300);
    await page.locator('#play').click();
    const after = await page.locator('#seek').inputValue();
    if (+after <= +before) throw new Error('playback did not advance');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (overflow) throw new Error('horizontal overflow at '+width);
    const download = page.waitForEvent('download');
    await page.locator('#png').click();
    const image = await download;
    await image.saveAs(resolve(`.work/ocean-communication-20261006/view-${width}-canvas.png`));
    await page.screenshot({path: resolve(`.work/ocean-communication-20261006/view-${width}.png`), fullPage: true});
    results.push({width, overflow, playback: true, png: image.suggestedFilename(), status: await page.locator('#status').innerText()});
    await page.close();
  }
  if(errors.length) throw new Error(errors.join('\n'));
  await writeFile(resolve('.work/ocean-communication-20261006/view-verification.json'), JSON.stringify({results, errors}, null, 2));
  console.log(JSON.stringify({results, errors}));
} finally { await browser.close(); }
