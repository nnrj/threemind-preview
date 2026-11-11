/** Check the recorded viewer only; no Core, server or remote model is started. */
import {createRequire} from 'node:module';
import {resolve,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {writeFile,stat} from 'node:fs/promises';
const require=createRequire(resolve('threemind-ui/package.json'));
const {chromium}=require('playwright');
const input=resolve(process.argv[2]||'.work/vision-correction-20261006/replay-preview.html');
const folder=dirname(input),browser=await chromium.launch({channel:'msedge',headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(input).href);await page.evaluate(()=>document.fonts.ready);
  const clips=await page.locator('#clips option').count();
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    await page.locator('#clips').selectOption(String(clips-1));
    const initial=await page.locator('#control').innerText();
    await page.locator('#play').click();await page.waitForTimeout(500);await page.locator('#play').click();
    const advanced=await page.locator('#seek').evaluate(el=>+el.value>0);
    await page.locator('#seek').evaluate(el=>{el.value=el.max;el.dispatchEvent(new Event('input',{bubbles:true}))});
    const final=await page.locator('#control').innerText();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
    await page.screenshot({path:resolve(folder,`viewer-${width}.png`),fullPage:true});
    const pending=page.waitForEvent('download');await page.locator('#shot').click();
    const download=await pending,path=resolve(folder,`viewer-scene-${width}.png`);await download.saveAs(path);
    checks.push({width,advanced,overflow,initial,final,screenshot_bytes:(await stat(path)).size});
  }
  if(!clips||errors.length||checks.some(c=>!c.advanced||c.overflow||!c.initial.includes('环境风力')||!c.final.includes('伺服执行')||!c.screenshot_bytes))
    throw Error(JSON.stringify({clips,errors,checks}));
  const result={input,clips,errors,checks,core_advanced:false};
  await writeFile(resolve(folder,'viewer-check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
