import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve,dirname} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(resolve(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const work=resolve(root,'.work/native-language-20261005'),qa=resolve(work,'viewer-qa');
await mkdir(qa,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true}),checks=[];
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(resolve(work,'native-expression.html')).href);
  await page.locator('#mediation tr').first().waitFor();
  const count=await page.locator('#source option').count();if(count!==9)throw Error('sources '+count);
  await page.locator('#source').selectOption('s163-background');
  await page.locator('#head').selectOption('developmental');
  await page.locator('#time').evaluate(el=>{el.value='120';el.dispatchEvent(new Event('input'));});
  const time=await page.locator('#when').innerText();if(!time.includes('328.0'))throw Error('seek '+time);
  await page.locator('#play').click();
  await page.waitForFunction(()=>document.querySelector('#time').value!=='120');
  await page.locator('#play').click();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('overflow '+width);
  await page.screenshot({path:resolve(qa,`viewer-${width}.png`)});
  if(errors.length)throw Error(errors.join('\n'));
  checks.push({width,sources:count,errors,overflow:false,seeking:true,play_pause:true,head_selection:true});
  await page.close();
 }
 await writeFile(resolve(qa,'checks.json'),JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));
}finally{await browser.close()}
