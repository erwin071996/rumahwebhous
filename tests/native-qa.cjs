/* Native cloud QA only. Requires playwright; backend owns server/dependency capture. */
"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const base = new URL(process.env.QA_BASE_URL || "");
if (!["127.0.0.1","localhost","[::1]"].includes(base.hostname) || base.username || base.password || !["http:","https:"].includes(base.protocol)) throw Error("QA_BASE_URL must be an isolated loopback origin");
const out = path.resolve(process.env.QA_ARTIFACT_DIR || "artifacts/native-qa");
const nonce = "QA_BRIEF_DO_NOT_SEND_" + Date.now();
const results = [], artifacts = [], blocked = [], leaks = [], unavailable = new Set(), errors = [];
let browser;
const dependencyStates = new WeakMap();
const REQUIRED_UI = ["/assets/ui/brief.css","/assets/ui/brief.js","/assets/ui/frontend.css","/assets/ui/frontend.js"];
const assetType = req => ["script","stylesheet"].includes(req.resourceType());
function decoded(value) {
let result=String(value || "");
for(let i=0;i<3;i++) {
const next=result.replace(/\+/g," ").replace(/%([0-9a-f]{2})/gi,(_,hex)=>String.fromCharCode(parseInt(hex,16)));
if(next===result) break; result=next;
}
return result;
}
function containsNonce(value) { return decoded(value).includes(nonce); }
function expectedAnalytics(u,req) {
return u.protocol==="https:" && !u.port && !u.username && !u.password && ["GET","HEAD"].includes(req.method()) &&
/^(www\.googletagmanager\.com|www\.google-analytics\.com|region[0-9]+\.google-analytics\.com)$/.test(u.hostname) &&
((req.resourceType()==="script" && ["/gtag/js","/gtm.js"].includes(u.pathname)) || ["/g/collect","/collect"].includes(u.pathname));
}
function dependencyFailure(state,raw,reason) {
const u=new URL(raw), label=u.origin===base.origin ? u.pathname : u.origin+u.pathname;
state.failed.add(label+" ("+reason+")"); unavailable.add(label);
}
function report(name,status,detail) { results.push({ name, status, ...(detail ? { detail:String(detail) } : {}) }); }
async function check(name,fn,reason) {
try {
const before=typeof reason==="function" ? await reason() : reason;
if(before) return report(name,"NOT RUN",before);
await fn();
const after=typeof reason==="function" ? await reason() : "";
if(after) return report(name,"NOT RUN",after);
report(name,"PASS");
} catch(e) { report(name,"FAIL",e.message); }
}
async function context(viewport,js=true,denyBrief=false) {
const c=await browser.newContext({ viewport, javaScriptEnabled:js, serviceWorkers:"block" });
const state={failed:new Set(),delivered:new Set(),js,denyBrief,closing:false};
dependencyStates.set(c,state);
const intendedAbort=req=>denyBrief && new URL(req.url()).origin===base.origin && new URL(req.url()).pathname==="/assets/ui/brief.js";
c.on("requestfailed",req=>{
if(state.closing || !assetType(req) || intendedAbort(req)) return;
const u=new URL(req.url()); if(expectedAnalytics(u,req)) return;
dependencyFailure(state,req.url(),req.failure()?.errorText || "request failed");
});
c.on("response",response=>{
const req=response.request(),u=new URL(response.url());
if(!assetType(req) || u.origin!==base.origin) return;
const mime=(response.headers()["content-type"] || "").split(";")[0].trim().toLowerCase();
const valid=req.resourceType()==="stylesheet" ? mime==="text/css" : /^(?:text|application)\/(?:javascript|ecmascript)$/.test(mime);
if(response.status()>=400 || !valid) dependencyFailure(state,response.url(),"HTTP "+response.status()+" / "+mime);
});
c.on("requestfinished",req=>{ if(assetType(req) && new URL(req.url()).origin===base.origin) state.delivered.add(req.url()); });
if(js) await c.addInitScript(() => Object.defineProperty(navigator,"clipboard",{ configurable:true, value:{ writeText:async()=>{ throw new Error("QA mocked clipboard denial"); } } }));
if(typeof c.routeWebSocket!=="function") throw Error("Required Playwright routeWebSocket API unavailable");
await c.routeWebSocket("**/*",async ws=>{
const u=new URL(ws.url());
blocked.push({origin:u.origin,path:u.pathname,method:"WEBSOCKET",category:"unexpected"});
leaks.push({method:"WEBSOCKET",path:u.pathname,reason:"unexpected WebSocket attempted"});
await ws.close({code:1008,reason:"QA network isolation"});
});
await c.route("**/*", async route => {
const req=route.request(), u=new URL(req.url()), body=req.postData() || "";
const sensitive=containsNonce(req.url()+" "+body), safeMethod=["GET","HEAD"].includes(req.method());
const lead=decoded(req.url()+" "+body).includes("generate_lead");
const analytics=expectedAnalytics(u,req) && !sensitive && !lead;
if(sensitive) leaks.push({method:req.method(),path:u.pathname,reason:"synthetic brief attempted in request"});
if(lead) leaks.push({method:req.method(),path:u.pathname,reason:"premature generate_lead attempted"});
if(!safeMethod) leaks.push({method:req.method(),path:u.pathname,reason:"unexpected non-GET request"});
if(["xhr","fetch","eventsource"].includes(req.resourceType()) && !analytics) leaks.push({method:req.method(),path:u.pathname,reason:"unexpected XHR/fetch/eventsource request"});
if(u.origin!==base.origin && !analytics) leaks.push({method:req.method(),path:u.pathname,reason:"unexpected external request"});
if(u.origin!==base.origin || !safeMethod || sensitive || lead || ["xhr","fetch","eventsource"].includes(req.resourceType())) {
blocked.push({ origin:u.origin, path:u.pathname, method:req.method(), category:analytics ? "expected-analytics" : "unexpected" });
return route.abort("blockedbyclient");
}
if (intendedAbort(req)) return route.abort("blockedbyclient");
if (/\/assets\/portfolio-real\/videos\/.*\.mp4$/.test(u.pathname)) return route.fulfill({status:404,contentType:"text/plain",body:"QA mocked media unavailable"});
return route.continue();
});
return c;
}
async function open(c,url) {
const p=await c.newPage(); p.setDefaultTimeout(4000);
const state=dependencyStates.get(c); dependencyStates.set(p,state);
p.on("pageerror",e=>errors.push({url,error:e.message}));
await p.goto(new URL(url,base).href,{waitUntil:"load",timeout:20000});
return {p,missing:state.failed};
}
async function dependencyReason(p) {
const state=dependencyStates.get(p);
const declared=await p.evaluate(()=>[
...Array.from(document.querySelectorAll('link[rel~="stylesheet"][href]')).filter(e=>!e.disabled).map(e=>({url:e.href,type:"stylesheet"})),
...Array.from(document.querySelectorAll("script[src]")).filter(e=>!e.type || ["module","text/javascript","application/javascript","text/ecmascript","application/ecmascript"].includes(e.type.toLowerCase())).map(e=>({url:e.src,type:"script"}))
]);
const localPaths=new Set();
for(const entry of declared) {
const u=new URL(entry.url),stub={method:()=>"GET",resourceType:()=>entry.type};
if(expectedAnalytics(u,stub)) continue;
if(u.origin!==base.origin) {dependencyFailure(state,entry.url,"nonlocal dependency");continue;}
localPaths.add(u.pathname);
if(state.denyBrief && u.pathname==="/assets/ui/brief.js") continue;
if(!state.delivered.has(entry.url)) dependencyFailure(state,entry.url,"dependency not loaded");
}
for(const required of REQUIRED_UI) if(!localPaths.has(required)) dependencyFailure(state,new URL(required,base).href,"required dependency absent from DOM");
return state.failed.size ? "CSS/JS unavailable: "+[...state.failed].join(", ") : "";
}
const focused=async(p,l)=>p.waitForFunction(el=>el===document.activeElement,await l.elementHandle(),{timeout:4000});
const poll=(p,fn,arg)=>p.waitForFunction(fn,arg,{timeout:4000});
async function shot(p,name) {
await p.evaluate(async()=>{
if(document.fonts) await document.fonts.ready;
const visible=Array.from(document.images).filter(img=>{const r=img.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.right>0&&r.top<innerHeight&&r.left<innerWidth;});
await Promise.all(visible.map(img=>img.decode()));
});
const file=path.join(out,name); await p.screenshot({path:file,fullPage:false}); artifacts.push(file);
const styles=await p.evaluate(()=>Array.from(document.querySelectorAll("h1,.portfolio-lead,.portfolio-hero-note strong,.portfolio-hero-note p,.home-proof small,.home-proof span,.presentation-summary small,.presentation-summary strong,form[data-brief-form] input,form[data-brief-form] select,form[data-brief-form] textarea")).map(el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect(),layers=[]; for(let n=el,i=0;n&&i<6;n=n.parentElement,i++){const b=getComputedStyle(n);layers.push({tag:n.tagName,id:n.id,background:b.backgroundColor,backgroundImage:b.backgroundImage});} return {tag:el.tagName,id:el.id,text:el.textContent.slice(0,80),color:s.color,background:s.backgroundColor,backgroundImage:s.backgroundImage,fontSize:s.fontSize,borderWidth:s.borderWidth,borderStyle:s.borderStyle,borderColor:s.borderColor,outline:s.outline,outlineWidth:s.outlineWidth,outlineColor:s.outlineColor,outlineOffset:s.outlineOffset,active:el===document.activeElement,focusVisible:el.matches(":focus-visible"),backgroundLayers:layers,rect:{x:r.x,y:r.y,width:r.width,height:r.height}};}));
const evidence=path.join(out,name+".computed.json"); await fs.writeFile(evidence,JSON.stringify(styles,null,2)); artifacts.push(evidence); }
async function pages() {
for(const viewport of [{width:1280,height:720},{width:390,height:844},{width:320,height:800}]) for(const url of ["/","/projects.html"]) {
const c=await context(viewport), {p,missing}=await open(c,url);
const key=(url==="/"?"index":"projects")+"-"+viewport.width, why=()=>dependencyReason(p);
await check(key+" screenshot captured (visual review pending)",()=>shot(p,key+".png"));
if(url==="/"&&viewport.width===1280) await check(key+" initial hero CTAs above fold and hit-test",async()=>{
const ctas=p.locator(".home-hero .button-row a[href]"); assert.equal(await ctas.count(),2);
for(let i=0;i<2;i++) assert(await ctas.nth(i).evaluate(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}));
},why);
await check(key+" no horizontal overflow and visible heading",async()=>{ assert(await p.locator("h1").isVisible()); assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)); },why);
await check(key+" keyboard Escape/focus and restored scrolling",async()=>{
const menu=p.locator(".menu-toggle"), summary=p.locator(".nav-services > summary");
if(viewport.width<=1020) {
await menu.focus(); await p.keyboard.press("Space"); await poll(p,()=>document.querySelector(".menu-toggle").getAttribute("aria-expanded")==="true");
await p.keyboard.press("Escape"); await focused(p,menu); assert.equal(await menu.getAttribute("aria-expanded"),"false");
} else {
await summary.focus(); await p.keyboard.press("Enter"); await poll(p,()=>document.querySelector(".nav-services").open);
await p.keyboard.press("Escape"); await focused(p,summary); assert.equal(await p.locator(".nav-services").evaluate(e=>e.open),false);
}
await p.evaluate(()=>scrollTo(0,0)); await p.mouse.wheel(0,500); await poll(p,()=>scrollY>100);
},why);
if(viewport.width===1280) await check(key+" breakpoint 1020/1021 visible focus",async()=>{
const link=p.locator("#site-nav > a[href]").first(), menu=p.locator(".menu-toggle"), summary=p.locator(".nav-services > summary");
await link.focus(); await p.setViewportSize({width:1020,height:844}); await focused(p,menu);
await p.setViewportSize({width:1021,height:720}); await focused(p,summary);
await p.setViewportSize(viewport);
const field=p.locator("form[data-brief-form] textarea[name=note]"); await field.focus();
await p.setViewportSize({width:390,height:844}); await focused(p,field); await p.setViewportSize(viewport);
},why);
await check(key+" brief validation, preview, mocked-copy denial and stale edit",async()=>{
const f=p.locator("form[data-brief-form]"), type=f.locator("select[name=type]"), compose=f.locator("[data-brief-compose]"), status=f.locator("[data-brief-status]"), output=f.locator("[data-brief-output]"), note=f.locator("textarea[name=note]");
assert.equal(await f.locator("[data-brief-fields]").evaluate(e=>e.disabled),false);
assert(await f.locator("input,select,textarea").evaluateAll(es=>es.every(e=>{const r=e.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1;})));
await type.selectOption(""); await compose.click(); await focused(p,type); assert.equal(await output.isVisible(),false);
await type.selectOption("Neon box"); await note.fill(nonce); await compose.click();
assert(await output.isVisible()); assert((await f.locator("[data-brief-preview]").inputValue()).includes(nonce));
assert(await f.locator("[data-brief-preview]").evaluate(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.left>=-1&&r.right<=innerWidth+1;}));
assert(await p.evaluate(()=>!(window.dataLayer||[]).some(entry=>entry&&entry[0]==="event"&&entry[1]==="generate_lead")),"Premature lead queued in dataLayer");
assert(!/sudah dikirim|berhasil dikirim|generate_lead/i.test(await status.textContent()));
assert((await f.locator("[data-brief-whatsapp]").getAttribute("href")).startsWith("https://wa.me/6285340382029?text=")); /* Never click this link. */
await f.locator("[data-brief-copy]").click(); await focused(p,f.locator("[data-brief-preview]"));
assert(!/tersalin/i.test(await status.textContent())); assert(/menu perangkat|Ctrl\+C/.test(await status.textContent()));
await note.fill(nonce+"_edited"); assert.equal(await output.isVisible(),false); assert.equal(await f.locator("[data-brief-whatsapp]").getAttribute("href"),null);
await note.focus(); await focused(p,note); assert(await note.evaluate(el=>{const s=getComputedStyle(el);return el.matches(":focus-visible")&&s.outlineStyle!=="none"&&parseFloat(s.outlineWidth)>=2;})); await shot(p,key+"-brief.png");
},why);
if(url==="/projects.html") {
await check(key+" filter counts/ARIA and hidden keyboard exclusion",async()=>{
const expected={all:10,corporate:2,government:5,retail:2,worship:1};
for(const [category,total] of Object.entries(expected)) {
await p.locator(".real-filter[data-filter="+category+"]").click();
assert.equal(await p.locator(".real-card:not([hidden])").count(),total);
assert.equal(await p.locator('.real-filter[aria-pressed="true"]').count(),1);
assert((await p.locator("#gallery-result-count").textContent()).startsWith(total+" proyek"));
}
for(let i=0;i<18;i++){ await p.keyboard.press("Tab"); assert.equal(await p.evaluate(()=>!!document.activeElement.closest(".real-card[hidden]")),false); }
await p.locator(".real-filter[data-filter=all]").click(); await p.locator("#project-gallery").scrollIntoViewIfNeeded(); await shot(p,key+"-gallery.png");
},why);
await check(key+" portfolio mocked-copy denial and toolbar hit target",async()=>{
await p.locator("#copy-portfolio-link").click();
const input=p.locator("#portfolio-share-url"); await focused(p,input); assert(await input.isVisible());
assert((await input.inputValue()).endsWith("/projects.html#studi-kasus")); assert(!/tersalin/i.test(await p.locator("#client-tool-status").textContent()));
const a=p.locator('.client-tools-actions a[href="#brief-proyek"]'); await a.scrollIntoViewIfNeeded();
assert(await a.evaluate(el=>{ const b=el.getBoundingClientRect(); return el.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2)); }));
},why);
await check(key+" native dialog + mocked MP4 error/close/focus",async()=>{
const trigger=p.locator(".real-video").first(), close=p.locator("#real-video-close");
await trigger.click(); await focused(p,close); await poll(p,()=>document.querySelector("#real-video-dialog").open);
assert(await p.locator("#real-video-dialog").evaluate(el=>el.matches(":modal")),"Native dialog did not enter modal top layer");
await poll(p,()=>/belum dapat dimuat/.test(document.querySelector("#real-video-status").textContent));
assert((await p.locator("#real-video-source").getAttribute("href")).endsWith(".mp4"));
await p.keyboard.press("Escape"); await poll(p,()=>!document.querySelector("#real-video-dialog").open); await focused(p,trigger);
assert(await p.locator("#real-video-player").evaluate(v=>v.paused&&!v.getAttribute("src")));
await p.evaluate(async()=>{ const b=document.querySelectorAll(".real-video"), d=document.querySelector("#real-video-dialog"); b[0].click(); const closed=new Promise(resolve=>d.addEventListener("close",resolve,{once:true})); d.close(); b[1].click(); await closed; });
await p.waitForFunction(()=>document.querySelector("#real-video-dialog").open);
assert(await p.locator("#real-video-dialog").evaluate(d=>d.matches(":modal")));
assert.equal(await p.locator("#real-video-player").getAttribute("src"),await p.locator(".real-video").nth(1).getAttribute("data-video")); await focused(p,close);
await p.keyboard.press("Escape");
},why);
}
if(viewport.width===1280) await check(key+" print PDF captured (visual review pending)",async()=>{
if(url==="/projects.html") await p.locator(".real-filter[data-filter=retail]").click(); await p.emulateMedia({media:"print"});
if(url==="/projects.html") assert(await p.locator(".real-card").evaluateAll(es=>es.length===10&&es.every(e=>getComputedStyle(e).display!=="none"))); const file=path.join(out,key+".pdf"); await p.pdf({path:file,format:"A4",printBackground:true}); artifacts.push(file); await p.emulateMedia({media:"screen"});
},why);
dependencyStates.get(c).closing=true; await c.close();
}
}
async function inertForms() {
for(const url of ["/","/projects.html"]) for(const mode of ["no-js","brief-js-blocked"]) {
await check((url==="/"?"index":"projects")+" "+mode+" native disabled/no data leakage",async()=>{
const c=await context({width:390,height:844},mode!=="no-js",mode==="brief-js-blocked");
try {
const {p}=await open(c,url), f=p.locator("form[data-brief-form]");
assert(await f.locator("input[name],select[name],textarea[name]").evaluateAll(es=>es.length===7&&es.every(e=>e.matches(":disabled"))));
assert.equal(await f.locator("[data-brief-compose]").isDisabled(),true);
assert.equal(await f.locator("[data-brief-preview]").getAttribute("name"),null);
assert(await f.locator('.brief-nojs a[href^="https://wa.me/"]').isVisible()); assert(await f.locator('.brief-nojs a[href^="tel:"]').isVisible());
const before=leaks.length;
/* Forced native submission can cause an empty local GET; no synthetic values may enter any request. */
await f.evaluate((form,value)=>{ for(const e of form.elements) if(e.name&&e.tagName!=="SELECT") e.value=value; setTimeout(()=>form.requestSubmit(),0); },nonce);
await p.waitForTimeout(250); assert.equal(leaks.length,before,"Brief values attempted in request");
} finally { dependencyStates.get(c).closing=true; await c.close(); }
});
}
}

