import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(path.join(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const work=path.join(root,'.work/ocean-causality-20261003');
const edge='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const browser=await chromium.launch({headless:true,...(fs.existsSync(edge)?{executablePath:edge}:{})});
try {
  const outcomes=[];
  for (const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:900}});const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(work,'views/g0-core.html')).href);
    await page.locator('#time').fill('220');
    await page.locator('#time').dispatchEvent('input');
    await page.locator('canvas').click({position:{x:100,y:100}});
    await page.locator('#play').click();
    await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('221'));
    await page.locator('#play').click();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    if (errors.length || overflow)throw new Error(JSON.stringify({width,errors,overflow}));
    await page.screenshot({path:path.join(work,`views/view-${width}.png`),fullPage:true});
    outcomes.push({width,status:await page.locator('#status').innerText(),selected:await page.locator('#detail').innerText(),errors,overflow});
    await page.close();
  }
  fs.writeFileSync(path.join(work,'views/ui-check.json'),JSON.stringify(outcomes,null,2));
  console.log(JSON.stringify(outcomes));
} finally { await browser.close(); }
