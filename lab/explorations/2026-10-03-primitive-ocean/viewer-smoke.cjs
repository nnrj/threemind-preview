const {chromium}=require('../../../threemind-ui/node_modules/@playwright/test');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const root=path.resolve(__dirname,'../../..');
 const work=path.join(root,'.work/primitive-ocean-20261003');
 const caseName=process.argv[2]||'phase1-0-core';
 const expectedRows=Number(process.argv[3]||16);
 const suffix=process.argv[2]?`-${caseName}`:'';
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const records=[];
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(pathToFileURL(path.join(work,`views/${caseName}.html`)).href);
   await page.locator('#time').fill(await page.locator('#time').getAttribute('max'));
   await page.locator('#time').dispatchEvent('input');
   assert.match(await page.locator('#stats').innerText(),/900 模拟秒/);
   assert.equal(await page.locator('#members tr').count(),expectedRows);
   await page.locator('#time').fill('0');await page.locator('#time').dispatchEvent('input');
   await page.getByRole('button',{name:'播放',exact:true}).click();
   await page.waitForFunction(()=>Number(document.querySelector('#time').value)>0);
   await page.getByRole('button',{name:'暂停',exact:true}).click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);
   await page.screenshot({path:path.join(work,`viewer${suffix}-${width}.png`),fullPage:true});
   records.push({width,passed:true,rows:await page.locator('#members tr').count()});
   await page.close();
  }
 }finally{await browser.close();}
 fs.writeFileSync(path.join(work,`viewer-verification${suffix}.json`),JSON.stringify(records,null,2),{flag:'wx'});
 console.log(JSON.stringify(records));
})().catch(e=>{console.error(e);process.exitCode=1;});
