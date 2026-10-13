"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {createModel,createCloudModel,createTransport,bind}=require("../cms/owner-ui.js");
const labels={a:"Foto bulat disetujui",b:"Foto akrilik disetujui"};
const clone=value=>JSON.parse(JSON.stringify(value));
const snapshot=model=>{const v=model.view();return {fields:v.fields,order:v.order,rights:v.rights,cover:v.cover};};
const checks=[];
async function check(name,fn){await fn();checks.push(name);}
function prepared(){const m=createModel(labels);m.edit("title","Judul sintetis");m.edit("summary","Ringkasan sintetis");m.select("b",true);m.right("b",true);m.cover("b");return m;}
function server(){
let state={revision:0,status:"empty",snapshot:null},review=false,requests=0;
return {get state(){return clone(state);},get requests(){return requests;},async send(action,payload){
if(action==="load")return {ok:true,state:clone(state)};
if(payload.expected_revision!==state.revision)return {ok:false,category:"Conflict"};
if(action==="save"){state={revision:state.revision+1,status:"draft",snapshot:clone(payload.snapshot)};review=false;return {ok:true,state:clone(state)};}
if(action==="preview"){review=true;return {ok:true,state:clone(state)};}
if(action==="approve"){if(!review)return {ok:false,category:"Conflict"};state.status="approved";return {ok:true,state:clone(state)};}
if(action==="request-publication"){if(state.status!=="approved"||!review)return {ok:false,category:"Conflict"};requests++;return {ok:true,request:{id:"synthetic-request-"+state.revision,status:"requested"}};}
return {ok:false,category:"Invalid"};
}};
}
function environment(){
const calls=[],replies=[];
const e={location:{href:"https://example.invalid/cms-owner/index.php",origin:"https://example.invalid"},AbortController:class{constructor(){this.signal={};}abort(){}},setTimeout:()=>1,clearTimeout:()=>{},fetch:async(url,options)=>{calls.push({url,options});const r=replies.shift();if(r instanceof Error)throw r;if(!r)throw Error("No synthetic response");return r;}};
return {e,calls,replies};
}
function response(body,status=200,type="application/json"){return {ok:status>=200&&status<300,status,headers:{get:()=>type},text:async()=>typeof body==="string"?body:JSON.stringify(body)};}
const config={service:{title:"Neon Box",summary:"Ringkasan publik",cover:"b"},media:[{id:"a",label:labels.a,src:"/assets/refresh-20261006/produk-fcf95321686c-640.webp"},{id:"b",label:labels.b,src:"/assets/refresh-20261006/produk-39db8e80530c-640.webp"}],publicationEnabled:false};
const boot={ok:true,csrf:"s".repeat(64),state:{revision:0,status:"empty",snapshot:null},config};
(async()=>{
await check("Existing model uses actual two approved IDs and fixed Layanan",()=>{const m=prepared();assert.equal(m.view().fields.kind,"Layanan");assert.throws(()=>m.select("c",true));assert.equal(m.labels.b,labels.b);});
await check("Fact edit cancels verified flag and approval",()=>{const m=prepared();m.edit("fact","Fakta sintetis");m.edit("verified",true);m.draft();m.preview();assert(m.approve().ok);m.edit("fact","Fakta berikut");assert(!m.view().fields.verified&&!m.view().approved);});
const backend=server(),a=createCloudModel(()=>createModel(labels),backend.send);
await check("Save persists revision before preview",async()=>{await a.load();for(const[k,v]of Object.entries(prepared().view().fields))a.model.edit(k,v);a.model.select("b",true);a.model.right("b",true);a.model.cover("b");assert((await a.save()).ok);assert(a.view().saved);assert.equal(a.view().serverRevision,1);});
await check("Reload preserves selected cover and rights",async()=>{assert((await a.load()).ok);assert.equal(a.view().cover,"b");assert.deepEqual(a.view().rights,["b"]);assert(!a.view().approved);});
await check("Request requires current server review and approval",async()=>{assert.equal((await a.requestPublication()).category,"ReviewRequired");await a.preview();assert(a.view().reviewReady);await a.approve();assert(a.view().approved);});
await check("Submission reports only requested and not live",async()=>{assert((await a.requestPublication()).ok);assert.equal(a.view().publication.status,"requested");assert.equal(backend.requests,1);assert(!Object.hasOwn(a.view().publication,"published"));});
await check("Edit hides request and invalidates approval",()=>{a.model.edit("summary","Ringkasan baru");assert(!a.view().saved&&!a.view().approved&&!a.view().publication);});
await check("New saved revision cannot revive prior submission",async()=>{await a.save();await a.preview();await a.approve();assert(!a.view().publication);});
await check("Known conflict keeps edits but invalidates review",async()=>{await a.save();await a.preview();await a.approve();const b=createCloudModel(()=>createModel(labels),backend.send);await b.load();b.model.edit("title","Sesi B");await b.save();const before=a.view().fields.title;assert.equal((await a.approve()).category,"Conflict");assert(a.view().needsReload&&!a.view().saved&&!a.view().approved&&!a.view().reviewReady);assert.equal(a.view().fields.title,before);});
await check("Saved edit during pending preview cannot acquire review",async()=>{const s=server(),m=createCloudModel(()=>prepared(),s.send);await m.save();let resolve;const delayed=createCloudModel(()=>prepared(),async(action,payload)=>action==="preview"?new Promise(r=>resolve=r):s.send(action,payload));await delayed.load();const promise=delayed.preview();delayed.model.edit("title","Edit saat menunggu");resolve({ok:true,state:s.state});assert.equal((await promise).category,"Unsaved");assert(!delayed.view().reviewReady);});
await check("Late superseded conflict preserves newer confirmed state",async()=>{const s=server();let resolve;let first=true;const m=createCloudModel(()=>prepared(),async(action,payload)=>action==="approve"&&first?(first=false,new Promise(r=>resolve=r)):s.send(action,payload));await m.save();await m.preview();const old=m.approve();await m.preview();await m.approve();resolve({ok:false,category:"Conflict"});await old;assert(m.view().approved&&m.view().saved&&!m.view().needsReload);});
await check("Pending request cannot mark later edits requested",async()=>{const s=server();let resolve;const m=createCloudModel(()=>prepared(),async(action,payload)=>action==="request-publication"?new Promise(r=>resolve=r):s.send(action,payload));await m.save();await m.preview();await m.approve();const p=m.requestPublication();m.model.edit("title","Revisi lokal berikut");resolve({ok:true,request:{id:"synthetic-old",status:"requested"}});assert.equal((await p).category,"Unsaved");assert(!m.view().publication&&!m.view().approved);});
await check("Unbound mutation performs no request",async()=>{const f=environment(),t=createTransport(f.e);assert.equal((await t.request("save",{})).category,"Access");assert.equal(f.calls.length,0);});
await check("HTTPS same-origin endpoint is fixed",()=>{const f=environment();f.e.location.href="http://example.invalid/cms-owner/";assert.throws(()=>createTransport(f.e));});
await check("Bootstrap is no-store GET, no draft in URL",async()=>{const f=environment(),t=createTransport(f.e);f.replies.push(response(boot));assert((await t.request("load",{})).ok);assert.equal(f.calls[0].url,"https://example.invalid/cms-owner/endpoint.php?action=load");assert.equal(f.calls[0].options.credentials,"same-origin");assert.equal(f.calls[0].options.redirect,"error");assert.equal(f.calls[0].options.cache,"no-store");assert(!f.calls[0].options.body);});
await check("POST uses session CSRF header and exact action payload",async()=>{const f=environment(),t=createTransport(f.e);f.replies.push(response(boot),response({ok:true,state:{revision:1,status:"draft",snapshot:snapshot(prepared())}}));await t.request("load",{});await t.request("save",{expected_revision:0,snapshot:snapshot(prepared())});const o=f.calls[1].options;assert.equal(o.method,"POST");assert.equal(o.headers["X-CSRF-Token"],boot.csrf);assert.deepEqual(Object.keys(JSON.parse(o.body)),["action","payload"]);assert(!o.body.includes(boot.csrf));assert(!f.calls[1].url.includes("Judul"));});
await check("Expired/CSRF response removes mutation capability",async()=>{const f=environment(),t=createTransport(f.e);f.replies.push(response(boot),response({ok:false,category:"Csrf"},403));await t.request("load",{});assert.equal((await t.request("approve",{expected_revision:1})).category,"Csrf");assert.equal((await t.request("save",{})).category,"Access");assert.equal(f.calls.length,2);});
await check("Unexpected authentication HTML is Access, no response leakage",async()=>{const f=environment(),t=createTransport(f.e);f.replies.push(response("<html>synthetic denial</html>",401,"text/html"));assert.deepEqual(await t.request("load",{}),{ok:false,category:"Access"});});
await check("Off-origin or malformed media configuration is rejected",async()=>{for(const src of ["https://other.invalid/photo.webp","/assets/../secret.webp","/assets/photo.webp?x=1"]){const f=environment(),t=createTransport(f.e),b=clone(boot);b.config.media[0].src=src;f.replies.push(response(b));assert.equal((await t.request("load",{})).category,"Unavailable");}});
await check("State cannot refer to unavailable media ID",async()=>{const f=environment(),t=createTransport(f.e),b=clone(boot);b.state={revision:1,status:"draft",snapshot:snapshot(prepared())};b.state.snapshot.order=["c"];b.state.snapshot.cover="c";f.replies.push(response(b));assert.equal((await t.request("load",{})).category,"Unavailable");});
await check("Malformed, oversized and failed network responses are generic",async()=>{for(const r of [response("{"),response("x".repeat(33000)),new Error("synthetic network detail")]){const f=environment(),t=createTransport(f.e);f.replies.push(r);assert.deepEqual(await t.request("load",{}),{ok:false,category:"Unavailable"});}});
await check("Publisher response cannot claim live",async()=>{const f=environment(),t=createTransport(f.e);f.replies.push(response(boot),response({ok:true,request:{id:"synthetic-request",status:"published"}}));await t.request("load",{});assert.equal((await t.request("request-publication",{expected_revision:1})).category,"Unavailable");});
await check("Actual HTML binds external connection indicator and denies unavailable session",async()=>{
const html=fs.readFileSync(path.join(__dirname,"../cms/owner-ui.html"),"utf8"),inside=html.slice(html.indexOf("<form"),html.indexOf("</form>"));
const elements=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(match=>[match[1],{dataset:{},setAttribute(){},removeAttribute(){},addEventListener(){},focus(){}}]));
const doc={getElementById:id=>elements[id],activeElement:null},form={ownerDocument:doc,dataset:{},querySelector:selector=>inside.includes('id="'+selector.slice(1)+'"')?elements[selector.slice(1)]:null,querySelectorAll:()=>[],setAttribute(){},addEventListener(){}};
assert(!form.querySelector("#owner-connection"),"Connection must test the actual outside-form position");
const f=environment();f.replies.push(response({ok:false,category:"Access"},401));
const bound=bind(form,f.e);assert(bound,"Actual HTML must bind");for(let i=0;i<12;i++)await Promise.resolve();
assert(elements["owner-fields"].disabled);assert.equal(bound.ready(),false);assert(elements["owner-status"].textContent.includes("Sesi Owner"));
});
await check("Source retains disabled/no-native-submit and literal preview contracts",()=>{const html=fs.readFileSync(path.join(__dirname,"../cms/owner-ui.html"),"utf8"),js=fs.readFileSync(path.join(__dirname,"../cms/owner-ui.js"),"utf8");assert(html.includes('id="owner-fields" disabled'));assert(!/<button\b(?![^>]*type="button")[^>]*>/i.test(html));assert(!/<(?:input|textarea)\b[^>]*\bname=/i.test(html));assert(!/innerHTML|localStorage|sessionStorage|document\.cookie|console\./.test(js));assert(js.includes('get("preview-title").textContent=preview.fields.title'));assert(js.includes('form.addEventListener("submit",event=>event.preventDefault())'));});
console.log(JSON.stringify({passed:checks.length,failed:0,checks},null,2));
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
