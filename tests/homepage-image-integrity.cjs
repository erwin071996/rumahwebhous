/* Verify exact reviewed homepage image bytes before any preview or lab run. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const {guardDerivative}=require("./webp-derivative-guard.cjs");
const sha=b=>crypto.createHash("sha256").update(b).digest("hex");
const blob=b=>crypto.createHash("sha1").update(Buffer.from("blob "+b.length+"\0")).update(b).digest("hex");
const expected=[
 ["/assets/branding/logo-3dkan-688.webp","logo-3dkan-688.webp",688,220,"VP8L"],
 ["/assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp","responsive/cimb-niaga-signage-atm-480.webp",480,854,"VP8"],
 ["/assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp","responsive/cimb-niaga-signage-atm-768.webp",768,1366,"VP8"]
];
const masters=[
 ["public_html/assets/branding/logo-3dkan-original.jpg",191744,"2072e61fb6c1391a8c893dd9f37dcb95846220c6d9a4118d4b72ec83b84405d0"],
 ["public_html/assets/portfolio-real/clean/cimb-niaga-signage-atm.webp",612162,"501e6f982db106e44c739b40dcf9416ae31692651c277a00980b3d0b80edf476"]
];
function validate(root=path.resolve(__dirname,"..")) {
 const m=JSON.parse(fs.readFileSync(path.join(root,"tests/homepage-image-manifest.json"),"utf8"));
 assert.equal(m.schemaVersion,1);
 assert.equal(m.sourceCommit,"ab9335cb8a80039eb710c0231167c6d490d66e37");
 assert.equal(m.generatorCommit,"d4fda02644f3bb629379ab77c252df07789c37a9");
 assert.equal(m.encoder.pillow,"12.3.0");assert.equal(m.encoder.crop,false);assert.equal(m.encoder.colorConversion,false);
 assert.deepEqual(m.masters.map(x=>[x.path,x.bytes,x.sha256]),masters);
 assert.equal(m.files.length,3);assert.deepEqual(m.files.map(x=>x.path).sort(),expected.map(x=>x[0]).sort());
 for(const [file,bytes,digest] of masters) {
  const at=path.join(root,file),stat=fs.lstatSync(at);assert(stat.isFile()&&!stat.isSymbolicLink());
  const data=fs.readFileSync(at);assert.equal(data.length,bytes);assert.equal(sha(data),digest,"Original master changed: "+file);
 }
 const records=[];
 for(const [url,guardPath,width,height,codec] of expected) {
  const e=m.files.find(x=>x.path===url);assert.equal(e.checkoutSource,"public_html"+url);assert.equal(e.guardPath,guardPath);
  assert.equal(e.mime,"image/webp");assert.deepEqual(e.dimensions,[width,height]);assert.equal(e.codec,codec);
  assert(Number.isInteger(e.bytes)&&e.bytes>0&&e.bytes<=1500000);assert(/^[a-f0-9]{64}$/.test(e.sha256)&&/^[a-f0-9]{40}$/.test(e.gitBlob));
  const at=path.join(root,e.checkoutSource),stat=fs.lstatSync(at);assert(stat.isFile()&&!stat.isSymbolicLink());
  const data=fs.readFileSync(at);assert.equal(data.length,e.bytes);assert.equal(sha(data),e.sha256);assert.equal(blob(data),e.gitBlob);
  const actual=guardDerivative(guardPath,data);assert.equal(actual.codec,codec);assert.equal(actual.width,width);assert.equal(actual.height,height);
  assert.equal(e.iccBytes,0);assert.equal(e.iccSha256,null);assert.equal(actual.icc,null);
  assert.equal(e.encoding.lossless,codec==="VP8L");assert.equal(e.encoding.quality,codec==="VP8L"?100:90);assert.equal(e.encoding.method,6);assert.equal(e.encoding.exact,true);
  const master=codec==="VP8L"?masters[0]:masters[1];assert.equal(e.sourcePath,master[0]);assert.equal(e.sourceSha256,master[2]);
  records.push({path:url,bytes:e.bytes,sha256:e.sha256,dimensions:[width,height],codec});
 }
 return {status:"PASS",records,scope:"Reviewed source/bytes/container/dimensions; native decode and pixel review remain separate"};
}
module.exports=validate;
if(require.main===module)console.log(JSON.stringify(validate(),null,2));
