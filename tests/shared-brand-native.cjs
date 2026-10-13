/* Focused SharedBrand native QA. Cloud loopback only; no production writer. */
"use strict";
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
const path = require("node:path");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
function loopback(value,label) {
 const url=new URL(value);
 assert(["http:","https:"].includes(url.protocol)&&["127.0.0.1","localhost","[::1]"].includes(url.hostname)&&!url.username&&!url.password,label+" must be isolated loopback");
 return url;
}
const base=loopback(process.env.QA_BASE_URL||"","QA_BASE_URL");
const baseline=loopback(process.env.QA_BASELINE_URL||"","QA_BASELINE_URL");
const out=path.resolve(process.env.QA_ARTIFACT_DIR||"artifacts/shared-brand");
const repo=path.resolve(process.env.QA_REPO_DIR||".");
const configPath=path.join(repo,"config/site-brand.json");
const samples=[
 ["utama","/"],["portfolio","/projects.html"],["root-guide","/panduan.html"],["layanan","/layanan/neon-box"],
 ["wilayah","/kota/makassar"],["produk","/produk/neon-box-bulat"],["panduan","/panduan/memilih-neon-box"],
 ["tutorial","/panduan/menentukan-tugas-utama-papan-nama-sebelum-memilih-bahan"],["topik","/topik/brief"],
 ["alat","/alat/susun-brief"],["toko","/toko/toko-1"],["informasi","/bantuan/privasi-pengunjung"]
];
const results=[],artifacts=[],violations=[],unavailable=[],runtimeErrors=[],blocked=[];
const nonce="SYNTHETIC_SHARED_BRAND_QA_DO_NOT_SEND";
let browser,version;
function report(name,status,detail) {results.push({name,status,...(detail?{detail:String(detail)}:{})});}
async function check(name,fn) {try{await fn();report(name,"PASS");}catch(e){report(name,"FAIL",e.message);}}
const analytics=u=>/^(www\.googletagmanager\.com|www\.google-analytics\.com|region\d+\.google-analytics\.com)$/.test(u.hostname);
async function context(origin,viewport,js=true) {
 const c=await browser.newContext({viewport,javaScriptEnabled:js,serviceWorkers:"block"});
 await c.routeWebSocket("**/*",ws=>{violations.push({category:"websocket"});ws.close();});
 await c.route("**/*",route=>{
  const req=route.request(),u=new URL(req.url()),method=req.method(),body=req.postData()||"";
  if((req.url()+" "+body).includes(nonce))violations.push({category:"synthetic-data-request",method,path:u.pathname});
  const snapshotRead=u.origin===origin.origin&&["GET","HEAD"].includes(method)&&!u.search&&["/assets/marketing-20261006/search-index.json","/portfolio.php"].includes(u.pathname);
  if(snapshotRead&&u.pathname==="/portfolio.php")return route.fulfill({status:200,contentType:"application/json",body:"[]"});
  if(u.origin!==origin.origin||!["GET","HEAD"].includes(method)||(["xhr","fetch","eventsource"].includes(req.resourceType())&&!snapshotRead)) {
   blocked.push({path:u.pathname,method,expected:analytics(u)});
   if(!analytics(u))violations.push({category:"unexpected-network",method,path:u.pathname});
   return route.abort("blockedbyclient");
  }
  if(/\/assets\/portfolio-real\/videos\/.*\.mp4$/.test(u.pathname))return route.fulfill({status:404,contentType:"text/plain",body:"QA deliberate unavailable media"});
  return route.continue();
 });
 return c;
}
async function open(c,origin,url) {
 const p=await c.newPage();p.setDefaultTimeout(5000);
 p.on("pageerror",e=>runtimeErrors.push({origin:origin===base?"candidate":"baseline",path:url,error:e.message}));
 p.on("response",r=>{if(r.status()>=400&&["script","stylesheet","image"].includes(r.request().resourceType()))unavailable.push({path:new URL(r.url()).pathname,status:r.status()});});
 const r=await p.goto(new URL(url,origin).href,{waitUntil:"load",timeout:15000});
 assert(r&&r.status()===200,"Expected HTTP200 for "+url);
 return p;
}
async function signature(p) {
 return p.evaluate(()=>{
  const main=document.querySelector("main");if(!main)throw Error("No main element");
  const meta=Array.from(document.querySelectorAll("head meta")).map(e=>Array.from(e.attributes).map(a=>[a.name,a.value]));
  const forms=Array.from(main.querySelectorAll("form,input,select,textarea,button")).map(e=>({tag:e.tagName,attrs:Array.from(e.attributes).filter(a=>a.name!=="class").map(a=>[a.name,a.value])}));
  return {
   title:document.title,meta,canonical:document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
   schemas:Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(e=>JSON.parse(e.textContent)),
   mainText:main.textContent.replace(/\s+/g," ").trim(),
   headings:Array.from(main.querySelectorAll("h1,h2,h3,h4,h5,h6")).map(e=>[e.tagName,e.textContent.replace(/\s+/g," ").trim()]),
   links:Array.from(main.querySelectorAll("[href]")).map(e=>[e.tagName,e.getAttribute("href")]),
   ids:Array.from(main.querySelectorAll("[id]")).map(e=>e.id),
   media:Array.from(main.querySelectorAll("img,video,source")).map(e=>({tag:e.tagName,attrs:Array.from(e.attributes).map(a=>[a.name,a.value])})),
   forms
  };
 });
}
async function focused(p,selector) {
 const l=p.locator(selector);await p.waitForFunction(el=>el===document.activeElement,await l.elementHandle(),{timeout:5000});
}
async function settle(p) {await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function shot(p,name) {
 const file=path.join(out,name+".png");await p.screenshot({path:file});artifacts.push(file);
 const metadata=await p.evaluate(()=>({viewport:{width:innerWidth,height:innerHeight},active:{tag:document.activeElement?.tagName,id:document.activeElement?.id},elements:Array.from(document.querySelectorAll(".site-header,.site-header .brand img,.site-footer .brand img,h1,.page-intro p,.menu-toggle")).map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return{tag:e.tagName,id:e.id,color:s.color,background:s.backgroundColor,font:s.fontFamily,rect:{top:r.top,left:r.left,width:r.width,height:r.height},currentSrc:e.currentSrc||null};})}));
 const target=path.join(out,name+".json");await fs.writeFile(target,JSON.stringify(metadata,null,2)+"\n");artifacts.push(target);
}
async function cssGate() {
 const css=await fs.readFile(path.join(repo,"public_html/assets/ui/design-system.css"),"utf8");
 assert.equal(crypto.createHash("sha256").update(css).digest("hex"),"66a28499c514cb36c4e43ef1bad89782f963a5bf93146fa81f7370f7e85fef74");
 assert.equal(Buffer.byteLength(css),12437);assert(!/&(?:gt|lt|amp);/.test(css),"Transport entities in CSS");
 const c=await browser.newContext();const p=await c.newPage();
 try {
  const result=await p.evaluate(css=>{
   const stripped=css.replace(/\/\*[\s\S]*?\*\//g,""),preludes=Array.from(stripped.matchAll(/([^{}]+)\{/g),m=>m[1].trim());
   const selectors=preludes.filter(s=>!s.startsWith("@"));
   if(!selectors.every(s=>CSS.supports("selector("+s+")")))throw Error("Authored selector rejected");
   const sheet=new CSSStyleSheet();sheet.replaceSync(css);
   const flatten=rules=>Array.from(rules).reduce((n,r)=>n+(r.type===CSSRule.STYLE_RULE?1:r.cssRules?flatten(r.cssRules):0),0);
   return{authored:selectors.length,parsed:flatten(sheet.cssRules)};
  },css);
  assert(result.authored>60);assert.equal(result.parsed,result.authored,"Browser silently discarded an authored CSS rule");
 } finally {await c.close();}
}
async function shell(p,config) {
 assert(await p.locator("body").evaluate(e=>e.classList.contains("kan-site")&&e.classList.contains("kan-nav-ready")));
 assert.equal(await p.locator(".site-header").count(),1);assert.equal(await p.locator(".site-footer").count(),1);
 assert.equal(await p.locator("#site-nav").count(),1);
 const logo=config.brand.logo_primary;
 for(const selector of [".site-header .brand img",".site-footer .footer-brand img"]) {
  const img=p.locator(selector);await img.scrollIntoViewIfNeeded();await img.evaluate(e=>e.decode());
  assert.equal(await img.getAttribute("src"),logo.path);assert.equal(await img.getAttribute("width"),String(logo.width));assert.equal(await img.getAttribute("height"),String(logo.height));assert.equal(await img.getAttribute("alt"),logo.alt);
  assert(await img.evaluate((e,ratio)=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e),b=e.closest(".brand");return e.complete&&e.naturalWidth>0&&Math.abs(r.width/r.height-ratio)<.015&&r.left>=-1&&r.right<=innerWidth+1&&s.objectFit==="contain"&&s.filter==="none"&&!!b;},logo.width/logo.height),"Logo geometry/loaded pixels");
 }
 const colors=config.colors;
 assert(await p.evaluate(colors=>{
  const toRgb=color=>{const e=document.createElement("span");e.style.color=color;document.body.append(e);const rgb=getComputedStyle(e).color;e.remove();return rgb;};
  const s=getComputedStyle(document.body);
  return s.color===toRgb(colors.text)&&s.backgroundColor===toRgb(colors.background);
 },colors),"Body does not consume shared tokens");
 const main=p.locator("main");assert(await main.isVisible());
 assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),"Horizontal overflow");
}
async function navigation(p,viewport) {
 const menu=".menu-toggle",summary=".nav-services > summary";
 await p.evaluate(()=>scrollTo(0,0));await settle(p);
 if(viewport.width<=1020) {
  assert(await p.locator(menu).isVisible());assert.equal(await p.locator("#site-nav").isVisible(),false);
  await p.locator(menu).focus();await p.keyboard.press("Space");assert.equal(await p.locator(menu).getAttribute("aria-expanded"),"true");assert(await p.locator("#site-nav").isVisible());
  await p.locator(summary).focus();await p.keyboard.press("Enter");assert(await p.locator(".nav-services").evaluate(e=>e.open));
  await p.keyboard.press("Escape");await focused(p,menu);assert.equal(await p.locator(menu).getAttribute("aria-expanded"),"false");
 } else {
  assert.equal(await p.locator(menu).isVisible(),false);
  await p.locator(summary).focus();await p.keyboard.press("Enter");assert(await p.locator(".nav-services").evaluate(e=>e.open));
  await p.keyboard.press("Escape");await focused(p,summary);assert.equal(await p.locator(".nav-services").evaluate(e=>e.open),false);
  try {
   await p.locator("#site-nav > a[href]").first().focus();await p.setViewportSize({width:1020,height:844});await focused(p,menu);
   await p.setViewportSize({width:1021,height:720});await focused(p,summary);
  } finally {await p.setViewportSize(viewport);}
 }
 await p.evaluate(()=>scrollTo(0,0));await p.keyboard.press("Tab");
 const skip=p.locator(".skip-link");
 await skip.focus();await p.keyboard.press("Enter");await focused(p,"#main");
}
async function modules(p,url) {
 if(await p.locator(".knowledge-search").count()) {
  await p.waitForFunction(()=>/halaman tersedia/.test(document.querySelector("#search-status").textContent)&&document.querySelectorAll("#knowledge-results a").length>0,null,{timeout:5000});
  assert.equal(await p.locator(".knowledge-search [name]").count(),0,"Read-only search must not submit named form data");
 }
 if(url==="/projects.html") {
  for(const [category,count] of [["retail",2],["worship",1],["all",10]]) {
   await p.locator('.real-filter[data-filter="'+category+'"]').click();
   assert.equal(await p.locator(".real-card:not([hidden])").count(),count);
   assert.equal(await p.locator('.real-filter[aria-pressed="true"]').count(),1);
  }
  const trigger=p.locator("#cimb-niaga .real-video");await trigger.click();await focused(p,"#real-video-close");
  await p.keyboard.press("Escape");await focused(p,"#cimb-niaga .real-video");
  assert(await p.locator("#real-video-player").evaluate(v=>v.paused&&!v.hasAttribute("src")));
 }
 if(url==="/"||url==="/projects.html") {
  const f=p.locator("form[data-brief-form]"),type=f.locator('select[name="type"]');
  await type.selectOption("Neon box");await f.locator("textarea[name=note]").fill(nonce);await f.locator("[data-brief-compose]").click();
  assert(await f.locator("[data-brief-output]").isVisible());assert((await f.locator("[data-brief-preview]").inputValue()).includes(nonce));
  await f.locator("textarea[name=note]").fill(nonce+"_edited");assert.equal(await f.locator("[data-brief-output]").isVisible(),false);
  await p.waitForFunction(()=>{const e=document.activeElement,h=document.querySelector(".site-header"),r=e.getBoundingClientRect(),s=getComputedStyle(e),ring=(parseFloat(s.outlineWidth)||0)+Math.max(0,parseFloat(s.outlineOffset)||0);return e.matches("form[data-brief-form] textarea[name=note]")&&r.top-ring>=h.getBoundingClientRect().bottom+8&&r.bottom+ring<=innerHeight-8;},null,{timeout:5000});
  assert.equal(await f.locator("[data-brief-whatsapp]").getAttribute("href"),null);
 }
 if(url==="/alat/susun-brief") {
  const f=p.locator(".utility-form");await f.locator("#tool-name").fill(nonce);await f.locator("#tool-product").fill("Synthetic signage");await f.locator("#tool-location").fill("Synthetic location");
  await f.locator('button[type="submit"]').click();assert(await f.locator(".tool-result").isVisible());assert((await f.locator(".tool-result pre").textContent()).includes(nonce));
  await f.locator("#tool-name").fill(nonce+"_edited");assert.equal(await f.locator(".tool-result").isVisible(),false);
  assert(await p.evaluate(()=>typeof KanTools.calc==="function"&&KanTools.calc("luas-panel",{w:"100",h:"100",qty:"2"}).values.area===2));
 }
}
async function noJs(url) {
 const c=await context(base,{width:390,height:844},false);
 try {
  const p=await open(c,base,url);
  assert.equal(await p.locator(".menu-toggle").isVisible(),false);assert(await p.locator("#site-nav").isVisible());
  assert.equal(await p.locator("body").evaluate(e=>e.classList.contains("kan-nav-ready")),false);
  assert(await p.locator("#site-nav > a[href]").first().evaluate(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;}));
  if(url==="/"||url==="/projects.html")assert(await p.locator("form[data-brief-form] input[name],form[data-brief-form] select[name],form[data-brief-form] textarea[name]").evaluateAll(es=>es.length===7&&es.every(e=>e.matches(":disabled"))));
  if(url==="/alat/susun-brief")assert(await p.locator("[data-client-only]").evaluate(e=>e.disabled));
 } finally {await c.close();}
}
(async()=>{
 await fs.mkdir(out,{recursive:true});
 try {
  const config=JSON.parse(await fs.readFile(configPath,"utf8"));browser=await chromium.launch({headless:true});version=await browser.version();
  await check("canonical CSS parses all selectors in Chromium",cssGate);
  const signatures=new Map();
  const bc=await context(baseline,{width:1280,height:720});
  try {for(const [family,url] of samples){const p=await open(bc,baseline,url);signatures.set(url,await signature(p));await p.close();}} finally {await bc.close();}
  for(const viewport of [{width:390,height:844},{width:1280,height:720}])for(const [family,url] of samples) {
   const name=family+"-"+viewport.width,c=await context(base,viewport);
   try {
    const p=await open(c,base,url);
    await check(name+" content and metadata invariants",async()=>assert.deepEqual(await signature(p),signatures.get(url)));
    await check(name+" common logo/tokens/layout",()=>shell(p,config));
    await p.evaluate(()=>scrollTo(0,0));await settle(p);await check(name+" initial screenshot evidence",()=>shot(p,name+"-header"));
    await check(name+" keyboard menu/Escape/resize/skip link",()=>navigation(p,viewport));
    if(["/","/projects.html","/alat/susun-brief"].includes(url)||await p.locator(".knowledge-search").count())await check(name+" changed dependency module behavior",()=>modules(p,url));
    await p.locator(".site-footer").scrollIntoViewIfNeeded();await check(name+" footer screenshot evidence",()=>shot(p,name+"-footer"));
   } catch(e){report(name+" setup","FAIL",e.message);}finally{await c.close();}
  }
  for(const [family,url] of samples)await check(family+" mobile no-JS navigation",()=>noJs(url));
  await check("no required local dependency unavailable",async()=>assert.equal(unavailable.length,0,JSON.stringify(unavailable)));
  await check("no candidate runtime error",async()=>assert.equal(runtimeErrors.filter(e=>e.origin==="candidate").length,0,JSON.stringify(runtimeErrors.filter(e=>e.origin==="candidate"))));
  await check("no unexpected network or synthetic data request",async()=>assert.equal(violations.length,0,JSON.stringify(violations)));
 } catch(e){report("focused runner setup","FAIL",e.message);}
 finally {
  if(browser)await browser.close().catch(e=>report("browser cleanup","FAIL",e.message));
  const reportData={candidateSha:process.env.QA_CANDIDATE_SHA||"UNKNOWN",baselineSha:"dd31d7305d1571b4fde960ed0b942135a88388a1",runtime:{playwright:require("playwright/package.json").version,chromium:version||null},results,artifacts,blocked,violations,unavailable,runtimeErrors,visualReview:"PENDING",limitations:["Screenshots are generated evidence; parent must inspect pixels for visual acceptance.","MP4 error context only; existing reviewed real-media proof remains separate.","No production hosting, API/config/auth source, settings, form POST, WA navigation or CMS writer used.","Legacy /portfolio.php requests use a synthetic empty JSON list; existing rendered cards are retained. Search uses the exact local public search-index snapshot."]};
  await fs.writeFile(path.join(out,"results.json"),JSON.stringify(reportData,null,2)+"\n");
  console.log(JSON.stringify({passed:results.filter(r=>r.status==="PASS").length,failed:results.filter(r=>r.status==="FAIL").length,diagnostics:results.filter(r=>r.status!=="PASS"),artifactDir:out},null,2));
  if(results.some(r=>r.status!=="PASS"))process.exitCode=1;
 }
})();
