const {chromium}=require('../../../threemind-ui/node_modules/@playwright/test');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const root=path.resolve(__dirname,'../../..');
 const work=path.join(root,'.work/ocean-evolution-20261003');
 const name=process.argv[2]||'engineering';
 const expectedMembers=Number(process.argv[3]||31);
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const records=[];
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(pathToFileURL(path.join(work,`views/${name}.html`)).href);
   await page.locator('#time').fill(await page.locator('#time').getAttribute('max'));
   await page.locator('#time').dispatchEvent('input');
   assert.equal(await page.locator('#members tr').count(),expectedMembers);
   await page.locator('#members tr').first().click();
   assert.match(await page.locator('#detail').innerText(),/推进耗能/);
   await page.getByLabel('身体着色').selectOption('shell');
   await page.getByRole('checkbox',{name:'营养颗粒',exact:true}).uncheck();
   await page.getByRole('checkbox',{name:'营养颗粒',exact:true}).check();
   const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载场景配置'}).click()]);
   assert.match(download.suggestedFilename(),/protocol\.json$/);
   await page.locator('#time').fill('0');await page.locator('#time').dispatchEvent('input');
   await page.getByRole('button',{name:'播放',exact:true}).click();
   await page.waitForFunction(()=>Number(document.querySelector('#time').value)>0);
   await page.getByRole('button',{name:'暂停',exact:true}).click();
   await page.locator('#time').fill(await page.locator('#time').getAttribute('max'));
   await page.locator('#time').dispatchEvent('input');
   await page.locator('#members tr').first().click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);
   await page.screenshot({path:path.join(work,`viewer-${name}-${width}.png`),fullPage:true});
   records.push({width,passed:true,rows:await page.locator('#members tr').count(),download:download.suggestedFilename()});
   await page.close();
  }
 }finally{await browser.close();}
 fs.writeFileSync(path.join(work,`viewer-verification-${name}.json`),JSON.stringify(records,null,2),{flag:'wx'});
 console.log(JSON.stringify(records));
})().catch(e=>{console.error(e);process.exitCode=1;});
