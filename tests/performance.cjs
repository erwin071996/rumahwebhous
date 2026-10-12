/* Cloud-only first-party performance lab. No form interaction or production mutation. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const fsSync = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const os = require("node:os");
const crypto = require("node:crypto");
const {execFileSync} = require("node:child_process");
const {pathToFileURL} = require("node:url");
const BASE = "5217e1cf524cff9cf6bd9977ba90551389cef51d";
const HTML = { "index.html": ["d73ab8912162d276a8be606da6d56ecc20db994a", "510984abb196d40c09e96224e6a4166b7698b326ced09a481f143e4dff40a821"], "projects.html": ["82843cc1fb0576a49563e050c4926dc16ec13575", "a7d9f952ef79c554220898abe82d1b98db4e305b312b0cb8295f38e8b20c3033"] };
const candidatePaths = ["index.html","projects.html","assets/ui/brief.js","assets/ui/brief.css","assets/ui/frontend.js","assets/ui/frontend.css","assets/ui/theme.css","assets/branding/logo-3dkan-original.jpg"];
const metrics = ["first-contentful-paint","largest-contentful-paint","speed-index","total-blocking-time","cumulative-layout-shift"];
const fixture = path.resolve(process.env.PERF_FIXTURE_DIR || "artifacts/native-qa/fixture");
const out = path.resolve(process.env.PERF_ARTIFACT_DIR || "artifacts/performance");
const candidateSha = process.env.QA_CANDIDATE_SHA;
const runs = [], failures = [], servers = [], inventory = {}, cleanupEvents = [];
let metadata, cleanupPending = false;
const digest = b => crypto.createHash("sha256").update(b).digest("hex");
async function limit(operation, ms, label) {
 let timer;
 return Promise.race([Promise.resolve().then(operation),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+" exceeded "+ms+"ms")),ms);})]).finally(()=>clearTimeout(timer));
}
async function stopOwnedProcess(child) {
 if(!child || typeof child.kill!=="function") throw Error("Owned Chromium process unavailable");
 if(child.exitCode!==null || child.signalCode!==null) return "already exited";
 const exited=new Promise(resolve=>{child.once("exit",resolve);if(child.exitCode!==null||child.signalCode!==null)resolve();});
 if(!child.kill("SIGKILL") && child.exitCode===null && child.signalCode===null) throw Error("Owned Chromium SIGKILL rejected");
 await limit(()=>exited,3000,"Owned Chromium exit");
 return "SIGKILL exit confirmed";
}
async function cleanupBrowser(browser,label,abortMeasurement=false) {
 const child=browser.process();
 let forced=abortMeasurement,reason="";
 try {
  if(!abortMeasurement) {
   try {await limit(()=>browser.close(),5000,"Chromium graceful close");cleanupEvents.push({label,status:"PASS",action:"graceful browser close"});return;}
   catch(e){forced=true;reason=e.message;}
  }
  const action=await stopOwnedProcess(child);
  await limit(()=>browser.disconnect(),1000,"Chromium transport disconnect");
  cleanupEvents.push({label,status:abortMeasurement?"PASS":"FAIL",action,reason:abortMeasurement?"Measurement deadline; owned browser aborted":reason});
  if(!abortMeasurement) throw Error("Graceful cleanup failed; owned process terminated: "+reason);
 } catch(e) {
  if(child) {
   try {child.stdin?.destroy();child.stdout?.destroy();child.stderr?.destroy();child.unref();}catch(ignore){}
  }
  cleanupEvents.push({label,status:"FAIL",action:forced?"owned process cleanup":"browser cleanup",detail:e.message});
  throw e;
 }
}
async function cleanupServer(server,index) {
 try {
  await limit(()=>new Promise((resolve,reject)=>{
   if(!server.listening)return resolve();
   server.close(error=>error?reject(error):resolve());
   server.closeAllConnections();
  }),2000,"Loopback server close");
  cleanupEvents.push({label:"server-"+index,status:"PASS",action:"owned server close"});
 } catch(e) {server.unref();cleanupEvents.push({label:"server-"+index,status:"FAIL",detail:e.message});throw e;}
}
function git(args, binary=false) { return execFileSync("git",args,{encoding:binary?undefined:"utf8",maxBuffer:3000000}); }
async function readChecked(file) { const s=await fs.lstat(file); assert(s.isFile()&&!s.isSymbolicLink(),"Regular file required: "+file); return fs.readFile(file); }
function checkBytes(b,entry) { assert.equal(b.length,entry.bytes,"Byte mismatch: "+entry.path); assert.equal(digest(b),entry.sha256,"Digest mismatch: "+entry.path); }
function mime(file) { return ({".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".svg":"image/svg+xml",".jpg":"image/jpeg",".webp":"image/webp"})[path.extname(file)] || "application/octet-stream"; }
const CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'none'; worker-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri 'self'";
async function startServer(files,canary=false) {
 const record={hits:0,unexpected:[],server:null,origin:""};
 const server=http.createServer((req,res)=>{
  if(canary) { record.hits++;res.writeHead(200,{"Content-Type":"text/plain"});res.end("guard canary");return; }
  let route;try{route=new URL(req.url,"http://127.0.0.1").pathname;}catch(e){res.writeHead(400);res.end();return;}
  if(!["GET","HEAD"].includes(req.method)) { record.unexpected.push({method:req.method,path:route});res.writeHead(405);res.end();return; }
  if(route==="/favicon.ico") {res.writeHead(204,{"Cache-Control":"no-store"});res.end();return;}
  if(route==="/") route="/index.html";
  let data=files.get(route);
  if(route==="/__performance_guard.html") data=Buffer.from("<!doctype html><title>Local guard probe</title><link rel=\"icon\" href=\"data:,\"><p>Read-only lab guard probe</p>");
  if(!data) {record.unexpected.push({method:req.method,path:route});res.writeHead(404);res.end();return;}
  res.writeHead(200,{"Content-Type":mime(route),"Content-Length":data.length,"Cache-Control":"no-store","Content-Security-Policy":CSP});
  res.end(req.method==="HEAD"?undefined:data);
 });
 server.on("upgrade",(req,socket)=>{record.hits++;socket.destroy();});
 await new Promise((resolve,reject)=>{server.once("error",reject);server.listen(0,"127.0.0.1",resolve);});
 record.server=server;record.origin="http://127.0.0.1:"+server.address().port;servers.push(server);return record;
}
async function buildFixtures() {
 assert(candidateSha&&/^[0-9a-f]{40}$/.test(candidateSha),"Exact QA_CANDIDATE_SHA required");
 assert.equal(git(["rev-parse","HEAD"]).trim(),candidateSha,"Candidate checkout is not pinned");
 git(["cat-file","-e",BASE+"^{commit}"]);
 const manifest=JSON.parse(await fs.readFile("tests/native-dependencies.json","utf8"));
 assert.equal(manifest.schemaVersion,1);
 const shared=manifest.files.filter(e=>!e.checkoutSource),photos=manifest.files.filter(e=>e.checkoutSource);
 assert.equal(shared.length,5);assert.equal(photos.length,12);
 const candidate=new Map(),baseline=new Map(), records=[];
 for(const entry of manifest.files) {
  assert(/^\/assets\/[a-zA-Z0-9_./-]+$/.test(entry.path)&&!entry.path.includes(".."));
  const b=await readChecked(path.join(fixture,entry.path.slice(1)));checkBytes(b,entry);
  candidate.set(entry.path,b);
  if(!entry.checkoutSource) baseline.set(entry.path,b);
  records.push({path:entry.path,bytes:b.length,sha256:digest(b),source:entry.checkoutSource?"immutable checkout photo":"same integrity-pinned public dependency snapshot"});
 }
 for(const relative of candidatePaths) {
  const b=await readChecked(path.join(fixture,relative)),original=await readChecked(path.join("public_html",relative));
  assert.equal(digest(b),digest(original),"Fixture differs from candidate: "+relative);candidate.set("/"+relative,b);
 }
 for(const [file,[blob,sha256]] of Object.entries(HTML)) {
  assert.equal(git(["rev-parse",BASE+":"+file]).trim(),blob);
  const b=git(["show",BASE+":"+file],true);assert.equal(digest(b),sha256);baseline.set("/"+file,b);
 }
 const names=git(["ls-tree","-r","--name-only",BASE,"assets/portfolio-real/clean"]).trim().split("\n").filter(x=>x.endsWith(".webp"));
 assert.equal(names.length,15,"Baseline photo inventory changed");
 const byPath=new Map(photos.map(e=>[e.path.slice(1),e]));
 const aliases={"proses-produksi-cimb-niaga.webp":"cimb-niaga-signage-atm.webp","uji-nyala-cimb-niaga.webp":"cimb-niaga-signage-atm.webp","proses-gadget-solution.webp":"gadget-solution-neonbox.webp"};
 for(const name of names) {
  const leaf=path.basename(name), canonical=aliases[leaf] ? "assets/portfolio-real/clean/"+aliases[leaf] : name;
  const e=byPath.get(canonical);assert(e,"Unknown baseline asset: "+name);
  const b=git(["show",BASE+":"+name],true);checkBytes(b,{...e,path:"/"+name});baseline.set("/"+name,b);
 }
 for(const [label,files] of [["baseline",baseline],["candidate",candidate]]) inventory[label]=[...files].map(([pathname,b])=>({path:pathname,bytes:b.length,sha256:digest(b)}));
 return {baseline,candidate,sharedSnapshot:{observedAt:manifest.observedAt,provenance:manifest.provenance,records}};
}
async function proveGuard(page,canary,phase) {
 const before=canary.hits;
 await page.evaluate(async origin=>{
  try { await fetch(origin+"/fetch"); } catch(e) {}
  await new Promise(resolve=>{try{const socket=new WebSocket(origin.replace("http:","ws:")+"/ws");socket.onerror=()=>resolve();setTimeout(()=>{socket.close();resolve();},100);}catch(e){resolve();}});
 },canary.origin);
 const session=await page.createCDPSession();
 try {
  const tree=await session.send("Page.getFrameTree");
  for(const includeCredentials of [false,true]) {
   const beforeProbe=canary.hits;
   let response,blockedByCSP=false;
   try {
    response=await session.send("Network.loadNetworkResource",{frameId:tree.frameTree.frame.id,url:canary.origin+"/source-map-"+includeCredentials,options:{disableCache:true,includeCredentials}});
   } catch(error) {
    if(error.name!=="ProtocolError"||error.message!=="Protocol error (Network.loadNetworkResource): CSP violation") throw error;
    blockedByCSP=true;
   }
   if(!blockedByCSP) assert.equal(response?.resource?.success,false,"CDP source-map guard did not reject canary (credentials="+includeCredentials+")");
   assert.equal(canary.hits,beforeProbe,"Canary request reached server");
   (metadata.canaryProof||=[]).push({phase,includeCredentials,outcome:blockedByCSP?"explicit protocol CSP rejection":"resource success=false rejection",hitsBefore:beforeProbe,hitsAfter:canary.hits});
  }
 } finally { await session.detach(); }
 await new Promise(resolve=>setTimeout(resolve,50));
 assert.equal(canary.hits,before,"Forbidden second-origin request reached local canary");
}
function median(values){const a=values.slice().sort((x,y)=>x-y);return a[Math.floor(a.length/2)];}
function aggregate() {
 const groups=[];
 for(const variant of ["baseline","candidate"]) for(const device of ["mobile","desktop"]) for(const url of ["/","/projects.html"]) {
  const selected=runs.filter(r=>r.variant===variant&&r.device===device&&r.url===url);
  const stats={variant,device,url,n:selected.length};
  for(const key of ["performanceScore",...metrics,"transferBytes","requestCount"]) {
   const values=selected.map(r=>r.metrics[key]).filter(Number.isFinite);
   stats[key]=values.length===3?{median:median(values),min:Math.min(...values),max:Math.max(...values)}:null;
  }
  groups.push(stats);
 }
 const comparisons=groups.filter(g=>g.variant==="candidate").map(g=>{
  const base=groups.find(b=>b.variant==="baseline"&&b.device===g.device&&b.url===g.url),delta={device:g.device,url:g.url};
  for(const key of ["performanceScore",...metrics,"transferBytes","requestCount"]) {
   delta[key]=base[key]&&g[key]?{baseline:base[key].median,candidate:g[key].median,absolute:g[key].median-base[key].median,percent:base[key].median===0?null:(g[key].median/base[key].median-1)*100}:null;
  }return delta;
 });
 return {groups,comparisons};
}
async function checkpoint(status) {
 const summary={metadata,inventory,runs,failures,cleanupPending,cleanupEvents,...aggregate(),status};
 try {await fs.writeFile(path.join(out,"summary.json"),JSON.stringify(summary,null,2));}
 catch(e) {console.error(JSON.stringify({status:"FAIL",label:"report persistence",detail:e.message}));throw e;}
 return summary;
}
(async()=>{
 await fs.mkdir(out,{recursive:true});
 metadata={baselineSha:BASE,candidateSha,caveats:["Reconstructed two-page baseline; shared CSS/JS/brand/favicon use the SAME public hash-pinned snapshot in both variants, not a full immutable historical deployment.","First-party localhost HTTP/1.1, no compression, no-store, default cold Lighthouse storage reset; no hosting/CDN/TLS timing or field CWV claim.","Puppeteer25.13 officially tests Chrome155; custom PlaywrightChromium156 requires compatibility/guard smoke; record actual version.","CSP + Puppeteer allowlist + page interception restrict tested page/network-service paths; this is NOT an OS network sandbox.","Navigation-only lab; no forms filled, links clicked or production media playback/INP acceptance."]};
 try {
  const {baseline,candidate,sharedSnapshot}=await buildFixtures();metadata.sharedSnapshot=sharedSnapshot;
  const {default:lighthouse,desktopConfig,generateReport}=await import(pathToFileURL(require.resolve("lighthouse")).href);
  const puppeteer=(await import(pathToFileURL(require.resolve("puppeteer-core")).href)).default,{chromium}=require("playwright");
  const modulePackage=name=>JSON.parse(fsSync.readFileSync(require.resolve(name+"/package.json"),"utf8")).version;
  metadata.versions={node:process.version,lighthouse:modulePackage("lighthouse"),puppeteerCore:modulePackage("puppeteer-core"),playwright:modulePackage("playwright")};
  assert.equal(metadata.versions.lighthouse,"13.5.0");assert.equal(metadata.versions.puppeteerCore,"25.13.0");assert.equal(metadata.versions.playwright,"1.64.0");
  assert(Number(process.versions.node.split(".")[0])>22||(Number(process.versions.node.split(".")[0])===22&&Number(process.versions.node.split(".")[1])>=19),"Node>=22.19 required");
  metadata.runner={platform:process.platform,arch:process.arch,release:os.release(),cpuModel:os.cpus()[0]?.model,cpuCount:os.cpus().length,memoryBytes:os.totalmem(),imageOS:process.env.ImageOS,imageVersion:process.env.ImageVersion};
  const sites={baseline:await startServer(baseline),candidate:await startServer(candidate)},canary=await startServer(new Map(),true);
  const binary=chromium.executablePath();metadata.chromiumBinarySHA256=digest(await fs.readFile(binary));
  for(const device of ["mobile","desktop"]) for(const url of ["/","/projects.html"]) for(let repeat=1;repeat<=3;repeat++) for(const variant of repeat%2?["baseline","candidate"]:["candidate","baseline"]) {
   const site=sites[variant],blocked=[],pageErrors=[];let browser,measurementTimedOut=false;
   const label=variant+"-"+device+"-"+(url==="/"?"index":"projects")+"-"+repeat;
   try {
    browser=await puppeteer.launch({executablePath:binary,headless:true,defaultViewport:null,ignoreDefaultArgs:["--enable-automation"],browser:"chrome",protocol:"cdp",allowlist:[site.origin+"/*"],timeout:30000});
    const browserVersion=await browser.version();assert(/(?:Chrome|Chromium)\/156\./.test(browserVersion),"Expected existing Chromium156: "+browserVersion);
    const page=await browser.newPage();await page.setBypassServiceWorker(true);await page.setRequestInterception(true);
    page.on("request",request=>{
     if(request.isInterceptResolutionHandled()) return;
     let u;try{u=new URL(request.url());}catch(e){return request.abort("blockedbyclient");}
     if(!["http:","https:"].includes(u.protocol)) return ["about:","data:","blob:"].includes(u.protocol)?request.continue():request.abort("blockedbyclient");
     if(u.origin!==site.origin||!["GET","HEAD"].includes(request.method())) {
      blocked.push({origin:u.origin,path:u.pathname,method:request.method()});return request.abort("blockedbyclient");
     }return request.continue();
    });
    page.on("pageerror",e=>pageErrors.push(e.message));
    await page.goto(site.origin+"/__performance_guard.html");await proveGuard(page,canary,label+" before");
    let deadline;
    const result=await Promise.race([lighthouse(site.origin+url,{onlyCategories:["performance"],output:"json",logLevel:"error",disableStorageReset:false,disableFullPageScreenshot:true},device==="desktop"?desktopConfig:undefined,page),new Promise((_,reject)=>{deadline=setTimeout(()=>{measurementTimedOut=true;reject(Error("Lighthouse whole-run deadline 120s; owned Chromium termination required"));},120000);})]).finally(()=>clearTimeout(deadline));
    assert(result&&result.lhr,"Lighthouse returned no result");const lhr=result.lhr;assert(!lhr.runtimeError,JSON.stringify(lhr.runtimeError));assert.equal(lhr.lighthouseVersion,"13.5.0");
    await proveGuard(page,canary,label+" after");assert.equal(site.hits,0,"Unexpected local WebSocket upgrade");assert.equal(site.unexpected.length,0,"Unexpected local requests: "+JSON.stringify(site.unexpected));
    assert.equal(pageErrors.length,0,"Uncaught page runtime errors: "+JSON.stringify(pageErrors));
    assert.equal(typeof lhr.categories.performance.score,"number","Missing performance score");
    const measured={performanceScore:lhr.categories.performance.score*100};
    for(const key of metrics){measured[key]=lhr.audits[key]?.numericValue;assert(Number.isFinite(measured[key]),"Missing metric: "+key);}
    const network=lhr.audits["network-requests"]?.details?.items||[];
    measured.transferBytes=lhr.audits["total-byte-weight"]?.numericValue;assert(Number.isFinite(measured.transferBytes),"Missing transfer-byte metric");assert(network.length>0,"Missing request inventory");
    measured.requestCount=network.filter(r=>r.url?.startsWith(site.origin)&&r.statusCode>=200&&r.statusCode<400).length;
    const reportFile=path.join(out,label);
    await fs.writeFile(reportFile+".report.json",JSON.stringify(lhr,null,2));
    await fs.writeFile(reportFile+".report.html",generateReport(lhr,"html"));
    runs.push({variant,device,url,repeat,browserVersion,configSettings:lhr.configSettings,environment:lhr.environment,fetchTime:lhr.fetchTime,metrics:measured,blocked,pageErrors,runWarnings:lhr.runWarnings,artifactPrefix:label});
    console.log(JSON.stringify({status:"PASS",label,metrics:measured,browserVersion}));
   } catch(e) { failures.push({label,status:"FAIL",detail:e.stack||e.message});throw e; }
   finally {
    if(browser) {
     cleanupPending=true;
     try {await checkpoint(failures.length?"FAIL":"RUNNING");}
     catch(e){failures.push({label:label+" report persistence",status:"FAIL",detail:e.message});}
     try {await cleanupBrowser(browser,label,measurementTimedOut);}
     catch(e){failures.push({label:label+" cleanup",status:"FAIL",detail:e.message});throw e;}
     finally {cleanupPending=false;await checkpoint(failures.length?"FAIL":"RUNNING");}
    }
   }
  }
 } catch(e) {if(!failures.length)failures.push({label:"performance setup",status:"FAIL",detail:e.stack||e.message});}
 finally {
  cleanupPending=true;
  try {await checkpoint(failures.length?"FAIL":"CLEANUP PENDING");}
  catch(e){failures.push({label:"final report persistence",status:"FAIL",detail:e.message});}
  for(let i=0;i<servers.length;i++) {
   try {await cleanupServer(servers[i],i);}
   catch(e){failures.push({label:"server-"+i+" cleanup",status:"FAIL",detail:e.message});}
  }
  cleanupPending=false;
  const status=failures.length?"FAIL":runs.length===24?"PASS":"NOT RUN";
  try {await checkpoint(status);}catch(e){process.exitCode=1;}
  console.log(JSON.stringify({status,completed:runs.length,expected:24,failures,cleanupEvents},null,2));
  if(status!=="PASS")process.exitCode=1;
 }
})();
