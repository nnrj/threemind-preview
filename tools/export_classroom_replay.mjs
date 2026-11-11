/** MP4 from the complete classroom viewer's own canvas. Never executes Core. */
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {dirname,resolve} from 'node:path';
import {stat,writeFile,rename} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(resolve(root,'threemind-ui/package.json'));
const {chromium}=require('playwright');
const args=process.argv.slice(2),opt=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
if(!opt('--input')||!opt('--output'))throw Error('Use --input complete-replay.html --output complete.mp4 [--preview-only]');
const input=resolve(opt('--input')),output=resolve(opt('--output')),fps=Number(opt('--fps','20'));
if(!Number.isInteger(fps)||fps<1||fps>30)throw Error('FPS 1–30');
if((await stat(input)).size>128*1024**2)throw Error('Replay exceeds128MiB');
const preview=args.includes('--preview-only');
if(!preview&&await stat(output).catch(()=>null))throw Error('Refuse to replace existing video');
const started=Date.now(),folder=dirname(output),checks=[];let browser,encoder,encoderDone,encodeError;
try{
  browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(input).href);await page.waitForFunction(()=>!!window.classroomReplay);
  await page.evaluate(()=>document.fonts.ready);
  const spec=await page.evaluate(()=>({duration:classroomReplay.duration,chapters:classroomReplay.chapters,title:classroomReplay.title||'ThreeMind E55 完整教学与对照实验'}));
  if(spec.duration>3600)throw Error('More than one hour of video');
  const times=[0,...spec.chapters.filter((c,i)=>[0,2,5,7,12,13,14,15].includes(i)).map(c=>c.start+5),spec.duration-5];
  for(let i=0;i<times.length;i++)await writeFile(resolve(folder,`preview-${String(i).padStart(2,'0')}.png`),Buffer.from(await page.evaluate(t=>classroomReplay.frame(t,'image/png'),times[i]),'base64'));
  await writeFile(resolve(folder,'poster.png'),Buffer.from(await page.evaluate(t=>classroomReplay.frame(t,'image/png'),(spec.chapters.find(c=>c.title.includes('最近4帧'))||spec.chapters[0]).start+Math.min(6,(spec.chapters[0].end-spec.chapters[0].start)/2)),'base64'));
  const completeViewer=await page.locator('#chapter').count();
  if(completeViewer){
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});await page.locator('#chapter').selectOption(String(spec.chapters[13].start));
    await page.locator('#play').click();await page.waitForTimeout(300);await page.locator('#play').click();
    const advanced=await page.evaluate(t=>Number(document.querySelector('#seek').value)>t,spec.chapters[13].start);
    await page.locator('#seek').evaluate((el,t)=>{el.value=t;el.dispatchEvent(new Event('input',{bubbles:true}))},spec.chapters[13].start+6.95);
    await page.screenshot({path:resolve(folder,`ui-${width}.png`),fullPage:true});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
    const downloading=page.waitForEvent('download');await page.locator('#shot').click();const download=await downloading;await download.saveAs(resolve(folder,`screenshot-${width}.png`));
    checks.push({width,advanced,overflow,screenshot_bytes:(await stat(resolve(folder,`screenshot-${width}.png`))).size});
  }
  }
  if(errors.length||checks.some(c=>!c.advanced||c.overflow||!c.screenshot_bytes))throw Error(JSON.stringify({errors,checks}));
  await writeFile(resolve(folder,'display-check.json'),JSON.stringify({checks,errors,preview_times:times},null,2));
  if(preview){console.log(JSON.stringify({duration:spec.duration,chapters:spec.chapters.length,previews:folder}));}
  else{
    const meta=resolve(folder,'chapters.ffmeta'),escape=s=>s.replace(/[=;#\\]/g,'\\$&').replace(/\n/g,' ');
    const chapters=[{start:0,end:spec.chapters[0].start,title:'阅读说明'},...spec.chapters,{start:spec.chapters.at(-1).end,end:spec.duration,title:'结果与未执行项目'}].filter(c=>c.end>c.start);
    await writeFile(meta,';FFMETADATA1\ntitle='+escape(spec.title)+'\n'+chapters.map(c=>`[CHAPTER]\nTIMEBASE=1/1000\nSTART=${Math.round(c.start*1000)}\nEND=${Math.round(c.end*1000)}\ntitle=${escape(c.title)}\n`).join(''),'utf8');
    const partial=output.replace(/\.mp4$/i,'')+'.partial.mp4';let stderr='';
    encoder=spawn(opt('--ffmpeg',process.env.FFMPEG||'ffmpeg'),['-hide_banner','-loglevel','warning','-n','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','pipe:0','-i',meta,'-map','0:v','-map_metadata','1','-map_chapters','1','-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',partial],{windowsHide:true,stdio:['pipe','ignore','pipe']});
    encoder.stderr.on('data',b=>{stderr=(stderr+b.toString()).slice(-4000)});encoder.stdin.on('error',e=>{encodeError=e});
    encoderDone=new Promise(resolve=>{encoder.on('error',e=>{encodeError=e;resolve(-1)});encoder.on('close',resolve)});
    const count=Math.ceil(spec.duration*fps);
    for(let n=0;n<count;n++){
      if(encodeError||encoder.exitCode!==null)throw encodeError||Error(stderr);
      if(Date.now()-started>20*60*1000)throw Error('20-minute media export budget');
      const bytes=Buffer.from(await page.evaluate(t=>classroomReplay.frame(t),n/fps),'base64');
      if(!encoder.stdin.write(bytes))await Promise.race([once(encoder.stdin,'drain'),encoderDone.then(()=>{throw encodeError||Error(stderr)})]);
      if(n%(fps*60)===0){if((await stat(partial).catch(()=>({size:0}))).size>512*1024**2)throw Error('Video512MiB bound');console.log(`Rendered ${n}/${count} (${Math.round(n/count*100)}%)`);}
    }
    encoder.stdin.end();if(await encoderDone!==0)throw Error(stderr);await rename(partial,output);
    const manifest={input,output,duration_s:spec.duration,fps,frames:count,width:1600,height:900,bytes:(await stat(output)).size,wall_seconds:(Date.now()-started)/1000,renderer:'complete classroom UI canvas',audio:false,core_advanced:false,answers_regenerated:false,chapters:chapters.length};
    await writeFile(resolve(folder,'video-manifest.json'),JSON.stringify(manifest,null,2));console.log(JSON.stringify(manifest));
  }
}finally{if(encoder&&encoder.exitCode===null){encoder.kill();await encoderDone;}await browser?.close();}