async function genericFallback() {
await check("projects simulated attribute-only nonmodal fallback: native CSS, Escape and close",async()=>{
const c=await context({width:390,height:844});
await c.addInitScript(()=>{
Object.defineProperty(HTMLDialogElement.prototype,"showModal",{configurable:true,writable:true,value:undefined});
Object.defineProperty(HTMLDialogElement.prototype,"open",{configurable:true,get:()=>undefined});
const nativeClose=HTMLDialogElement.prototype.close;
window.__qaFallbackCloseCalls=0;
HTMLDialogElement.prototype.close=function(){window.__qaFallbackCloseCalls++;return nativeClose.call(this);};
});
try {
const {p}=await open(c,"/projects.html");
assert.equal(await dependencyReason(p),"");
const trigger=p.locator(".real-video").first(),dialog=p.locator("#real-video-dialog"),close=p.locator("#real-video-close"),video=p.locator("#real-video-player");
for(const action of ["Escape","button"]) {
await trigger.click();await focused(p,close);
assert.equal(await dialog.getAttribute("aria-modal"),"false");
assert(await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return el.hasAttribute("open")&&!el.matches(":modal")&&getComputedStyle(el).display==="block"&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;}));
await poll(p,()=>/belum dapat dimuat/.test(document.querySelector("#real-video-status").textContent));
if(action==="Escape") {await shot(p,"projects-390-attribute-fallback.png");await p.keyboard.press("Escape");}
else await close.click();
await poll(p,()=>!document.querySelector("#real-video-dialog").hasAttribute("open"));await focused(p,trigger);
assert(await video.evaluate(el=>el.paused&&!el.hasAttribute("src")));
}
assert.equal(await p.evaluate(()=>window.__qaFallbackCloseCalls),0,"Fallback called native close");
assert.equal(await dependencyReason(p),"");
} finally {dependencyStates.get(c).closing=true;await c.close();}
});
}

