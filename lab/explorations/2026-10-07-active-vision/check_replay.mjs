/** Validate a recorded local viewer; no service or Core started. */
import {createRequire} from 'node:module';
import {resolve,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {writeFile,stat} from 'node:fs/promises';
const require=createRequire(resolve('threemind-ui/package.json'));
const {chromium}=require('playwright');
const input=resolve(process.argv[2]),folder=dirname(input),errors=[],checks=[];
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(input).href);await page.evaluate(()=>document.fonts.ready);
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:950});await page.locator('#clip').selectOption('0');
  await page.locator('#play').click();await page.waitForTimeout(350);await page.locator('#play').click();
  const advanced=await page.locator('#seek').evaluate(el=>+el.value>0);
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  await page.screenshot({path:resolve(folder,`eye-viewer-${width}.png`),fullPage:true});
  const pending=page.waitForEvent('download');await page.locator('#shot').click();
  const download=await pending,dest=resolve(folder,`eye-scene-${width}.png`);await download.saveAs(dest);
  checks.push({width,advanced,overflow,screenshot_bytes:(await stat(dest)).size});
 }
 await page.locator('#clip').selectOption('0');await page.locator('#record').click();await page.waitForTimeout(1600);
 const pending=page.waitForEvent('download');await page.locator('#record').click();
 const download=await pending,video=resolve(folder,'eye-recording-check.webm');await download.saveAs(video);
 const playback=await browser.newPage();await playback.goto(pathToFileURL(video).href);
 const decoded=await playback.locator('video').evaluate(async v=>{v.muted=true;await v.play();await new Promise(r=>setTimeout(r,250));return{width:v.videoWidth,height:v.videoHeight,currentTime:v.currentTime,error:v.error?.message||null}});
 const result={input,errors,checks,video_bytes:(await stat(video)).size,decoded,core_advanced:false};
 if(errors.length||checks.some(c=>!c.advanced||c.overflow||!c.screenshot_bytes)||result.video_bytes<1024||!decoded.width||!decoded.currentTime||decoded.error)throw Error(JSON.stringify(result));
 await writeFile(resolve(folder,'eye-viewer-check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
