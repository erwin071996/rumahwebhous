/* Real MP4 fixture QA. Separate from native-qa.cjs deliberate 404 coverage. */
"use strict";
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");
const base = new URL(process.env.QA_BASE_URL || "");
if (!["127.0.0.1","localhost","[::1]"].includes(base.hostname) || base.username || base.password || !["http:","https:"].includes(base.protocol)) throw Error("Loopback QA_BASE_URL required");
const fixture = path.resolve(process.env.QA_FIXTURE_DIR || "artifacts/native-qa/fixture");
const out = path.resolve(process.env.QA_ARTIFACT_DIR || "artifacts/native-qa","media");
const results=[], evidence=[], blocked=[], leaks=[], runtimeErrors=[], responses=[];
let browser, browserServer, ownedChild, browserVersion=null;
async function bounded(operation,label,ms=5000) { let timer; try { return await Promise.race([Promise.resolve().then(operation),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+" timeout")),ms);})]); } finally { clearTimeout(timer); } }
async function checkpoint(status) { await fs.writeFile(path.join(out,"media-results.json"),JSON.stringify({candidateSha:process.env.QA_CANDIDATE_SHA||"UNKNOWN",status,results,evidence,responses,blocked,leaks,runtimeErrors,runtime:{playwright:require("playwright/package.json").version,chromium:browserVersion}},null,2)+"\n"); }
const digest = b => crypto.createHash("sha256").update(b).digest("hex");
const mediaPath = /^\/assets\/portfolio-real\/videos\/[a-z0-9-]+\.mp4$/;
async function manifest() {
const m=JSON.parse(await fs.readFile(process.env.QA_MEDIA_MANIFEST || "tests/native-media-manifest.json","utf8"));
assert.equal(m.schemaVersion,1);
assert.equal(m.origin,"https://www.3dkanadvertising.store");
assert.equal(m.files?.length,5,"Exactly five independently verified public MP4 entries required");
assert.equal(new Set(m.files.map(e=>e.path)).size,5);
for(const e of m.files) {
assert(mediaPath.test(e.path)&&e.mime==="video/mp4"&&Number.isInteger(e.bytes)&&e.bytes>0&&e.bytes<=64000000&&/^[a-f0-9]{64}$/.test(e.sha256),"Invalid verified MP4 entry");
const file=path.resolve(fixture,"."+e.path),real=await fs.realpath(file),stat=await fs.stat(real);
assert(real.startsWith(fixture+path.sep)&&stat.isFile()&&stat.size===e.bytes,"Missing/unsafe or mismatched fixture MP4");
assert.equal(digest(await fs.readFile(real)),e.sha256,"Verified MP4 bytes changed: "+e.path);
}
return m;
}
function analytics(u,req) {
return u.protocol==="https:"&&!u.port&&["GET","HEAD"].includes(req.method())&&/^(www\.googletagmanager\.com|www\.google-analytics\.com|region[0-9]+\.google-analytics\.com)$/.test(u.hostname)&&(["/gtag/js","/gtm.js","/g/collect","/collect"].includes(u.pathname));
}
async function context(viewport,files) {
const c=await browser.newContext({viewport,serviceWorkers:"block"});
await c.routeWebSocket("**/*",ws=>{leaks.push({category:"WebSocket",url:ws.url()});ws.close({code:1008,reason:"QA isolation"});});
await c.route("**/*",route=>{
const req=route.request(),u=new URL(req.url());
if(u.origin!==base.origin||!["GET","HEAD"].includes(req.method())||["xhr","fetch","eventsource"].includes(req.resourceType())) {
const expected=analytics(u,req);
blocked.push({path:u.pathname,method:req.method(),expected});
if(!expected)leaks.push({path:u.pathname,method:req.method(),category:"Unexpected request"});
return route.abort("blockedbyclient");
}
if((req.resourceType()==="media"||/\.mp4$/i.test(u.pathname))&&(!files.some(e=>e.path===u.pathname)||u.search||u.hash||u.username||u.password)) {
leaks.push({path:u.pathname,category:"Unverified media request"});return route.abort("blockedbyclient");
}
return route.continue();
});
c.on("response",r=>{
const req=r.request(),u=new URL(r.url());
if(mediaPath.test(u.pathname))responses.push({path:u.pathname,status:r.status(),mime:(r.headers()["content-type"]||"").split(";")[0],range:req.headers().range||null,contentRange:r.headers()["content-range"]||null});
});
return c;
}
async function state(p) {
return p.locator("#real-video-player").evaluate(v=>({
paused:v.paused,src:v.getAttribute("src"),currentSrc:v.currentSrc,time:v.currentTime,duration:Number.isFinite(v.duration)?v.duration:null,
width:v.videoWidth,height:v.videoHeight,readyState:v.readyState,networkState:v.networkState,muted:v.muted,volume:v.volume,
error:v.error?{code:v.error.code,message:v.error.message}:null,visibility:document.visibilityState,
mp4Support:v.canPlayType("video/mp4"),audioTracks:v.audioTracks?.length??null,audioDecodedBytes:v.webkitAudioDecodedByteCount??null,
probe:v.__mediaProbe?{kind:v.__mediaProbe.kind,advances:v.__mediaProbe.advances,events:v.__mediaProbe.events}:null,
status:document.querySelector("#real-video-status").textContent
}));
}
async function probe(p,expected) {
await p.locator("#real-video-player").evaluate((v,url)=>{
if(v.__mediaCancel)v.__mediaCancel();
const q={active:true,kind:typeof v.requestVideoFrameCallback==="function"?"video-frame-callback":typeof v.getVideoPlaybackQuality==="function"?"playback-quality":"unsupported",advances:0,last:-1,events:[]};
v.__mediaProbe=q;
const event=e=>{if(q.events.length<60)q.events.push({type:e.type,time:v.currentTime,error:v.error?.code||null});};
const names=["loadedmetadata","playing","pause","error","emptied","stalled","ended"];
names.forEach(n=>v.addEventListener(n,event));
let id;
const frame=(now,metadata)=>{
if(!q.active)return;
if(v.currentSrc===url&&metadata.mediaTime>q.last){if(q.last>=0)q.advances++;q.last=metadata.mediaTime;}
id=v.requestVideoFrameCallback(frame);
};
if(q.kind==="video-frame-callback")id=v.requestVideoFrameCallback(frame);
v.__mediaCancel=()=>{q.active=false;if(id!==undefined&&v.cancelVideoFrameCallback)v.cancelVideoFrameCallback(id);names.forEach(n=>v.removeEventListener(n,event));};
},expected);
}
async function progress(p,expected) {
const baseline=await p.locator("#real-video-player").evaluate(v=>{
const q=v.__mediaProbe,quality=q?.kind==="playback-quality"?v.getVideoPlaybackQuality():null;
return {start:v.currentTime,frames:q?.kind==="video-frame-callback"?q.advances:quality?quality.totalVideoFrames-quality.droppedVideoFrames:null};
});
await p.waitForFunction(({url,start,frames})=>{
const v=document.querySelector("#real-video-player"),q=v.__mediaProbe,quality=q?.kind==="playback-quality"?v.getVideoPlaybackQuality():null;
const current=q?.kind==="video-frame-callback"?q.advances:quality?quality.totalVideoFrames-quality.droppedVideoFrames:null;
return v.currentSrc===url&&!v.paused&&v.readyState>=2&&!v.error&&v.currentTime>=start+.25&&frames!==null&&current!==null&&current-frames>=2;
},{url:expected,...baseline},{timeout:6000});
}
async function cleanup(p,trigger) {
await p.waitForFunction(()=>{const d=document.querySelector("#real-video-dialog"),v=document.querySelector("#real-video-player");return !d.hasAttribute("open")&&v.paused&&!v.hasAttribute("src")&&v.currentSrc===""&&v.readyState===0;},null,{timeout:2000});
await p.waitForFunction(el=>document.activeElement===el,await trigger.elementHandle(),{timeout:2000});
const first=await state(p);
const quiet=await p.locator("#real-video-player").evaluate(v=>new Promise(resolve=>{
let violation=null,samples=0;
const sample=()=>{samples++;if(!violation&&(!v.paused||v.hasAttribute("src")||v.currentSrc!==""))violation={paused:v.paused,src:v.getAttribute("src"),currentSrc:v.currentSrc,time:v.currentTime};};
const names=["play","playing","loadedmetadata"];names.forEach(n=>v.addEventListener(n,sample));
const timer=setInterval(sample,25);sample();setTimeout(()=>{clearInterval(timer);names.forEach(n=>v.removeEventListener(n,sample));sample();resolve({samples,violation});},1000);
}));
const last=await state(p);
assert.equal(quiet.violation,null,"Playback/source revived during settled close window: "+JSON.stringify(quiet.violation));
assert(last.paused&&!last.src&&!last.currentSrc&&Math.abs(last.time-first.time)<=.05,"Playback resumed after settled close");
assert(await p.locator("video").evaluateAll(es=>es.every(v=>v.paused)),"Another player continued");
if(first.audioDecodedBytes!==null&&last.audioDecodedBytes!==null)assert(last.audioDecodedBytes<=first.audioDecodedBytes,"Audio decode counter advanced after source unload");
await p.locator("#real-video-player").evaluate(v=>v.__mediaCancel?.());
return quiet;
}
async function classify(p,error,from,paths) {
const s=await state(p).catch(()=>null);
const bad=responses.slice(from).filter(r=>paths.includes(r.path)&&(![200,206].includes(r.status)||r.mime!=="video/mp4"));
const category=bad.length||s?.error?.code===2?"SOURCE_NETWORK_FAILURE":[3,4].includes(s?.error?.code)?"DECODE_OR_CODEC_FAILURE":!s?.error&&s?.mp4Support===""?"CODEC_CAPABILITY_UNREPORTED":"INCONCLUSIVE_TIMEOUT_OR_CONTROL_FAILURE";
return {category,message:error.message,state:s,badResponses:bad};
}
(async()=>{
await fs.mkdir(out,{recursive:true});
try {
const m=await manifest();
browserServer=await chromium.launchServer({headless:true,host:"127.0.0.1",timeout:30000});
ownedChild=browserServer.process();
browser=await chromium.connect(browserServer.wsEndpoint(),{timeout:10000});browserVersion=await browser.version();
for(const viewport of [{width:1280,height:720},{width:390,height:844}]) {
const c=await context(viewport,m.files),p=await c.newPage();p.setDefaultTimeout(10000);
p.on("pageerror",e=>runtimeErrors.push(e.message));
await p.goto(new URL("/projects.html",base).href,{waitUntil:"load"});
const domPaths=await p.locator(".real-video").evaluateAll(es=>[...new Set(es.map(e=>e.dataset.video))]);
assert.deepEqual([...domPaths].sort(),m.files.map(e=>e.path).sort(),"Manifest must cover all five real UI assets");
for(const entry of m.files) {
const name=viewport.width+" "+entry.path,trigger=p.locator('.real-video[data-video="'+entry.path+'"]').first(),url=new URL(entry.path,base).href,responseStart=responses.length;
try {
const cycles=[];
for(let cycle=0;cycle<2;cycle++) {
await probe(p,url);await trigger.click();
await p.waitForFunction(url=>{const v=document.querySelector("#real-video-player");return v.currentSrc===url&&v.readyState>=1&&Number.isFinite(v.duration)&&v.duration>0&&v.videoWidth>0&&v.videoHeight>0;},url,{timeout:12000});
assert.equal(await p.locator("#real-video-source").getAttribute("href"),entry.path);
assert(await p.locator("#real-video-dialog").evaluate(d=>d.matches(":modal")),"Actual native modal required");
let manual=false;
try {await progress(p,url);}
catch(error) {
const s=await state(p);
if(s.error||!s.paused||!/Tekan tombol putar/.test(s.status))throw error;
manual=true;await p.locator("#real-video-player").focus();await p.keyboard.press("Space");await progress(p,url);
}
const playing=await state(p);
assert(!playing.muted&&playing.volume>0,"Normal fixture test must not hide audio by muting");
if(cycle===0) {
const video=p.locator("#real-video-player");await video.evaluate(v=>v.pause());
const paused=await state(p);await p.waitForTimeout(750);const still=await state(p);
assert(still.paused&&Math.abs(still.time-paused.time)<=.05,"API pause did not stop time");
await video.evaluate(async v=>{let timer;try{await Promise.race([v.play(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error("API resume deadline 6000ms")),6000);})]);}finally{clearTimeout(timer);}});await progress(p,url);
const file=path.join(out,entry.path.split("/").pop()+"-"+viewport.width+".png");await video.screenshot({path:file});
}
if(cycle===0)await p.keyboard.press("Escape");else await p.locator("#real-video-close").click();
const quiet=await cleanup(p,trigger);cycles.push({cycle,manualNativeGesture:manual,playing,quiet,closed:await state(p)});
}
evidence.push({name,source:{bytes:entry.bytes,sha256:entry.sha256,mime:entry.mime},cycles,pauseResume:"HTMLMediaElement API; initial open through trusted UI click"});
results.push({name,status:"PASS"});
} catch(error) {
const detail=await classify(p,error,responseStart,[entry.path]);results.push({name,status:"FAIL",detail});
await p.keyboard.press("Escape").catch(()=>{});
await p.locator("#real-video-player").evaluate(v=>v.__mediaCancel?.()).catch(()=>{});
}
}
const adjacentStart=responses.length;
try {
const first=m.files[0],next=m.files[1],a=p.locator('.real-video[data-video="'+first.path+'"]').first(),b=p.locator('.real-video[data-video="'+next.path+'"]').first();
await a.click();await p.keyboard.press("Escape");await cleanup(p,a);
const url=new URL(next.path,base).href;await probe(p,url);await b.click();await progress(p,url);
assert.equal(await p.locator("#real-video-player").getAttribute("src"),next.path);
await p.locator("#real-video-close").click();await cleanup(p,b);
results.push({name:viewport.width+" immediate UI close / adjacent-file reopen",status:"PASS"});
} catch(error){results.push({name:viewport.width+" immediate UI close / adjacent-file reopen",status:"FAIL",detail:await classify(p,error,adjacentStart,[m.files[0].path,m.files[1].path])});}
await checkpoint("RUNNING");await bounded(()=>c.close(),"Context cleanup");
}
assert(responses.length>0&&responses.every(r=>[200,206].includes(r.status)&&r.mime==="video/mp4"),"Real fixture media response/MIME failed");
assert.equal(leaks.length,0,"Unexpected requests blocked");assert.equal(runtimeErrors.length,0,"Uncaught page error");
results.push({name:"Fixture response/MIME and network/runtime isolation",status:"PASS"});
} catch(error){results.push({name:"Media fixture setup or global gate",status:"FAIL",detail:{message:error.stack||error.message}});}
finally {
await checkpoint("CLEANUP PENDING");
if(browser){try{await bounded(()=>browser.close(),"Browser connection cleanup");}catch(error){results.push({name:"Browser cleanup",status:"FAIL",detail:{message:error.message}});}}
if(browserServer){try{await bounded(()=>browserServer.close(),"Owned browser server cleanup");}catch(error){results.push({name:"Owned browser cleanup",status:"FAIL",detail:{message:error.message}});if(ownedChild&&ownedChild.exitCode===null&&ownedChild.signalCode===null)ownedChild.kill("SIGKILL");}}
const report={candidateSha:process.env.QA_CANDIDATE_SHA||"UNKNOWN",runtime:{playwright:require("playwright/package.json").version,chromium:browserVersion},results,evidence,responses,blocked,leaks,runtimeErrors,
limitations:["Pinned local fixture proves decoding/playback of verified public bytes, not live network throughput or every browser/codec build.","Unmuted playback state, pause/unload/time stability and available decode counters were observed. No acoustic recording or claim that audio was heard.","API pause/resume is labeled separately from native-controls interaction. Deliberate 404 tests remain in native-qa.cjs.","Immediate UI close is tested; metadata may arrive before the close on a fast fixture. No before-metadata timing claim."]};
await fs.writeFile(path.join(out,"media-results.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({passed:results.filter(r=>r.status==="PASS").length,failed:results.filter(r=>r.status==="FAIL").length,diagnostics:results.filter(r=>r.status!=="PASS"),artifactDir:out},null,2));
if(results.some(r=>r.status!=="PASS"))process.exitCode=1;
}
})();
