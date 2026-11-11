import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(path.join(root,'threemind-ui/package.json'));
const {chromium}=require('@playwright/test');
const folder=path.join(root,'.work/ocean-community-20261003/media/final');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
try {
  const results=[];
  for (const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(folder,'gallery.html')).href);
    await page.waitForFunction(()=>[...document.querySelectorAll('video[data-causal]')].every(v=>v.duration===13));
    await page.locator('#seek').evaluate(e=>{e.value='6';e.dispatchEvent(new Event('input'))});
    await page.getByRole('button',{name:'一起播放',exact:true}).click();
    await page.waitForFunction(()=>[...document.querySelectorAll('video[data-causal]')].every(v=>v.currentTime>6.2));
    await page.getByRole('button',{name:'一起暂停',exact:true}).click();
    const state=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,
      videos:[...document.querySelectorAll('video[data-causal]')].map(v=>({paused:v.paused,time:v.currentTime,duration:v.duration}))}));
    if(errors.length||state.overflow||state.videos.some(v=>!v.paused))throw new Error(JSON.stringify({width,errors,state}));
    await page.screenshot({path:path.join(folder,`gallery-${width}.png`),fullPage:false});
    results.push({width,errors,...state});await page.close();
  }
  fs.writeFileSync(path.join(folder,'gallery-verification.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
}finally{await browser.close();}
