/* Strict still-WebP container/dimension gate for reviewed derivatives.
   This is not a compressed-image/ICC decoder. SHA, provenance and native decode
   must pass separately before preview. No filesystem, requests or mutation. */
"use strict";
const EXPECTED = Object.freeze({
  "logo-3dkan-688.webp": Object.freeze({ width:688, height:220, codec:"VP8L" }),
  "responsive/cimb-niaga-signage-atm-480.webp": Object.freeze({ width:480, height:854, codec:"VP8" }),
  "responsive/cimb-niaga-signage-atm-768.webp": Object.freeze({ width:768, height:1366, codec:"VP8" })
});
function demand(ok,message) { if(!ok) throw new Error("WebP guard: "+message); }
function inspectWebp(bytes) {
  demand(bytes instanceof Uint8Array,"byte buffer required");
  demand(bytes.length>=12 && bytes.length<=64*1024*1024,"file size outside guard limits");
  const text=(at,n)=>String.fromCharCode(...bytes.subarray(at,at+n));
  const le=(at,n)=>{ let value=0; for(let i=0;i<n;i++) value+=bytes[at+i]*2**(8*i); return value; };
  demand(text(0,4)==="RIFF" && text(8,4)==="WEBP","RIFF/WEBP signature required");
  const riffSize=le(4,4);
  demand(riffSize===bytes.length-8 && (riffSize&1)===0,"RIFF size/trailing bytes mismatch");
  const chunks=[];
  for(let at=12;at<bytes.length;) {
    demand(bytes.length-at>=8,"truncated chunk header");
    const id=text(at,4),size=le(at+4,4),start=at+8;
    demand(size<=bytes.length-start,"chunk exceeds RIFF boundary");
    const end=start+size,padded=end+(size&1);
    demand(padded<=bytes.length,"missing chunk padding");
    demand(!(size&1)||bytes[end]===0,"nonzero chunk padding");
    chunks.push({id,size,start,end});
    demand(chunks.length<=32,"too many derivative chunks");
    at=padded;
  }
  demand(chunks.length>0,"image chunk missing");
  const known=new Set(["VP8X","ICCP","ALPH","VP8 ","VP8L","EXIF","XMP "]);
  const seen=new Set();
  for(const chunk of chunks) {
    demand(known.has(chunk.id),"unsupported derivative chunk");
    demand(!seen.has(chunk.id),"duplicate chunk");
    seen.add(chunk.id);
  }
  const images=chunks.filter(c=>c.id==="VP8 "||c.id==="VP8L");
  demand(images.length===1,"exactly one still-image frame required");
  const image=images[0],imageIndex=chunks.indexOf(image),extended=chunks[0].id==="VP8X";
  demand(!seen.has("VP8X")||extended,"VP8X must be first");
  let canvas=null,flags=0;
  if(extended) {
    const c=chunks[0]; demand(c.size===10,"VP8X payload must be ten bytes");
    flags=bytes[c.start];
    demand((flags&0xc1)===0 && bytes[c.start+1]===0 && bytes[c.start+2]===0 && bytes[c.start+3]===0,"VP8X reserved bits");
    demand((flags&2)===0,"animation not allowed");
    canvas={width:le(c.start+4,3)+1,height:le(c.start+7,3)+1};
    demand(canvas.width*canvas.height<=0xffffffff,"VP8X canvas overflow");
    for(const [id,mask] of [["ICCP",0x20],["EXIF",8],["XMP ",4]]) {
      demand(Boolean(flags&mask)===seen.has(id),"VP8X feature/chunk mismatch");
    }
  } else {
    demand(chunks.length===1,"metadata/features require VP8X");
  }
  const icc=chunks.find(c=>c.id==="ICCP"),alpha=chunks.find(c=>c.id==="ALPH");
  if(icc) demand(extended && icc.size>0 && chunks.indexOf(icc)<imageIndex,"ICCP must precede image");
  if(icc && alpha) demand(chunks.indexOf(icc)<chunks.indexOf(alpha),"ICCP must precede ALPH");
  for(const id of ["EXIF","XMP "]) {
    const c=chunks.find(c=>c.id===id); if(c) demand(c.size>0,"empty metadata chunk");
  }
  let width,height,codec,alphaHint=false;
  if(image.id==="VP8L") {
    demand(image.size>=6 && bytes[image.start]===0x2f,"truncated/invalid VP8L header");
    const bits=le(image.start+1,4);
    demand(Math.floor(bits/2**29)===0,"unsupported VP8L version");
    width=(bits&0x3fff)+1; height=((bits>>>14)&0x3fff)+1;
    alphaHint=Boolean((bits>>>28)&1); codec="VP8L";
    demand(!alpha,"VP8L must not have separate ALPH");
  } else {
    demand(image.size>=11,"truncated VP8 keyframe");
    const tag=le(image.start,3),partition=tag>>>5;
    demand((tag&1)===0 && ((tag>>>1)&7)<=3 && (tag&16)!==0,"VP8 displayed keyframe required");
    demand(text(image.start+3,3)===String.fromCharCode(0x9d,1,0x2a),"VP8 start code");
    demand(partition>0 && 10+partition<image.size,"VP8 partition exceeds frame");
    const rawWidth=le(image.start+6,2),rawHeight=le(image.start+8,2);
    demand((rawWidth>>>14)===0 && (rawHeight>>>14)===0,"scaled VP8 frame not allowed");
    width=rawWidth&0x3fff; height=rawHeight&0x3fff; codec="VP8";
    demand(width>0 && height>0,"zero VP8 dimension");
    demand(Boolean(flags&0x10)===Boolean(alpha),"VP8 alpha feature/chunk mismatch");
    if(alpha) {
      demand(extended && chunks.indexOf(alpha)<imageIndex && alpha.size>=2,"invalid ALPH order/header");
      const header=bytes[alpha.start],compression=header&3;
      demand((header&0xc0)===0 && ((header>>>4)&3)<=1 && compression<=1,"unsupported ALPH header");
      if(compression===0) demand(alpha.size-1===width*height,"raw ALPH size mismatch");
    }
  }
  if(canvas) demand(canvas.width===width && canvas.height===height,"canvas/frame dimension mismatch");
  return Object.freeze({
    width,height,codec,extended,alphaHint,icc:icc?Object.freeze({offset:icc.start,bytes:icc.size}):null,
    chunks:Object.freeze(chunks.map(c=>Object.freeze({id:c.id,offset:c.start,bytes:c.size})))
  });
}
function guardDerivative(relative,bytes) {
  demand(typeof relative==="string","derivative path must be a string");
  demand(Object.prototype.hasOwnProperty.call(EXPECTED,relative),"unreviewed derivative path");
  const expected=EXPECTED[relative],actual=inspectWebp(bytes);
  demand(actual.width===expected.width && actual.height===expected.height,"derivative dimensions differ");
  demand(actual.codec===expected.codec,"derivative codec differs");
  if(relative==="logo-3dkan-688.webp" && actual.extended) demand(actual.icc!==null,"extended logo requires ICCP");
  return actual;
}
module.exports=Object.freeze({EXPECTED,inspectWebp,guardDerivative});
