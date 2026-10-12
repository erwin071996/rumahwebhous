/* Verify original asset bytes and the two candidate references before previewing. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),crypto=require("node:crypto");
const digest=data=>crypto.createHash("sha256").update(data).digest("hex");
const logo=fs.readFileSync("public_html/assets/branding/logo-3dkan-original.jpg");
assert.equal(logo.length,191744);
assert.equal(digest(logo),"2072e61fb6c1391a8c893dd9f37dcb95846220c6d9a4118d4b72ec83b84405d0");
assert.equal(logo.readUInt16BE(0),0xffd8);
let frame=null;
for(let i=2;i<logo.length;) {
 if(logo[i++]!==0xff)throw Error("Invalid JPEG marker");
 while(logo[i]===0xff)i++;
 const marker=logo[i++];
 if(marker===0xd9||marker===0xda)break;
 if(marker===0x01||marker>=0xd0&&marker<=0xd7)continue;
 const length=logo.readUInt16BE(i);if(length<2||i+length>logo.length)throw Error("Invalid JPEG segment");
 if([0xc0,0xc1,0xc2].includes(marker)){frame={bits:logo[i+2],height:logo.readUInt16BE(i+3),width:logo.readUInt16BE(i+5)};break;}
 i+=length;
}
assert.deepEqual(frame,{bits:8,height:654,width:2048});
const theme=fs.readFileSync("public_html/assets/ui/theme.css");
assert.equal(digest(theme),"33077a45d4c7f7d4ab6a5bd69340bd77b1a0cc91bde2fa1c29e6d2b3b8d6044d");
for(const name of ["index.html","projects.html"]) {
 const html=fs.readFileSync("public_html/"+name,"utf8"),head=html.split("</head>")[0];
 assert.equal((html.match(/<img[^>]+src="\/assets\/branding\/logo-3dkan-original\.jpg"[^>]*>/g)||[]).length,2);
 assert.equal((html.match(/https:\/\/www\.3dkanadvertising\.store\/assets\/branding\/logo-3dkan-original\.jpg/g)||[]).length,1);
 assert(!html.includes('src="/assets/refresh-20261006/brand.svg"'));
 assert(head.includes('<meta name="theme-color" content="#102347">'));
 assert.equal((head.match(/href="\/assets\/ui\/theme\.css"/g)||[]).length,1);
 assert(head.lastIndexOf("/assets/ui/theme.css")>head.lastIndexOf("/assets/ui/frontend.css"));
 assert(head.lastIndexOf("/assets/ui/theme.css")>head.lastIndexOf("</style>"));
}
console.log("Original logo size/hash/frame and both page/theme references PASS (rendering remains separate)");
