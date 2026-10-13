/* Actual PHP session round trips with synthetic loopback bootstrap only. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const { spawn } = require("node:child_process");
const repo = path.resolve(__dirname, "..");
const php = process.env.CMS_PHP_BIN || "php";
const results = [];
let child, root, base;
const snapshot = { fields: { kind:"Layanan",title:"Synthetic HTTP Neon",summary:"Synthetic HTTP summary",
fact:"PRIVATE_HTTP_FACT",source:"PRIVATE_HTTP_SOURCE",verified:true }, order:["a","b"],rights:["a","b"],cover:"a" };
function jar() { return { cookie:null,csrf:null }; }
async function request(j,route="/cms-owner/endpoint.php",action=null,payload=null,options={}) {
const url=new URL(route,base);if(!action)url.searchParams.set("action","load");
const headers={};if(j.cookie)headers.Cookie=j.cookie;
if(action){headers["Content-Type"]=options.contentType||"application/json";headers.Origin=options.origin??"https://www.3dkanadvertising.store";
if(options.csrf!==null)headers["X-CSRF-Token"]=options.csrf??j.csrf??"wrong";}
const r=await fetch(url,{method:action?"POST":"GET",headers,body:action?JSON.stringify({action,payload}):undefined,
redirect:"manual",signal:AbortSignal.timeout(5000)});
const set=r.headers.get("set-cookie");if(set)j.cookie=set.split(";")[0];
const body=await r.json();
if(body.csrf)j.csrf=body.csrf;
return {status:r.status,body,headers:r.headers,setCookie:set};
}
async function check(name,fn) { try{await fn();results.push({name,status:"PASS"});}
catch(error){results.push({name,status:"FAIL",category:error.name});} }
async function ready() {
for(let i=0;i<30;i++){
if(child.exitCode!==null)throw Error("PHP fixture ended");
try{const r=await fetch(new URL("/cms-owner/unavailable.php",base),{signal:AbortSignal.timeout(400)});
if(r.status===503)return;}catch(error){}
await new Promise(resolve=>setTimeout(resolve,100));
}
throw Error("PHP fixture startup unavailable");
}
(async()=>{
try {
root=await fs.mkdtemp(path.join(os.tmpdir(),"kan-owner-http-"));await fs.chmod(root,0o700);
const server=net.createServer();await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
const port=server.address().port;await new Promise(resolve=>server.close(resolve));base="http://127.0.0.1:"+port;
child=spawn(php,["-d","display_errors=0","-d","session.use_cookies=0","-S","127.0.0.1:"+port,"tests/fixtures/cms-owner-http.php"],
{cwd:repo,env:{...process.env,CMS_OWNER_FIXTURE_ROOT:root},stdio:["ignore","ignore","pipe"]});
child.stderr.on("data",()=>{});let processError=null;child.on("error",error=>{processError=error.name;});
await ready();assert.equal(processError,null);
await check("missing-host-bootstrap-fails-closed",async()=>{const r=await request(jar(),"/cms-owner/unavailable.php");assert.equal(r.status,503);assert.deepEqual(r.body,{ok:false,category:"Unavailable"});});
await check("anonymous-other-expired-and-non-https-denied",async()=>{
for(const route of ["/cms-owner/anonymous.php","/cms-owner/other.php","/cms-owner/expired.php","/cms-owner/plain.php"]){
const r=await request(jar(),route);assert.equal(r.status,401);assert.deepEqual(r.body,{ok:false,category:"Access"});}
});
const a=jar(),b=jar();
await check("owner-load-cookie-and-private-response-headers",async()=>{
const r=await request(a);assert.equal(r.status,200);assert.equal(r.body.config.media.length,2);
assert.match(r.setCookie,/secure/i);assert.match(r.setCookie,/HttpOnly/i);assert.match(r.setCookie,/SameSite=Strict/i);assert.match(r.setCookie,/path=\/cms-owner\//i);
assert.match(r.headers.get("cache-control"),/no-store/);assert.equal(r.headers.get("x-content-type-options"),"nosniff");
assert.match(a.csrf,/^[a-f0-9]{64}$/);assert.equal(r.body.state.revision,0);
});
await check("missing-session-csrf-and-cross-origin-rejected",async()=>{
const fresh=await request(jar(),undefined,"save",{expected_revision:0,snapshot});assert.equal(fresh.status,401);
const missing=await request(a,undefined,"save",{expected_revision:0,snapshot},{csrf:null});assert.equal(missing.status,403);
const wrong=await request(a,undefined,"save",{expected_revision:0,snapshot},{csrf:"wrong"});assert.equal(wrong.status,403);
const cross=await request(a,undefined,"save",{expected_revision:0,snapshot},{origin:"https://example.invalid"});assert.equal(cross.status,403);
});
await check("save-and-reload-across-real-php-requests",async()=>{
assert.equal((await request(a,undefined,"save",{expected_revision:0,snapshot})).status,200);
const r=await request(a);assert.equal(r.body.state.revision,1);assert.deepEqual(r.body.state.snapshot,snapshot);
});
await check("owner-session-b-cannot-approve-session-a-preview",async()=>{
assert.equal((await request(a,undefined,"preview",{expected_revision:1})).status,200);await request(b);
assert.notEqual(a.cookie,b.cookie);assert.notEqual(a.csrf,b.csrf);
assert.equal((await request(b,undefined,"approve",{expected_revision:1})).status,409);
});
await check("durable-session-preview-approved-request-idempotency",async()=>{
assert.equal((await request(a,undefined,"approve",{expected_revision:1})).status,200);
const first=await request(a,undefined,"request-publication",{expected_revision:1});
const second=await request(a,undefined,"request-publication",{expected_revision:1});
assert.equal(first.status,200);assert.deepEqual(first.body,second.body);assert.equal(first.body.request.status,"requested");
assert.match(first.body.request.id,/^[a-f0-9]{64}$/);assert.deepEqual(Object.keys(first.body),["ok","request"]);
const file=path.join(root,"neon-box-publication-request.json"),bytes=await fs.readFile(file,"utf8");
assert(!bytes.includes("PRIVATE_HTTP_FACT")&&!bytes.includes("PRIVATE_HTTP_SOURCE"));
assert.equal((await fs.stat(file)).mode&0o077,0);
});
await check("new-private-edit-invalidates-old-review-and-pending",async()=>{
const edit=JSON.parse(JSON.stringify(snapshot));edit.fields.source="PRIVATE_HTTP_EDIT";edit.fields.verified=false;
assert.equal((await request(b,undefined,"save",{expected_revision:1,snapshot:edit})).status,200);
await assert.rejects(fs.stat(path.join(root,"neon-box-publication-request.json")));
assert.equal((await request(a,undefined,"request-publication",{expected_revision:1})).status,409);
assert.equal((await request(a,undefined,"approve",{expected_revision:2})).status,409);
});
await check("client-identity-and-receipt-never-authority",async()=>{
assert.equal((await request(b,undefined,"approve",{expected_revision:2,review:"forged",identity:"synthetic-owner"})).status,422);
});
await check("session-files-and-private-store-permissions",async()=>{
const files=await fs.readdir(root);assert(files.some(name=>name.startsWith("sess_")));
for(const name of files)assert.equal((await fs.stat(path.join(root,name))).mode&0o077,0);
assert.equal((await fs.stat(root)).mode&0o077,0);
});
} catch(error){results.push({name:"HTTP fixture setup",status:"FAIL",category:error.name});}
finally {
if(child&&child.exitCode===null){child.kill("SIGTERM");await Promise.race([new Promise(resolve=>child.once("exit",resolve)),new Promise(resolve=>setTimeout(resolve,2000))]);if(child.exitCode===null)child.kill("SIGKILL");}
if(root&&path.dirname(root)===path.resolve(os.tmpdir())&&path.basename(root).startsWith("kan-owner-http-"))await fs.rm(root,{recursive:true,force:true});
const failed=results.filter(row=>row.status==="FAIL").length;
console.log(JSON.stringify({passed:results.length-failed,failed,results,scope:"Synthetic loopback PHP sessions; no hosting authentication/TLS proof"},null,2));
if(failed)process.exitCode=1;
}
})();
