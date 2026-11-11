import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve,dirname} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(resolve(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const work=resolve(root,'.work/language-calibration-20261005'),qa=resolve(work,'viewer-qa');
await mkdir(qa,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true}),checks=[];
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(resolve(work,'language-calibration.html')).href);
  await page.locator('#history tr').first().waitFor();
  const count=await page.locator('#source option').count();if(count!==15)throw Error('continuous sources '+count);
  await page.locator('#source').selectOption('1');
  await page.locator('#time').evaluate(el=>{el.value='120';el.dispatchEvent(new Event('input'));});
  const time=await page.locator('#when').innerText();
  if(!time.includes('592.0'))throw Error('time seek '+time);
  await page.locator('#next').click();if(await page.locator('#time').inputValue()!=='121')throw Error('next');
  await page.locator('#previous').click();if(await page.locator('#time').inputValue()!=='120')throw Error('previous');
  if(await page.locator('#history tr').count()!==9)throw Error('bounded history');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('viewport overflow '+width);
  await page.screenshot({path:resolve(qa,`viewer-${width}.png`)});
  await page.locator('#objectText').scrollIntoViewIfNeeded();await page.screenshot({path:resolve(qa,`readout-${width}.png`)});
  if(errors.length)throw Error(errors.join('\n'));
  checks.push({width,sources:count,errors,overflow:false,seeking:true,previous_next:true,visible_history:9});
  await page.close();
 }
 await writeFile(resolve(qa,'checks.json'),JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));
}finally{await browser.close()}
