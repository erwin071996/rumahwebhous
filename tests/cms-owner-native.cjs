/* Isolated UI browser smoke. API/session responses below are synthetic, never hosting auth. */
"use strict";
const {chromium}=require("playwright");
const fs=require("node:fs/promises"),path=require("node:path"),assert=require("node:assert/strict");
const repo=path.resolve(__dirname,".."),out=path.resolve(process.env.QA_ARTIFACT_DIR||"artifacts/cms-owner-native");
const origin="https://127.0.0.1:9443",results=[],artifacts=[],unexpected=[],errors=[];
const clone=value=>JSON.parse(JSON.stringify(value));
const photos=[{id:"a",label:"Neon box bulat",src:"/assets/refresh-20261006/produk-fcf95321686c-640.webp"},{id:"b",label:"Neon box akrilik",src:"/assets/refresh-20261006/produk-39db8e80530c-640.webp"}];
const config={service:{title:"Neon Box",summary:"Ringkasan publik sintetis untuk uji",cover:"b"},media:photos,publicationEnabled:false};
const files=new Map([
["/cms-owner/",["cms/owner-ui.html","text/html"]],
["/cms-owner/owner-ui.css",["cms/owner-ui.css","text/css"]],
["/cms-owner/owner-ui.js",["cms/owner-ui.js","application/javascript"]],
["/assets/ui/brand-tokens.css",["public_html/assets/ui/brand-tokens.css","text/css"]],
...photos.map(item=>[item.src,["public_html"+item.src,"image/webp"]])
]);
let browser;
async function check(name,fn){try{await fn();results.push({name,status:"PASS"});}catch(error){results.push({name,status:"FAIL",detail:error.message});}}
async function context(viewport,js=true,denied=false){
const c=await browser.newContext({viewport,javaScriptEnabled:js,serviceWorkers:"block"});
await c.routeWebSocket("**/*",socket=>{unexpected.push({category:"WebSocket",path:new URL(socket.url()).pathname});socket.close({code:1008,reason:"QA isolation"});});
let state={revision:0,status:"empty",snapshot:null},review=false;
const csrf="synthetic_csrf_".padEnd(64,"x"),calls=[];
await c.route("**/*",async route=>{
const request=route.request(),url=new URL(request.url());
if(url.origin!==origin){unexpected.push({category:"External request",method:request.method(),path:url.pathname});return route.abort("blockedbyclient");}
if(url.pathname==="/cms-owner/endpoint.php"){
calls.push({method:request.method(),query:url.search,action:null});
let reply,status=200;
if(denied){reply={ok:false,category:"Access"};status=401;}
else if(request.method()==="GET"&&url.search==="?action=load")reply={ok:true,csrf,state:clone(state),config};
else if(request.method()==="POST"&&!url.search){
const body=request.postDataJSON(),payload=body?.payload;calls.at(-1).action=body?.action;
if(request.headers()["x-csrf-token"]!==csrf){reply={ok:false,category:"Csrf"};status=403;}
else if(!payload||payload.expected_revision!==state.revision){reply={ok:false,category:"Conflict"};status=409;}
else if(body.action==="save"){state={revision:state.revision+1,status:"draft",snapshot:clone(payload.snapshot)};review=false;reply={ok:true,state:clone(state)};}
else if(body.action==="preview"){review=true;reply={ok:true,state:clone(state)};}
else if(body.action==="approve"){if(!review){reply={ok:false,category:"Conflict"};status=409;}else{state.status="approved";reply={ok:true,state:clone(state)};}}
else {reply={ok:false,category:"Unavailable"};status=503;}
}else{reply={ok:false,category:"Invalid"};status=400;}
return route.fulfill({status,contentType:"application/json",headers:{"Cache-Control":"no-store"},body:JSON.stringify(reply)});
}
const file=files.get(url.pathname);
if(!file||url.search||!["GET","HEAD"].includes(request.method())){unexpected.push({category:"Unexpected local request",path:url.pathname,method:request.method()});return route.abort("blockedbyclient");}
return route.fulfill({status:200,contentType:file[1],headers:{"Cache-Control":"no-store"},body:await fs.readFile(path.join(repo,file[0]))});
});
const p=await c.newPage();p.setDefaultTimeout(5000);p.on("pageerror",error=>errors.push(error.message));await p.goto(origin+"/cms-owner/",{waitUntil:"load"});
return {c,p,calls,otherSessionSave(){state={...state,revision:state.revision+1,status:"draft",snapshot:{...state.snapshot,fields:{...state.snapshot.fields,title:"Perubahan sesi sintetis lain"}}};review=false;}};
}
(async()=>{
await fs.mkdir(out,{recursive:true});
try{
browser=await chromium.launch({headless:true});
for(const viewport of [{width:390,height:844},{width:1280,height:900}]){
const {c,p,calls,otherSessionSave}=await context(viewport);
await check(viewport.width+" initial real HTML binds and uses two approved assets",async()=>{
await p.waitForFunction(()=>!document.querySelector("#owner-fields").disabled);
assert.equal(await p.locator("#owner-connection").textContent(),"Terhubung ke sesi Owner.");
assert.equal(await p.locator("#owner-title").inputValue(),"Neon Box");assert.equal(await p.locator("#owner-media li").count(),2);
assert.equal(await p.locator("#owner-cover-b").isChecked(),true);assert.equal(await p.locator("#owner-rights-b").isChecked(),false);
for(const img of await p.locator("#owner-media img").all()){await img.scrollIntoViewIfNeeded();await img.evaluate(el=>el.decode());}
assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
assert.equal(await p.locator("#owner-request").isDisabled(),true);
});
await check(viewport.width+" keyboard save load review approve and conflict retain edits",async()=>{
await p.locator("#owner-rights-b").check();await p.locator("#owner-title").fill("Judul uji Owner");
await p.locator("#owner-save").focus();await p.keyboard.press("Enter");
await p.waitForFunction(()=>document.querySelector("#owner-draft-state").textContent.includes("tersimpan privat"));
await p.locator("#owner-load").focus();await p.keyboard.press("Enter");await p.waitForFunction(()=>!document.querySelector("#owner-save").disabled);
assert.equal(await p.locator("#owner-title").inputValue(),"Judul uji Owner");assert.equal(await p.locator("#owner-cover-b").isChecked(),true);
await p.locator("#owner-preview").focus();await p.keyboard.press("Enter");await p.waitForFunction(()=>!document.querySelector("#owner-output").hidden);
assert.equal(await p.locator("#owner-preview-heading").evaluate(el=>el===document.activeElement),true);assert.equal(await p.locator("#owner-preview-title").textContent(),"Judul uji Owner");
await p.locator("#owner-approve").focus();await p.keyboard.press("Enter");await p.waitForFunction(()=>document.querySelector("#owner-review-state").textContent.includes("telah disetujui"));
assert.equal(await p.locator("#owner-approve").isDisabled(),true);
assert.equal(await p.locator("#owner-request").isDisabled(),true);
otherSessionSave();await p.locator("#owner-preview").focus();await p.keyboard.press("Enter");
await p.waitForFunction(()=>document.querySelector("#owner-status").textContent.includes("Revisi server telah berubah"));
assert.equal(await p.locator("#owner-title").inputValue(),"Judul uji Owner");assert.equal(await p.locator("#owner-preview").isDisabled(),true);assert.equal(await p.locator("#owner-request").isDisabled(),true);
await p.locator("#owner-load").click();assert.equal(await p.locator("#owner-discard").isVisible(),true);
assert.equal(await p.locator("#owner-title").inputValue(),"Judul uji Owner");await p.locator("#owner-discard").click();
await p.waitForFunction(()=>document.querySelector("#owner-title").value==="Perubahan sesi sintetis lain");
assert(calls.every(call=>call.method!=="GET"||call.query==="?action=load"));assert(!calls.some(call=>call.action==="request-publication"));
});
await check(viewport.width+" screenshot captured, visual review pending",async()=>{const file=path.join(out,"owner-"+viewport.width+".png");await p.screenshot({path:file,fullPage:true});artifacts.push(file);});
await c.close();
}
await check("Synthetic denied session keeps UI mutations disabled",async()=>{const {c,p}=await context({width:390,height:844},true,true);try{await p.waitForFunction(()=>document.querySelector("#owner-status").textContent.includes("Sesi Owner"));assert.equal(await p.locator("#owner-title").isDisabled(),true);assert.equal(await p.locator("#owner-save").isDisabled(),true);assert.equal(await p.locator("#owner-request").isDisabled(),true);}finally{await c.close();}});
await check("No-JS controls remain inert without query or API calls",async()=>{const {c,p,calls}=await context({width:390,height:844},false);try{assert.equal(await p.locator("#owner-title").isDisabled(),true);assert.equal(await p.locator("#owner-save").isDisabled(),true);await p.locator("#owner-load").focus();await p.keyboard.press("Enter");await p.keyboard.press("Space");assert.equal(p.url(),origin+"/cms-owner/");assert.equal(calls.length,0);}finally{await c.close();}});
await check("All requests stayed in synthetic local fixture and no page errors",async()=>{assert.equal(unexpected.length,0);assert.equal(errors.length,0);});
}catch(error){results.push({name:"Runner setup",status:"FAIL",detail:error.message});}
finally{
if(browser)await browser.close();
const report={candidateSha:process.env.GITHUB_SHA||"UNKNOWN",fixture:"Synthetic API/session, authoritative CMS UI and actual two checkout photos; no hosting auth/persistence/publisher claim",results,artifacts,unexpected,errors,visualReview:"PENDING"};
await fs.writeFile(path.join(out,"results.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({passed:results.filter(r=>r.status==="PASS").length,failed:results.filter(r=>r.status==="FAIL").length,diagnostics:results.filter(r=>r.status==="FAIL"),artifactDir:out},null,2));
if(results.some(r=>r.status==="FAIL"))process.exitCode=1;
}
})();
