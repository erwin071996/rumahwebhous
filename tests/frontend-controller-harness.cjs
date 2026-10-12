async function runFrontendControllerTests(sourceCode) {
class Element {
  constructor(id, tag) { this.id=id;this.tag=tag||"div";this.tagName=this.tag.toUpperCase();this.attrs=new Map();this.dataset={};this.events={};this.children=[];this.parent=null;this.textContent="";this.disabled=true;this.hidden=false;this.open=false;this.value="";this.selected=false;this._src="";this.error=null;this.pauseCalls=0;this.loadCalls=0;this.playCalls=0;this.playMode="resolve";this.classes=new Set();this.classList={toggle:(name,on)=>{const active=on===undefined?!this.classes.has(name):on;if(active)this.classes.add(name);else this.classes.delete(name);return active;},contains:(name)=>this.classes.has(name)}; }
  setAttribute(k,v){this.attrs.set(k,String(v));if(k==="open"&&this.reflectOpen!==false)this.open=true;if(k==="src")this._src=String(v);}
  getAttribute(k){return this.attrs.has(k)?this.attrs.get(k):null;}
  hasAttribute(k){return this.attrs.has(k);}
  removeAttribute(k){this.attrs.delete(k);if(k==="open"&&this.reflectOpen!==false)this.open=false;if(k==="src")this._src="";}
  addEventListener(t,fn,options){(this.events[t]||=[]).push({fn,options});}
  async fire(t,extra){const event=Object.assign({target:this,prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}},extra||{});for(const {fn} of this.events[t]||[]){await fn(event);if(event.stopped)break;}return event;}
  querySelector(q){if(q==="summary")return this.children.find(x=>x.tag==="summary")||null;return null;}
  append(el){el.parent=this;this.children.push(el);return el;}
  contains(el){return this===el||this.children.some(child=>child.contains(el));}
  closest(q){if(q==='form[data-brief-form]'&&this.tag==="form"&&this.hasAttribute("data-brief-form"))return this;if(q==="a[href]"&&this.tag==="a"&&this.href)return this;return this.parent?this.parent.closest(q):null;}
  matches(q){return q===":disabled"&&this.disabled;}
  getBoundingClientRect(){return this.rect||{top:0,bottom:0,left:0,right:0,width:0,height:0};}
  focus(options){this.document.activeElement=this;this.lastFocusOptions=options;for(const {fn} of this.document.events.focusin||[])fn({target:this});}
  select(){this.selected=true;}
  set src(value){this._src=value;this.attrs.set("src",value);this.error=null;}
  get src(){return this._src;}
  pause(){this.pauseCalls+=1;}
  load(){this.loadCalls+=1;this.error=null;}
  play(){this.playCalls+=1;if(this.playMode==="reject")return Promise.reject(new Error("Playback blocked"));return Promise.resolve();}
}
class UrlStub {
  constructor(input,base){const text=String(input);const root=String(base||"https://www.3dkanadvertising.store/");const rootMatch=root.match(/^(https?:\/\/[^/]+)([^#?]*)?(?:\?[^#]*)?(#.*)?$/);if(!rootMatch)throw new Error("Unsupported URL base");const absolute=/^https?:\/\//.test(text)?text:rootMatch[1]+(text.startsWith("/")?text:text.startsWith("#")?(rootMatch[2]||"/")+text:"/"+text);const m=absolute.match(/^(https?:\/\/[^/]+)([^#?]*)?(?:\?[^#]*)?(#.*)?$/);if(!m)throw new Error("Unsupported URL");this.href=absolute;this.origin=m[1];this.pathname=m[2]||"/";this.hash=m[3]||"";}
}
const all=[];
function element(id,tag){const e=new Element(id,tag);all.push(e);return e;}
const menu=element("menu","button"),nav=element("site-nav","nav"),services=nav.append(element("services","details")),summary=services.append(element("summary","summary"));
menu.setAttribute("aria-expanded","false");
const filters=["all","corporate","government","retail","worship"].map((category,i)=>{const b=element("filter-"+category,"button");b.dataset.filter=category;b.textContent=["Semua","Corporate","Instansi & Pemerintahan","Retail","Rumah Ibadah"][i];b.setAttribute("aria-pressed",String(i===0));return b;});
const categories=["corporate","corporate","government","government","government","government","government","retail","retail","worship"];
const cards=categories.map((category,i)=>{const c=element("card-"+i,"article");c.dataset.cat=category;return c;});
const count=element("gallery-result-count"),dialog=element("real-video-dialog","dialog"),video=dialog.append(element("real-video-player","video")),title=dialog.append(element("real-video-title")),status=dialog.append(element("real-video-status")),directSource=dialog.append(element("real-video-source","a")),closeButton=dialog.append(element("real-video-close","button"));
const openers=["cimb","brmp"].map(key=>{const b=element("open-"+key,"button");b.dataset.video="/assets/portfolio-real/videos/"+key+".mp4";b.dataset.title="Dokumentasi "+key;return b;});
const copy=element("copy-portfolio-link","button"),print=element("print-portfolio","button"),toolStatus=element("client-tool-status"),shareFallback=element("portfolio-share-fallback"),shareUrl=shareFallback.append(element("portfolio-share-url","input"));shareFallback.hidden=true;
const anchor=nav.append(element("brief-anchor","a"));anchor.href="https://www.3dkanadvertising.store/projects.html#brief-proyek";const brief=element("brief-proyek","section");
const submenuLink=services.append(element("services-anchor","a")),unrelatedInput=element("outside-input","input");
const header=element("header","header");header.rect={top:0,bottom:73,left:0,right:390,width:390,height:73};const briefForm=element("brief-form","form");briefForm.setAttribute("data-brief-form","home");const briefField=briefForm.append(element("test-brief-field","textarea"));briefField.disabled=false;
const body=element("body","body"),rootElement=element("html","html");
const doc=new Element("document");doc.body=body;doc.documentElement=rootElement;doc.activeElement=body;doc.pageFocused=true;doc.hasFocus=()=>doc.pageFocused;doc.contains=e=>all.includes(e);doc.querySelector=q=>q===".site-header"?header:q===".menu-toggle"?menu:q===".nav-services"?services:q==="dialog[open]"?(dialog.hasAttribute("open")?dialog:null):null;doc.querySelectorAll=q=>q===".real-filter"?filters:q===".real-card"?cards:q===".real-video"?openers:[];doc.getElementById=id=>all.find(e=>e.id===id)||null;for(const e of all)e.document=doc;
const media=new Element("media-query");media.matches=true;
const window=new Element("window");Object.assign(window,{innerHeight:844,scrollCalls:[],matchMedia:()=>media,printCalls:0,print(){this.printCalls++;},getComputedStyle:el=>({outlineWidth:el.outlineWidth||"3px",outlineOffset:el.outlineOffset||"3px"}),requestAnimationFrame:fn=>{timers.push(fn);return timers.length;},scrollBy(options,amount){const dy=typeof options==="object"?options.top:amount;this.scrollCalls.push({dy,active:doc.activeElement.id});for(const e of all)if(e.rect&&e!==header)e.rect={...e.rect,top:e.rect.top-dy,bottom:e.rect.bottom-dy};}});
window.visualViewport=new Element("visual-viewport");window.visualViewport.height=844;window.visualViewport.offsetTop=0;
const navigator={clipboard:{mode:"deny",writes:[],async writeText(text){this.writes.push(text);if(this.mode==="deny")throw new Error("Denied");}}};
const location={origin:"https://www.3dkanadvertising.store",pathname:"/projects.html",href:"https://www.3dkanadvertising.store/projects.html"};
const timers=[];const timeout=fn=>{timers.push(fn);return timers.length;};
dialog.showModal=function(){this.open=true;this.setAttribute("open","");};
dialog.close=function(){this.open=false;this.removeAttribute("open");Promise.resolve().then(()=>this.fire("close"));};
const execute=new Function("document","window","navigator","location","URL","setTimeout",sourceCode);execute(doc,window,navigator,location,UrlStub,timeout);
const results=[];
function expect(name,condition,details){results.push({name,pass:!!condition,details});}
async function flush(){await Promise.resolve();await Promise.resolve();for(const f of timers.splice(0))f();await Promise.resolve();}
async function escape(){const e=await doc.fire("keydown",{key:"Escape"});if(dialog.open&&!e.prevented)await dialog.fire("cancel");await flush();return e;}
const visible=()=>cards.filter(c=>!c.hidden).length;
expect("initial-all",visible()===10&&count.textContent==="10 proyek ditampilkan.",{count:visible(),status:count.textContent});
for(let repeat=1;repeat<=2;repeat++){
 for(const [category,expected] of [["retail",2],["worship",1],["all",10]]){
  const button=filters.find(b=>b.dataset.filter===category);await button.fire("click");
  expect("filters-"+repeat+"-"+category,visible()===expected&&filters.every(b=>b.getAttribute("aria-pressed")===String(b===button))&&cards.every(c=>c.hidden===c.classList.contains("real-hidden"))&&filters.every(b=>b.getAttribute("aria-controls")==="project-gallery"),{visible:visible(),status:count.textContent,pressed:filters.filter(b=>b.getAttribute("aria-pressed")==="true").map(b=>b.dataset.filter)});
 }
}
for(let repeat=1;repeat<=2;repeat++){
 const opener=openers[repeat-1];await opener.fire("click");await flush();
 expect("modal-open-"+repeat,dialog.open&&dialog.getAttribute("role")==="dialog"&&dialog.getAttribute("aria-modal")==="true"&&doc.activeElement===closeButton&&video.src===opener.dataset.video&&directSource.href===opener.dataset.video,{title:title.textContent,active:doc.activeElement.id});
 const beforePause=video.pauseCalls,beforeLoad=video.loadCalls;await escape();
 expect("modal-escape-"+repeat,!dialog.open&&!video.hasAttribute("src")&&video.src===""&&video.pauseCalls>beforePause&&video.loadCalls>beforeLoad&&doc.activeElement===opener,{pauseIncrement:video.pauseCalls-beforePause,loadIncrement:video.loadCalls-beforeLoad,active:doc.activeElement.id});
}
await openers[0].fire("click");video.error={code:4};await video.fire("error");expect("video-error",status.textContent.startsWith("Video belum dapat dimuat.")&&directSource.href===openers[0].dataset.video,{status:status.textContent,source:directSource.href});await closeButton.fire("click");await flush();
for(let repeat=1;repeat<=2;repeat++){
 navigator.clipboard.mode="deny";await copy.fire("click");expect("clipboard-denial-"+repeat,!shareFallback.hidden&&shareUrl.selected&&shareUrl.value==="https://www.3dkanadvertising.store/projects.html#studi-kasus"&&doc.activeElement===shareUrl&&!/tersalin/.test(toolStatus.textContent),{hidden:shareFallback.hidden,selected:shareUrl.selected,status:toolStatus.textContent});
}
navigator.clipboard.mode="allow";await copy.fire("click");expect("clipboard-success-after-denial",shareFallback.hidden&&toolStatus.textContent==="Tautan portofolio tersalin.",{status:toolStatus.textContent});
media.matches=true;menu.setAttribute("aria-expanded","true");nav.setAttribute("data-open","");services.open=true;summary.focus();const mobileEscape=await escape();expect("mobile-nav-escape",!services.open&&!nav.hasAttribute("data-open")&&menu.getAttribute("aria-expanded")==="false"&&doc.activeElement===menu&&mobileEscape.prevented&&mobileEscape.stopped,{active:doc.activeElement.id});
media.matches=false;services.open=true;menu.setAttribute("aria-expanded","false");nav.removeAttribute("data-open");summary.focus();await escape();expect("desktop-services-escape",!services.open&&doc.activeElement===summary&&!nav.hasAttribute("data-open")&&menu.getAttribute("aria-expanded")==="false",{active:doc.activeElement.id});
menu.setAttribute("aria-expanded","true");nav.setAttribute("data-open","");services.open=true;await media.fire("change");expect("breakpoint-reset",!services.open&&!nav.hasAttribute("data-open")&&menu.getAttribute("aria-expanded")==="false",{expanded:menu.getAttribute("aria-expanded")});
media.matches=true;menu.setAttribute("aria-expanded","true");nav.setAttribute("data-open","");services.open=true;anchor.focus();await media.fire("change");expect("breakpoint-hidden-nav-link-to-menu",doc.activeElement===menu&&!nav.hasAttribute("data-open")&&!services.open,{active:doc.activeElement.id});
media.matches=false;menu.focus();await media.fire("change");expect("breakpoint-hidden-menu-to-summary",doc.activeElement===summary,{active:doc.activeElement.id});
media.matches=false;services.open=true;submenuLink.focus();await media.fire("change");expect("breakpoint-closed-submenu-to-summary",doc.activeElement===summary&&!services.open,{active:doc.activeElement.id});
media.matches=false;anchor.focus();await media.fire("change");expect("breakpoint-visible-desktop-nav-focus-preserved",doc.activeElement===anchor,{active:doc.activeElement.id});
media.matches=true;unrelatedInput.focus();await media.fire("change");expect("breakpoint-unrelated-form-focus-preserved",doc.activeElement===unrelatedInput,{active:doc.activeElement.id});
menu.setAttribute("aria-expanded","true");nav.setAttribute("data-open","");services.open=true;await nav.fire("click",{target:anchor});await flush();expect("same-page-nav-anchor",doc.activeElement===brief&&brief.getAttribute("tabindex")==="-1"&&!services.open&&!nav.hasAttribute("data-open"),{active:doc.activeElement.id,focusOptions:brief.lastFocusOptions});
await print.fire("click");expect("print-trigger",window.printCalls===1,{calls:window.printCalls});
delete navigator.clipboard;await copy.fire("click");expect("clipboard-unavailable",!shareFallback.hidden&&shareUrl.selected&&doc.activeElement===shareUrl&&!/tersalin/.test(toolStatus.textContent),{status:toolStatus.textContent});
await openers[0].fire("click");menu.setAttribute("aria-expanded","true");nav.setAttribute("data-open","");services.open=true;const dialogKey=await doc.fire("keydown",{key:"Escape"});expect("dialog-escape-does-not-close-nav",menu.getAttribute("aria-expanded")==="true"&&nav.hasAttribute("data-open")&&services.open&&!dialogKey.prevented,{expanded:menu.getAttribute("aria-expanded")});await dialog.fire("cancel");await flush();services.open=false;nav.removeAttribute("data-open");menu.setAttribute("aria-expanded","false");
let rejectOld;const normalPlay=video.play;let first=true;video.play=function(){if(first){first=false;return new Promise((resolve,reject)=>{rejectOld=reject;});}return Promise.resolve();};await openers[0].fire("click");await closeButton.fire("click");await flush();await openers[1].fire("click");const newLoading=status.textContent;rejectOld(new Error("Abort of prior playback"));await flush();expect("prior-play-promise-does-not-overwrite-new-open",status.textContent===newLoading,{before:newLoading,after:status.textContent});await closeButton.fire("click");await flush();video.play=normalPlay;
const nativeClose=dialog.close;const delayedClose=[];dialog.close=function(){this.open=false;this.removeAttribute("open");delayedClose.push(()=>this.fire("close"));};await openers[0].fire("click");await closeButton.fire("click");await openers[1].fire("click");const currentSource=video.src,currentLoads=video.loadCalls,currentPauses=video.pauseCalls;await delayedClose.shift()();await flush();expect("old-close-event-after-reopen",dialog.open&&video.src===currentSource&&video.hasAttribute("src")&&video.loadCalls===currentLoads&&video.pauseCalls===currentPauses&&doc.activeElement===closeButton,{source:video.src,expectedSource:currentSource,loadDelta:video.loadCalls-currentLoads,pauseDelta:video.pauseCalls-currentPauses,active:doc.activeElement.id});dialog.close=nativeClose;await closeButton.fire("click");await flush();
dialog.showModal=undefined;dialog.close=undefined;openers[0].focus();await openers[0].fire("click");expect("fallback-dialog-focus-close",doc.activeElement===closeButton&&dialog.getAttribute("role")==="dialog"&&dialog.getAttribute("aria-modal")==="false",{active:doc.activeElement.id,status:status.textContent});await doc.fire("keydown",{key:"Escape"});expect("fallback-dialog-escape",!dialog.open&&!video.hasAttribute("src")&&doc.activeElement===openers[0],{open:dialog.open,active:doc.activeElement.id});await openers[0].fire("click");await closeButton.fire("click");expect("fallback-dialog-close-button",!dialog.open&&doc.activeElement===openers[0]&&!video.hasAttribute("src"),{open:dialog.open,active:doc.activeElement.id});
anchor.focus();doc.activeElement=body;await doc.fire("focusin",{target:body});media.matches=true;await media.fire("change");expect("css-blurred-nav-body-to-mobile-menu",doc.activeElement===menu,{active:doc.activeElement.id});
menu.focus();doc.activeElement=body;media.matches=false;await media.fire("change");expect("css-blurred-menu-body-to-desktop-summary",doc.activeElement===summary,{active:doc.activeElement.id});
services.open=true;submenuLink.focus();doc.activeElement=body;media.matches=false;await media.fire("change");expect("css-blurred-submenu-body-to-summary",doc.activeElement===summary&&!services.open,{active:doc.activeElement.id});
anchor.focus();unrelatedInput.focus();doc.activeElement=body;media.matches=true;await media.fire("change");expect("unrelated-focus-clears-navigation-memo",doc.activeElement===body,{active:doc.activeElement.id});
anchor.focus();await doc.fire("pointerdown",{target:cards[0]});doc.activeElement=body;media.matches=true;await media.fire("change");expect("outside-pointer-clears-navigation-memo",doc.activeElement===body,{active:doc.activeElement.id});
anchor.focus();await nav.fire("click",{target:anchor});doc.activeElement=body;media.matches=true;await media.fire("change");expect("same-page-click-resize-before-target-does-not-steal-focus",doc.activeElement===body,{active:doc.activeElement.id});await flush();expect("same-page-click-target-focus-survives-resize",doc.activeElement===brief,{active:doc.activeElement.id});
anchor.focus();doc.pageFocused=false;doc.activeElement=body;media.matches=true;await media.fire("change");expect("background-page-focus-not-reclaimed",doc.activeElement===body,{active:doc.activeElement.id});doc.pageFocused=true;
anchor.focus();await doc.fire("click",{target:cards[0]});doc.activeElement=body;media.matches=true;await media.fire("change");expect("outside-click-clears-navigation-memo",doc.activeElement===body,{active:doc.activeElement.id});
anchor.focus();doc.pageFocused=false;media.matches=true;await media.fire("change");expect("inactive-page-nav-does-not-reassign-focus",doc.activeElement===anchor,{active:doc.activeElement.id});doc.pageFocused=true;
menu.focus();doc.pageFocused=false;media.matches=false;await media.fire("change");expect("inactive-page-menu-does-not-reassign-focus",doc.activeElement===menu,{active:doc.activeElement.id});doc.pageFocused=true;
dialog.reflectOpen=false;delete dialog.open;openers[0].focus();await openers[0].fire("click");
expect("generic-dialog-attribute-open",dialog.hasAttribute("open")&&dialog.open===undefined&&doc.activeElement===closeButton,{open:dialog.hasAttribute("open"),active:doc.activeElement.id});
expect("generic-dialog-nonmodal-semantics",dialog.getAttribute("role")==="dialog"&&dialog.getAttribute("aria-modal")==="false"&&dialog.getAttribute("data-video-fallback")==="true",{role:dialog.getAttribute("role"),modal:dialog.getAttribute("aria-modal")});
video.error={code:4};await video.fire("error");expect("generic-dialog-media-error",status.textContent.startsWith("Video belum dapat dimuat.")&&directSource.href===openers[0].dataset.video,{status:status.textContent});
const genericEscape=await doc.fire("keydown",{key:"Escape"});expect("generic-dialog-escape",!dialog.hasAttribute("open")&&genericEscape.prevented&&genericEscape.stopped&&!video.hasAttribute("src")&&doc.activeElement===openers[0],{open:dialog.hasAttribute("open"),active:doc.activeElement.id});
await openers[1].fire("click");await closeButton.fire("click");expect("generic-dialog-close-button",!dialog.hasAttribute("open")&&!video.hasAttribute("src")&&doc.activeElement===openers[1],{open:dialog.hasAttribute("open"),active:doc.activeElement.id});
await openers[0].fire("click");await doc.fire("keydown",{key:"Escape"});expect("generic-dialog-repeat",!dialog.hasAttribute("open")&&!video.hasAttribute("src")&&doc.activeElement===openers[0],{open:dialog.hasAttribute("open"),active:doc.activeElement.id});
const closedStatus=status.textContent;await video.fire("playing");expect("closed-dialog-playing-ignored",status.textContent===closedStatus,{before:closedStatus,after:status.textContent});
await flush();
const placeField=(top,height=74)=>{briefField.rect={top,bottom:top+height,left:24,right:324,width:300,height};};
const clearTop=()=>header.rect.bottom+8+6,clearBottom=()=>window.visualViewport.offsetTop+window.visualViewport.height-8-6;
placeField(72);briefField.focus();await flush();expect("brief-focus-clears-sticky-header",doc.activeElement===briefField&&briefField.rect.top>=clearTop(),{rect:briefField.rect,lastScroll:window.scrollCalls.at(-1)});
placeField(4720);await window.fire("resize");await flush();expect("brief-resize-reveals-focused-field",doc.activeElement===briefField&&briefField.rect.top>=clearTop()&&briefField.rect.bottom<=clearBottom(),{rect:briefField.rect});
placeField(72);await doc.fire("input",{target:briefField});await flush();expect("brief-edit-reflow-clears-header",doc.activeElement===briefField&&briefField.rect.top>=clearTop(),{rect:briefField.rect});
placeField(850);await doc.fire("change",{target:briefField});await flush();expect("brief-change-clears-bottom",briefField.rect.bottom<=clearBottom()&&doc.activeElement===briefField,{rect:briefField.rect});
placeField(200);let scrollCount=window.scrollCalls.length;briefField.focus();await flush();expect("brief-visible-field-does-not-scroll",window.scrollCalls.length===scrollCount&&doc.activeElement===briefField,{scrolls:window.scrollCalls.length-scrollCount});
unrelatedInput.rect={top:0,bottom:80,left:0,right:100,width:100,height:80};unrelatedInput.focus();scrollCount=window.scrollCalls.length;await window.fire("resize");await flush();expect("brief-helper-ignores-unrelated-controls",window.scrollCalls.length===scrollCount&&doc.activeElement===unrelatedInput,{scrolls:window.scrollCalls.length-scrollCount});
placeField(72);briefField.focus();unrelatedInput.focus();scrollCount=window.scrollCalls.length;await flush();expect("brief-pending-reveal-does-not-follow-stale-focus",window.scrollCalls.length===scrollCount&&doc.activeElement===unrelatedInput,{scrolls:window.scrollCalls.length-scrollCount});
doc.pageFocused=false;placeField(72);briefField.focus();scrollCount=window.scrollCalls.length;await flush();expect("brief-helper-ignores-inactive-page",window.scrollCalls.length===scrollCount,{scrolls:window.scrollCalls.length-scrollCount});doc.pageFocused=true;
window.visualViewport.height=420;placeField(390);await window.visualViewport.fire("resize");await flush();expect("brief-helper-respects-visible-keyboard-viewport",briefField.rect.bottom<=clearBottom()&&doc.activeElement===briefField,{rect:briefField.rect,visibleHeight:window.visualViewport.height});window.visualViewport.height=844;
placeField(0,900);briefField.focus();await flush();expect("brief-oversized-preview-aligns-top",briefField.rect.top>=clearTop()&&doc.activeElement===briefField,{rect:briefField.rect});
header.rect.bottom=120;header.rect.height=120;placeField(73);briefField.focus();await flush();expect("brief-helper-measures-header-height",briefField.rect.top>=clearTop(),{rect:briefField.rect,headerBottom:header.rect.bottom});header.rect.bottom=73;header.rect.height=73;
placeField(72);scrollCount=window.scrollCalls.length;await doc.fire("input",{target:briefField});await doc.fire("change",{target:briefField});await window.fire("resize");const queued=timers.length;await flush();expect("brief-helper-coalesces-one-frame",queued===1&&window.scrollCalls.length===scrollCount+1,{queued,scrolls:window.scrollCalls.length-scrollCount});
briefField.disabled=true;placeField(72);briefField.focus();scrollCount=window.scrollCalls.length;await flush();expect("brief-helper-ignores-disabled-control",window.scrollCalls.length===scrollCount,{scrolls:window.scrollCalls.length-scrollCount});briefField.disabled=false;
briefField.rect={top:72,bottom:72,left:0,right:0,width:0,height:0};briefField.focus();scrollCount=window.scrollCalls.length;await flush();expect("brief-helper-ignores-hidden-control",window.scrollCalls.length===scrollCount,{scrolls:window.scrollCalls.length-scrollCount});
return {results,passed:results.filter(x=>x.pass).length,failed:results.filter(x=>!x.pass).length,limitations:["Controller stub only; browser default focus, CSS, viewport layout, network media, and print rendering not proved.","Escape emulates the native dialog cancel event after document keydown."]};
}
if (typeof module !== 'undefined' && module.exports) module.exports = { runFrontendControllerTests };