(async()=>{
await fs.mkdir(out,{recursive:true});
try { browser=await chromium.launch({headless:true}); await pages(); await inertForms(); await genericFallback(); }
catch(e) { report("native runner setup/execution","FAIL",e.stack||e.message); }
finally {
if(browser) await browser.close();
report("production media playback","NOT RUN","MP4 requests mocked 404; only native modal/error plumbing tested.");
await check("all expected CSS/JS loaded without unexpected failures",async()=>assert.equal(unavailable.size,0,JSON.stringify([...unavailable])));
await check("no attempted brief/external form/WA leakage",async()=>assert.equal(leaks.length,0,JSON.stringify(leaks)));
await check("no uncaught page runtime errors",async()=>assert.equal(errors.length,0,JSON.stringify(errors)));
const reportData={runtime:{playwright:require("playwright/package.json").version,chromium:browser ? browser.version() : "not launched"},candidateSha:process.env.QA_CANDIDATE_SHA||process.env.GITHUB_SHA||"UNKNOWN",browser:"Chromium native cloud",baseOrigin:base.origin,results,artifacts,unavailable:[...unavailable],blocked,leaks,errors,visualReview:"PENDING"};
await fs.writeFile(path.join(out,"results.json"),JSON.stringify(reportData,null,2));
console.log(JSON.stringify({passed:results.filter(r=>r.status==="PASS").length,failed:results.filter(r=>r.status==="FAIL").length,notRun:results.filter(r=>r.status==="NOT RUN").length,artifactDir:out},null,2));
if(results.some(r=>r.status==="FAIL"||r.status==="NOT RUN"&&r.name!=="production media playback")) process.exitCode=1;
}
})();
