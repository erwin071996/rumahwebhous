/* Focused synthetic CMS fixture QA. Loopback only; no live CMS or private draft. */
"use strict";
const {chromium}=require("playwright"),fs=require("node:fs/promises"),path=require("node:path"),assert=require("node:assert/strict");
const target=new URL(process.env.QA_CMS_URL||"");
assert(["127.0.0.1","localhost","[::1]"].includes(target.hostname)&&target.protocol==="http:"&&!target.username&&!target.password&&!target.search,"Explicit loopback fixture URL required");
const out=path.resolve(process.env.QA_CMS_ARTIFACT_DIR||"artifacts/cms-prototype"),checks=[],leaks=[],errors=[],dialogs=[];let browser,version=null;
(async()=>{await fs.mkdir(out,{recursive:true});try{
browser=await chromium.launch({headless:true});version=await browser.version();
const c=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:"block"});
await c.routeWebSocket("**/*",socket=>{leaks.push({kind:"WebSocket"});socket.close();});
await c.route("**/*",route=>{const r=route.request(),u=new URL(r.url());if(r.method()!=="GET"||u.origin!==target.origin||u.pathname!==target.pathname||u.search){leaks.push({kind:"Request",method:r.method(),path:u.pathname});return route.abort("blockedbyclient");}return route.continue();});
await c.addInitScript(()=>{globalThis.__cmsEffects=[];globalThis.__cmsGuardsReady=false;const denied=name=>function(){__cmsEffects.push(name);throw Error("Fixture blocked "+name);};globalThis.fetch=denied("fetch");globalThis.XMLHttpRequest=denied("XHR");globalThis.WebSocket=denied("WebSocket");for(const key of ["localStorage","sessionStorage"])Object.defineProperty(globalThis,key,{configurable:true,get:denied(key)});navigator.sendBeacon=denied("sendBeacon");globalThis.__cmsGuardsReady=true;});
const p=await c.newPage();p.setDefaultTimeout(8000);p.on("pageerror",e=>errors.push(e.message));p.on("dialog",async d=>{dialogs.push(d.type());await d.dismiss();});
async function check(name,fn){await fn();checks.push({name,status:"PASS"});}
await p.goto(target.href,{waitUntil:"load"});
await check("Blank session and disabled export",async()=>{assert.equal(await p.evaluate(()=>__cmsGuardsReady),true,"Fixture guards failed to install");assert.equal(await p.locator("#cms-title").inputValue(),"");assert(await p.locator("#cms-queue").isDisabled());assert(await p.locator("#cms-preview").isDisabled());});
await check("Error focus and native Tab sequence",async()=>{await p.locator("#cms-prepare").click();assert.equal(await p.evaluate(()=>document.activeElement.id),"cms-kind");await p.keyboard.press("Tab");assert.equal(await p.evaluate(()=>document.activeElement.id),"cms-title");});
await p.locator("#cms-kind").selectOption("Proyek");await p.locator("#cms-title").fill("<img src=x onerror=alert(1)>");await p.locator("#cms-summary").fill("Ringkasan sintetis");await p.locator("#cms-source").fill("javascript:alert(1)");
await p.locator("#cms-select-a").check();await p.locator("#cms-select-b").check();await p.locator("#cms-cover-a").check();
async function preview(){await p.locator("#cms-prepare").click();await p.locator("#cms-preview").click();}
await check("Literal preview and heading focus",async()=>{await preview();assert.equal(await p.locator("#cms-preview-title").textContent(),"<img src=x onerror=alert(1)>");assert.equal(await p.locator("#cms-output img, #cms-output a[href]").count(),0);assert.equal(await p.evaluate(()=>document.activeElement.id),"cms-preview-heading");});
await check("Rights blocker focuses chosen media",async()=>{await p.locator("#cms-approve").click();assert.equal(await p.evaluate(()=>document.activeElement.id),"cms-rights-a");assert.equal(await p.locator("#cms-rights-a").getAttribute("aria-invalid"),"true");});
await p.locator("#cms-rights-a").check();await p.locator("#cms-rights-b").check();await preview();await p.locator("#cms-approve").click();
await check("Simulated approval revokes on edit",async()=>{assert.match(await p.locator("#cms-approval-state").textContent(),/disetujui dalam simulasi/);await p.locator("#cms-summary").fill("Ringkasan sintetis berubah");assert.equal(await p.locator("#cms-approval-state").textContent(),"Belum disetujui.");assert(await p.locator("#cms-output").isHidden());});
await check("Keyboard reorder keeps focus and cover",async()=>{await p.locator("#cms-up-b").focus();await p.keyboard.press("Enter");assert.equal(await p.evaluate(()=>document.activeElement.id),"cms-down-b");assert(await p.locator("#cms-up-b").isDisabled());assert(await p.locator("#cms-cover-a").isChecked());await preview();assert.match(await p.locator("#cms-preview-media").textContent(),/^Media contoh B/);});
await check("Fact change clears verification",async()=>{await p.locator("#cms-fact").fill("Fakta sintetis");await p.locator("#cms-verified").check();await p.locator("#cms-fact").fill("Fakta sintetis berubah");assert.equal(await p.locator("#cms-verified").isChecked(),false);});
await p.screenshot({path:path.join(out,"cms-prototype-1280.png"),fullPage:true});await p.setViewportSize({width:390,height:844});assert.equal(await p.evaluate(()=>innerWidth),390);await p.screenshot({path:path.join(out,"cms-prototype-390.png"),fullPage:true});
await check("No network/storage/write attempts in changed flow",async()=>{assert.deepEqual(await p.evaluate(()=>__cmsEffects),[]);assert.equal(leaks.length,0);assert.equal(errors.length,0);assert.equal(dialogs.length,0);assert(await p.locator("#cms-queue").isDisabled());});
await check("Reload loses draft as explained",async()=>{await p.reload({waitUntil:"load"});assert.equal(await p.evaluate(()=>__cmsGuardsReady),true,"Reload guards failed to install");assert.equal(await p.locator("#cms-title").inputValue(),"");assert.equal(await p.locator("#cms-kind").inputValue(),"");assert(await p.locator("#cms-preview").isDisabled());assert.deepEqual(await p.evaluate(()=>__cmsEffects),[]);});
await c.close();
}catch(error){checks.push({name:"Focused fixture flow",status:"FAIL",detail:error.stack||error.message});}finally{
if(browser)try{await browser.close();}catch(error){checks.push({name:"Browser cleanup",status:"FAIL",detail:error.message});}
if(leaks.length||errors.length||dialogs.length)checks.push({name:"Global fixture isolation",status:"FAIL",detail:{leaks,errors,dialogs}});
const report={runtime:{playwright:require("playwright/package.json").version,chromium:version},fixture:target.pathname,checks,leaks,errors,dialogs,limitations:["Synthetic nonpublic loopback fixture only; no real draft, persistence, identity, CMS adapter, queue or publish capability tested."]};
await fs.writeFile(path.join(out,"results.json"),JSON.stringify(report,null,2)+"\n");console.log(JSON.stringify({passed:checks.filter(x=>x.status==="PASS").length,failed:checks.filter(x=>x.status==="FAIL").length,artifactDir:out},null,2));if(checks.some(x=>x.status==="FAIL"))process.exitCode=1;
}})();
