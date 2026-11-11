import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve,dirname} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(resolve(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const work=resolve(root,'.work/expression-alignment-20261005'),qa=resolve(work,'viewer-qa');
await mkdir(qa,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true}),checks=[];
try {
  for(const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:1050},deviceScaleFactor:1});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pathToFileURL(resolve(work,'expression-alignment.html')).href);
    await page.locator('#items tr').first().waitFor();
    if(await page.locator('#seed option').count()!==3)throw Error('source count');
    if(await page.locator('#items tr').count()!==18)throw Error('word tests');
    await page.locator('#scope').selectOption('cross');
    await page.locator('#seed').selectOption('251');
    await page.locator('#modality').selectOption('words');
    if(await page.locator('#items tr').count()!==10)throw Error('visual tests');
    await page.locator('#condition').selectOption('frozen');
    if(await page.locator('#items tr').count()!==5)throw Error('nonlearning tests');
    await page.locator('#reader').selectOption('developmental-s163-vision');
    if(await page.locator('#latency tr').count()!==15)throw Error('latency controls');
    if(!(await page.locator('#latency').innerText()).includes('530'))throw Error('window times missing');
    await page.locator('#condition').selectOption('cycle1');
    await page.locator('#scope').selectOption('all');
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('page overflow '+width);
    await page.screenshot({path:resolve(qa,`viewer-${width}.png`)});
    if(errors.length)throw Error(errors.join('\n'));
    checks.push({width,errors,overflow:false,scope_switch:true,source_switch:true,modality_switch:true,latency_rows:15});
    await page.close();
  }
  await writeFile(resolve(qa,'checks.json'),JSON.stringify(checks,null,2));
  console.log(JSON.stringify(checks));
} finally {await browser.close();}
