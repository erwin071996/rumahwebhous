/* One focused BRMP-to-brief native flow; reuse the existing isolated candidate preview. */
"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const base = new URL(process.env.BRMP_BASE_URL || "http://127.0.0.1:8765");
assert(["127.0.0.1","localhost","[::1]"].includes(base.hostname) && !base.username && !base.password && ["http:","https:"].includes(base.protocol),"Isolated loopback preview required");
const out = path.resolve(process.env.QA_ARTIFACT_DIR || "artifacts/shared-brand");
const results=[], blocked=[], leaks=[], errors=[], missing=[];
const nonce="QA_BRMP_DO_NOT_SEND_"+Date.now();
let browser, context, version=null;
(async()=>{
await fs.mkdir(out,{recursive:true});
try {
browser=await chromium.launch({headless:true});version=await browser.version();
context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:"block"});
await context.route("**/*",route=>{
const request=route.request(),url=new URL(request.url()),body=request.postData()||"";
if((request.url()+" "+body).includes(nonce))leaks.push({path:url.pathname,method:request.method(),category:"Synthetic brief attempted in request"});
if(!["GET","HEAD"].includes(request.method()))leaks.push({path:url.pathname,method:request.method(),category:"Non-read request"});
if(/^(wa\.me|api\.whatsapp\.com|web\.whatsapp\.com)$/.test(url.hostname))leaks.push({path:url.pathname,category:"Unexpected WhatsApp request"});
if(url.origin!==base.origin||!["GET","HEAD"].includes(request.method())){
blocked.push({path:url.pathname,method:request.method()});return route.abort("blockedbyclient");
}
return route.continue();
});
const page=await context.newPage();page.setDefaultTimeout(5000);
page.on("pageerror",error=>errors.push(error.name));
page.on("response",response=>{
if(response.url().startsWith(base.origin)&&response.status()>=400&&["script","stylesheet"].includes(response.request().resourceType()))
missing.push({path:new URL(response.url()).pathname,status:response.status()});
});
await page.goto(new URL("/projects.html#brmp",base).href,{waitUntil:"load"});
const card=page.locator("article#brmp"),cta=card.locator('a.case-cta[href="#brief-proyek"]');
assert.equal(await cta.count(),1);assert.equal(await cta.textContent(),"Siapkan brief huruf timbul interior");
assert.equal(await card.locator('a.case-cta[href="/layanan/huruf-timbul"]').textContent(),"Panduan brief huruf timbul");
assert((await card.textContent()).includes("Referensi visual: BRMP"));
await cta.scrollIntoViewIfNeeded();
assert(await cta.evaluate(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&[.15,.5,.85].every(f=>el.contains(document.elementFromPoint(r.left+r.width*f,r.top+r.height/2)));}),"New BRMP CTA hit target is covered");
await page.screenshot({path:path.join(out,"brmp-cta-390.png"),fullPage:false});
await cta.click();
assert.equal(new URL(page.url()).hash,"#brief-proyek");
const form=page.locator("form[data-brief-form]");
await form.locator('select[name="type"]').selectOption({label:"Huruf timbul"});
await form.locator('textarea[name="note"]').fill("Referensi visual: BRMP; "+nonce);
await form.locator("[data-brief-compose]").click();
assert(await form.locator("[data-brief-output]").isVisible());
const preview=await form.locator("[data-brief-preview]").inputValue();
assert(preview.includes("Huruf timbul")&&preview.includes("Referensi visual: BRMP")&&preview.includes(nonce));
const messageLink=await form.locator("[data-brief-whatsapp]").getAttribute("href");
assert(messageLink&&messageLink.startsWith("https://wa.me/6285340382029?text=")); // Never open it.
assert(!/sudah dikirim|berhasil dikirim/i.test(await form.locator("[data-brief-status]").textContent()));
results.push({name:"BRMP CTA and one manual Huruf timbul preview without sending",status:"PASS"});
await page.goto(new URL("/layanan/huruf-timbul",base).href,{waitUntil:"load"});
assert.equal(await page.title(),"Jasa Huruf Timbul: Pilihan & Brief Pesanan | 3DKan");
assert.equal(await page.locator("#service-detail-brief-interior-brmp p").count(),3);
assert.equal(await page.locator("#service-detail-brief-interior-brmp a").count(),0);
results.push({name:"Affected service renders exact approved title and one editorial section",status:"PASS"});
assert.equal(leaks.length,0,"Unexpected synthetic brief/WA/write request");
assert.equal(errors.length,0,"Uncaught page error");
assert.equal(missing.length,0,"Local script/style unavailable");
results.push({name:"Existing preview dependencies and read-only isolation",status:"PASS"});
} catch(error) {
results.push({name:"Focused BRMP native flow",status:"FAIL",category:error.name,message:error.message});
} finally {
if(context)await context.close().catch(()=>{results.push({name:"Context cleanup",status:"FAIL"});});
if(browser)await browser.close().catch(()=>{results.push({name:"Browser cleanup",status:"FAIL"});});
const report={candidateSha:process.env.QA_CANDIDATE_SHA||"UNKNOWN",runtime:{playwright:require("playwright/package.json").version,chromium:version},
results,blocked,leaks,errors,missing,limitations:["One390px focused flow only; no full visual/performance/media audit.","Synthetic message was composed only; WhatsApp was never opened or sent."]};
await fs.writeFile(path.join(out,"brmp-native-results.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({passed:results.filter(r=>r.status==="PASS").length,failed:results.filter(r=>r.status==="FAIL").length},null,2));
if(results.some(r=>r.status!=="PASS"))process.exitCode=1;
}
})();
