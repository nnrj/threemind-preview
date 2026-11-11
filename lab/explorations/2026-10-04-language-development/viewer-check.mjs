import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {resolve, dirname} from 'node:path';
import {mkdir, writeFile} from 'node:fs/promises';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(resolve(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const work=resolve(root,'.work/language-development-20261004');
const qa=resolve(work,'viewer-qa'); await mkdir(qa,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[];
try {
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});
  const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  await page.goto(pathToFileURL(resolve(work,'language-development.html')).href);
  await page.locator('#table tr').first().waitFor();
  if(await page.locator('#table tr').count()!==40)throw new Error('bounded table');
  await page.locator('#seed').selectOption('37');
  await page.locator('#condition').selectOption('reversed');
  const source=await page.locator('#source').innerText();
  if(!source.includes('s37-reversed'))throw new Error('source selector');
  await page.locator('#seek').evaluate(el=>{el.value='532';el.dispatchEvent(new Event('input'));});
  if(!(await page.locator('#time').innerText()).includes('266.0'))throw new Error('time seeking');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw new Error('viewport overflow '+width);
  await page.screenshot({path:resolve(qa,`viewer-${width}.png`)});
  await page.locator('#base').scrollIntoViewIfNeeded();
  await page.screenshot({path:resolve(qa,`readouts-${width}.png`)});
  await page.locator('#play').click();await page.waitForTimeout(200);await page.locator('#play').click();
  if(Number(await page.locator('#seek').inputValue())<=532)throw new Error('playback');
  const download=page.waitForEvent('download');await page.locator('#download').click();
  const item=await download;if(!item.suggestedFilename().includes('s37-reversed'))throw new Error('download identity');
  if(errors.length)throw new Error(errors.join('\n'));
  results.push({width,source,overflow:false,errors,table_rows:40,seeking:true,playback:true,download:true});
  await page.close();
 }
 await writeFile(resolve(qa,'checks.json'),JSON.stringify(results,null,2));
 console.log(JSON.stringify(results));
} finally { await browser.close(); }
