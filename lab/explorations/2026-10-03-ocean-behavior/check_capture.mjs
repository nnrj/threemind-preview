import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(path.join(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const out=path.join(root,'.work/ocean-behavior-20261003/media/ui');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
try {
  const results=[];
  for(const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:25071/e2e/fixtures/capture.html');
    await page.getByRole('button',{name:'重置视角',exact:true}).click();
    await page.getByText('导出高级选项',{exact:true}).click();
    await page.getByLabel('标题',{exact:true}).filter({visible:true}).first().fill('ThreeMind 真实画面录制验收');
    await page.getByLabel('最长录制秒数',{exact:true}).fill('2');
    const screenshot=page.waitForEvent('download');
    await page.getByRole('button',{name:'截图',exact:true}).click();
    const png=await screenshot;await png.saveAs(path.join(out,`capture-${width}.png`));
    const recording=page.waitForEvent('download',{timeout:20000});
    await page.getByRole('button',{name:'录屏',exact:true}).click();
    await page.getByRole('status').filter({hasText:'正在录制画面'}).waitFor();
    const video=await recording;await video.saveAs(path.join(out,`capture-${width}.webm`));
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    await page.screenshot({path:path.join(out,`ui-${width}.png`),fullPage:true});
    if(errors.length||overflow||await page.getByRole('alert').count())throw new Error(JSON.stringify({width,errors,overflow}));
    results.push({width,errors,overflow,video_bytes:fs.statSync(path.join(out,`capture-${width}.webm`)).size});
    await page.close();
  }
  for(const fallback of [false,true]) {
    const page=await browser.newPage({viewport:{width:1100,height:900},acceptDownloads:true});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    if(fallback)await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext=function(type,...args){return type.startsWith('webgl')?null:original.call(this,type,...args);};});
    await page.goto('http://127.0.0.1:25071/e2e/fixtures/capture.html?graph=1');
    const button=page.getByRole('button',{name:'截图',exact:true});
    await button.waitFor();await page.waitForFunction(()=>!document.querySelector('.capture-panel button').disabled);
    const event=page.waitForEvent('download',{timeout:5000}).catch(async e=>{
      await page.screenshot({path:path.join(out,`graph-error-${fallback}.png`),fullPage:true});
      throw new Error(JSON.stringify({fallback,errors,body:await page.locator('body').innerText(),failure:e.message}));});
    await button.click();
    const download=await event;await download.saveAs(path.join(out,`graph-${fallback?'canvas':'webgl'}.png`));
    if(errors.length)throw new Error(JSON.stringify(errors));
    results.push({graph:true,fallback,errors});await page.close();
  }
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
} finally {await browser.close();}
