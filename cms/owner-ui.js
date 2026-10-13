/* CMS Owner UI reuses the PR22 prototype model and cloud revision bridge. */
(function(root){
"use strict";
function createModel(labels){
const types=["Layanan"],ids=Object.keys(labels);
labels=Object.freeze({...labels});
let fields={kind:"Layanan",title:"",summary:"",fact:"",source:"",verified:false},order=[],rights=new Set(),cover=null,revision=0,draft=null,previewed=null,approved=null;
function change(){revision++;draft=null;previewed=null;approved=null;}
function view(){return {fields:{...fields},order:order.slice(),rights:[...rights],cover,revision,draftReady:draft===revision,previewReady:previewed===revision,approved:approved===revision};}
function errors(){const e=[];if(!types.includes(fields.kind))e.push({field:"kind",message:"Pilih jenis konten."});if(!fields.title.trim())e.push({field:"title",message:"Isi judul."});if(!fields.summary.trim())e.push({field:"summary",message:"Isi ringkasan."});return e;}
return Object.freeze({
view,labels:Object.freeze(labels),
edit(key,value){if(!Object.hasOwn(fields,key))throw Error("Unknown field");if((key==="verified"&&typeof value!=="boolean")||(key!=="verified"&&typeof value!=="string"))throw Error("Invalid field type");if(fields[key]!==value){fields[key]=value;if(key==="fact"||key==="source")fields.verified=false;change();}},
select(id,on){if(!ids.includes(id))throw Error("Unknown fixture media");const found=order.includes(id);if(!!on!==found){if(on)order.push(id);else{order=order.filter(x=>x!==id);rights.delete(id);if(cover===id)cover=null;}change();}},
right(id,on){if(!order.includes(id))return;const found=rights.has(id);if(!!on!==found){if(on)rights.add(id);else rights.delete(id);change();}},
move(id,delta){const at=order.indexOf(id),to=at+delta;if(![-1,1].includes(delta)||at<0||to<0||to>=order.length)return false;[order[at],order[to]]=[order[to],order[at]];change();return true;},
cover(id){if(id!==null&&!order.includes(id))throw Error("Select media first");if(cover!==id){cover=id;change();}},
draft(){const e=errors();if(e.length)return {ok:false,errors:e};draft=revision;previewed=null;approved=null;return {ok:true};},
preview(){if(draft!==revision)return {ok:false,errors:[{field:"prepare",message:"Siapkan draf sesi untuk revisi terbaru."}]};previewed=revision;return {ok:true,fields:{...fields},order:order.map(id=>({id,label:labels[id],rights:rights.has(id)})),cover};},
approve(){const e=errors();if(previewed!==revision)e.push({field:"preview",message:"Buka pratinjau revisi terbaru."});for(const id of order)if(!rights.has(id))e.push({field:"rights-"+id,message:labels[id]+": hak penggunaan belum disetujui."});if(order.length&&!cover)e.push({field:"cover-"+order[0],message:"Pilih sampul dari media yang dipilih."});if(fields.fact.trim()&&!fields.verified)e.push({field:"verified",message:"Fakta yang diisi belum terverifikasi. Verifikasi atau kosongkan fakta."});if(e.length)return {ok:false,errors:e};approved=revision;return {ok:true};},
queue(){return {ok:false,message:"Antrean ekspor belum terhubung. Belum ada penyimpanan atau publikasi CMS."};},
clear(){fields={kind:"Layanan",title:"",summary:"",fact:"",source:"",verified:false};order=[];rights.clear();cover=null;change();}
});
}
// PR22 state bridge reused; gateway owns identity, persistence and publication.
function createCloudModel(createModel, transport) {
    let model = createModel(), serverRevision = 0, savedSnapshot = null, reviewReady = false, operation = 0, needsReload = false, publication = null;
    const snapshot = () => {
        const v = model.view();
        return {fields: v.fields, order: v.order, rights: v.rights, cover: v.cover};
    };
    // Rights are a set; media order is independently meaningful.
    const fingerprint = s => JSON.stringify({...s, rights: [...s.rights].sort()});
    const saved = () => savedSnapshot !== null && savedSnapshot === fingerprint(snapshot());
    const localFailure = category => ({ok: false, category});
    function rejected(reply, op) {
        if (reply.category === "Conflict" && op === operation) {
            reviewReady = false;
            publication = null;
            savedSnapshot = null;
            needsReload = true;
            model.draft(); // Clear approval/preview without changing fields or either revision.
        }
        return reply;
    }
    function restore(s) {
        const fresh = createModel();
        for (const [key, value] of Object.entries(s.fields)) fresh.edit(key, value);
        for (const id of s.order) fresh.select(id, true);
        for (const id of s.rights) fresh.right(id, true);
        fresh.cover(s.cover);
        fresh.draft();
        return fresh;
    }
    return Object.freeze({
        get model() { return model; },
        view() { return {...model.view(), serverRevision, saved: saved(), needsReload, reviewReady: reviewReady && saved() && model.view().previewReady, publication: publication && publication.revision===serverRevision && publication.fingerprint===fingerprint(snapshot()) && saved() && model.view().approved ? {id:publication.id,status:publication.status} : null}; },
        async load() {
            const op = ++operation, startingModel = model, uiRevision = model.view().revision;
            reviewReady = false;
            const reply = await transport("load", {});
            if (!reply.ok) return rejected(reply, op);
            if (op !== operation || model !== startingModel) return localFailure("Conflict");
            if (model.view().revision !== uiRevision) return localFailure("Unsaved");
            const fresh = reply.state.snapshot === null ? createModel() : restore(reply.state.snapshot);
            model = fresh;
            serverRevision = reply.state.revision;
            savedSnapshot = reply.state.snapshot === null ? null : fingerprint(snapshot());
            reviewReady = false;
            needsReload = false;
            return reply;
        },
        async save() {
            const draft = model.draft();
            if (!draft.ok) return draft;
            const op = ++operation, startingModel = model;
            const sent = snapshot();
            reviewReady = false;
            const reply = await transport("save", {expected_revision: serverRevision, snapshot: sent});
            if (!reply.ok) return rejected(reply, op);
            if (reply.ok) {
                if (op !== operation || model !== startingModel) return localFailure("Conflict");
                serverRevision = reply.state.revision;
                savedSnapshot = fingerprint(sent);
                needsReload = false;
            }
            return reply;
        },
        async preview() {
            if (!saved()) return localFailure("Unsaved");
            const op = ++operation, startingModel = model, startingRevision = serverRevision;
            reviewReady = false;
            const sent = fingerprint(snapshot()), uiRevision = model.view().revision;
            const reply = await transport("preview", {expected_revision: serverRevision});
            if (!reply.ok) return rejected(reply, op);
            if (op !== operation || model !== startingModel || serverRevision !== startingRevision) return localFailure("Conflict");
            if (fingerprint(snapshot()) !== sent || model.view().revision !== uiRevision) return localFailure("Unsaved");
            const preview = model.preview();
            reviewReady = preview.ok;
            return preview.ok ? {...reply, preview} : preview;
        },
        async approve() {
            if (!saved() || !reviewReady || !model.view().previewReady) return localFailure("ReviewRequired");
            const op = ++operation, startingModel = model, startingRevision = serverRevision;
            // The server repeats media/fact/revision checks; no client approval flag is sent.
            const sent = fingerprint(snapshot()), uiRevision = model.view().revision;
            const reply = await transport("approve", {expected_revision: serverRevision});
            if (!reply.ok) return rejected(reply, op);
            if (op !== operation || model !== startingModel || serverRevision !== startingRevision
                || reply.state.revision !== startingRevision) return localFailure("Conflict");
            if (fingerprint(snapshot()) !== sent || model.view().revision !== uiRevision) { reviewReady = false; return localFailure("Unsaved"); }
            const approval = model.approve();
            return approval.ok ? reply : approval;
        },
        async requestPublication() {
            if (!saved() || !reviewReady || !model.view().approved || needsReload) return localFailure("ReviewRequired");
            const op = ++operation, startingModel = model, startingRevision = serverRevision, sent = fingerprint(snapshot());
            const reply = await transport("request-publication", {expected_revision: serverRevision});
            if (!reply.ok) return rejected(reply, op);
            if (op !== operation || model !== startingModel || serverRevision !== startingRevision) return localFailure("Conflict");
            if (fingerprint(snapshot()) !== sent || !model.view().approved) return localFailure("Unsaved");
            publication = {...reply.request,revision:serverRevision,fingerprint:sent};
            return reply;
        }
    });
}

function createTransport(environment) {
const endpoint = new URL("./endpoint.php", environment.location.href);
if (endpoint.origin !== environment.location.origin || endpoint.protocol !== "https:" || endpoint.username || endpoint.password) throw Error("Isolated HTTPS gateway required");
let csrf = null, configuration = null;
const categories = ["Access","Csrf","Conflict","Invalid","Unavailable"];
function validState(state,config) {
if (!state || !Number.isSafeInteger(state.revision) || state.revision < 0 || !["empty","draft","approved"].includes(state.status)) return false;
if (state.snapshot === null) return state.revision === 0 && state.status === "empty";
const s=state.snapshot;
if (!s.fields || s.fields.kind !== "Layanan" || typeof s.fields.verified !== "boolean" || ["title","summary","fact","source"].some(k=>typeof s.fields[k]!=="string")) return false;
if (!Array.isArray(s.order) || !Array.isArray(s.rights) || s.order.length>3 || s.rights.length>3 || new Set(s.order).size!==s.order.length || new Set(s.rights).size!==s.rights.length) return false;
return s.order.every(id=>config.media.some(item=>item.id===id)) && s.rights.every(id=>s.order.includes(id)) && (s.cover===null || s.order.includes(s.cover));
}
function validConfiguration(config) {
if (!config || !config.service || typeof config.service.title!=="string" || typeof config.service.summary!=="string" || ![null,"a","b","c"].includes(config.service.cover) || typeof config.publicationEnabled!=="boolean" || !Array.isArray(config.media) || config.media.length<1 || config.media.length>3) return false;
const seen=new Set();
const valid=config.media.every(item=>{
if (!item || !["a","b","c"].includes(item.id) || seen.has(item.id) || typeof item.label!=="string" || item.label.length<1 || item.label.length>120 || typeof item.src!=="string" || !/^\/assets\/[a-zA-Z0-9_/-]+\.(webp|jpg|jpeg|png)$/.test(item.src)) return false;
const url=new URL(item.src,endpoint);seen.add(item.id);
return url.origin===endpoint.origin && !url.search && !url.hash && !item.src.split("/").some(part=>part===".."||part===".");
});
return valid && (config.service.cover===null || seen.has(config.service.cover));
}
async function request(action,payload) {
if (!["load","save","preview","approve","request-publication"].includes(action)) return {ok:false,category:"Invalid"};
if (action!=="load" && !csrf) return {ok:false,category:"Access"};
const controller=new environment.AbortController(), timer=environment.setTimeout(()=>controller.abort(),12000);
try {
const url=new URL(endpoint.href);
const options={method:action==="load"?"GET":"POST",credentials:"same-origin",mode:"same-origin",redirect:"error",cache:"no-store",signal:controller.signal,headers:{"Accept":"application/json"}};
if (action==="load") url.search="?action=load";
else {options.headers["Content-Type"]="application/json";options.headers["X-CSRF-Token"]=csrf;options.body=JSON.stringify({action,payload});}
const response=await environment.fetch(url.href,options);
if (!response.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return {ok:false,category:response.status===401||response.status===403?"Access":"Unavailable"};
const text=await response.text();
if (text.length>32768) return {ok:false,category:"Unavailable"};
let reply;try {reply=JSON.parse(text);} catch(error) {return {ok:false,category:"Unavailable"};}
if (!reply || reply.ok!==true) {
const category=categories.includes(reply?.category)?reply.category:response.status===401?"Access":"Unavailable";
if (category==="Access"||category==="Csrf") csrf=null;
return {ok:false,category};
}
if (!response.ok) return {ok:false,category:"Unavailable"};
if (action==="load") {
if (typeof reply.csrf!=="string" || !/^[a-zA-Z0-9_-]{32,128}$/.test(reply.csrf) || !validConfiguration(reply.config) || !validState(reply.state,reply.config)) return {ok:false,category:"Unavailable"};
csrf=reply.csrf;configuration=reply.config;
return {ok:true,state:reply.state,config:configuration};
}
if (action==="request-publication") {
if (!reply.request || reply.request.status!=="requested" || typeof reply.request.id!=="string" || !/^[a-zA-Z0-9_-]{1,100}$/.test(reply.request.id)) return {ok:false,category:"Unavailable"};
return {ok:true,request:{id:reply.request.id,status:"requested"}};
}
if (!validState(reply.state,configuration)) return {ok:false,category:"Unavailable"};
return {ok:true,state:reply.state};
} catch(error) {return {ok:false,category:"Unavailable"};}
finally {environment.clearTimeout(timer);}
}
return Object.freeze({request,get configuration(){return configuration;}});
}

function bind(form,environment) {
if (!form || form.dataset.ownerBound) return null;
const document=form.ownerDocument,get=id=>id==="connection"?document.getElementById("owner-connection"):form.querySelector("#owner-"+id);
const ids=["fields","title","summary","fact","source","verified","media","load","discard","baseline","save","preview","approve","request","status","connection","draft-state","review-state","publication-state","revision","output","preview-heading","preview-title","preview-summary","preview-fact","preview-source","preview-media"];
if(ids.some(id=>!get(id)))return null;
form.dataset.ownerBound="true";
let transport;try{transport=createTransport(environment);}catch(error){get("status").textContent="Gateway belum tersedia pada koneksi HTTPS ini. Isian tetap nonaktif.";return null;}
let cloud=null,config=null,busy=false,connected=false,discardArmed=false,discardAction="load";
const messages={Access:"Sesi Owner tidak tersedia atau telah berakhir. Buka kembali halaman melalui akses Owner; edit lokal tetap dipertahankan.",Csrf:"Verifikasi sesi gagal. Muat ulang draf melalui akses Owner sebelum melanjutkan; edit lokal tetap dipertahankan.",Conflict:"Revisi server telah berubah. Edit lokal tetap ada. Muat ulang untuk mengambil revisi terbaru, lalu tinjau ulang.",Invalid:"Draf ditolak. Periksa judul, ringkasan, batas teks, sampul, hak media, dan verifikasi fakta.",Unavailable:"Gateway tidak dapat dihubungi. Hasil operasi belum terkonfirmasi; sambungkan dan muat ulang sebelum mencoba lagi.",Unsaved:"Ada perubahan yang belum tersimpan. Simpan revisi terbaru sebelum review.",ReviewRequired:"Simpan, buka pratinjau, lalu setujui revisi terbaru sebelum mengajukan publikasi."};
function announce(message){get("status").textContent=message;}
function clearErrors(){form.querySelectorAll('[aria-invalid="true"]').forEach(el=>el.removeAttribute("aria-invalid"));}
function showFailure(reply){
clearErrors();
if(reply.errors){for(const error of reply.errors)(get(error.field==="prepare"?"save":error.field)||get("media")).setAttribute("aria-invalid","true");announce(reply.errors.map(error=>error.message).join(" "));get(reply.errors[0].field==="prepare"?"save":reply.errors[0].field)?.focus();}
else announce(messages[reply.category]||"Operasi belum terkonfirmasi.");
if(["Access","Csrf","Unavailable"].includes(reply.category))connected=false;
}
function setFields(){
const v=cloud.view();
for(const key of ["title","summary","fact","source"])get(key).value=v.fields[key];
get("verified").checked=v.fields.verified;
}
function render(){
const v=cloud?.view();
if(v)get("verified").checked=v.fields.verified;
get("fields").disabled=!connected;
for(const action of ["load","baseline","save","preview","approve","request","discard"])get(action).disabled=busy;
get("load").disabled=busy;
get("baseline").disabled=busy||!connected||!config;
get("save").disabled=busy||!connected||!v;
get("preview").disabled=busy||!connected||!v?.saved||v?.needsReload;
get("approve").disabled=busy||!connected||!v?.reviewReady||v?.needsReload||v?.approved;
get("request").disabled=busy||!connected||!config?.publicationEnabled||!v?.approved||!v?.saved||v?.needsReload||!!v?.publication;
get("discard").hidden=!discardArmed;
get("discard").textContent=discardAction==="baseline"?"Buang edit lokal dan isi dari konten publik":"Buang edit lokal dan muat ulang";
get("connection").textContent=connected?"Terhubung ke sesi Owner.":"Belum terhubung ke sesi Owner.";
get("revision").textContent=v?String(v.serverRevision):"—";
get("draft-state").textContent=!v?"Belum dimuat.":v.needsReload?"Revisi server berubah; edit lokal belum aman untuk review.":v.saved?"Draf revisi ini tersimpan privat.":"Perubahan lokal belum tersimpan.";
get("review-state").textContent=v?.approved&&v.saved?"Revisi tersimpan telah disetujui.":v?.reviewReady?"Pratinjau revisi tersimpan telah dibuka; persetujuan diperlukan.":"Review diperlukan untuk revisi tersimpan terbaru.";
get("publication-state").textContent=v?.publication?"Permintaan "+v.publication.id+" diajukan. Publikasi live belum diverifikasi.":config&&!config.publicationEnabled?"Handoff publikasi belum terhubung.":"Belum ada permintaan yang dikonfirmasi pada sesi halaman ini.";
get("output").hidden=!v?.previewReady||!v.saved||v.needsReload;
get("preview").setAttribute("aria-expanded",String(!get("output").hidden));
form.setAttribute("aria-busy",String(busy));
if(v){
const list=get("media"),active=document.activeElement,desired=v.order.concat(config.media.map(item=>item.id).filter(id=>!v.order.includes(id)));
if([...list.children].map(item=>item.dataset.media).join()!==desired.join()){for(const id of desired)list.append(form.querySelector('[data-media="'+id+'"]'));if(active?.isConnected&&!active.disabled)active.focus();}
}
if(v)for(const item of config.media){
const id=item.id,selected=v.order.includes(id),at=v.order.indexOf(id);
get("select-"+id).checked=selected;
get("rights-"+id).disabled=!connected||!selected;
get("rights-"+id).checked=v.rights.includes(id);
get("cover-"+id).disabled=!connected||!selected;
get("cover-"+id).checked=v.cover===id;
get("up-"+id).disabled=!connected||!selected||at===0;
get("down-"+id).disabled=!connected||!selected||at===v.order.length-1;
get("position-"+id).textContent=selected?"Posisi "+(at+1):"Belum dipilih";
}
}
function edit(action){
clearErrors();discardArmed=false;action();render();announce("Perubahan belum tersimpan. Pratinjau dan persetujuan revisi sebelumnya dibatalkan.");
}
function media(){
const list=get("media");list.replaceChildren();
for(const item of config.media){
const li=document.createElement("li"),image=document.createElement("img"),heading=document.createElement("strong"),position=document.createElement("span");
li.dataset.media=item.id;image.src=item.src;image.alt=item.label;image.loading="lazy";image.decoding="async";heading.textContent=item.label;position.id="owner-position-"+item.id;position.className="muted";
li.append(image,heading,position);
for(const [key,label,type] of [["select","Pilih media","checkbox"],["rights","Hak penggunaan sudah ditinjau","checkbox"],["cover","Jadikan sampul","radio"]]){
const control=document.createElement("input"),wrap=document.createElement("label");
control.id="owner-"+key+"-"+item.id;control.type=type;if(type==="radio")control.name="owner-cover";wrap.append(control,document.createTextNode(" "+label));li.append(wrap);
control.addEventListener("change",()=>edit(()=>key==="select"?cloud.model.select(item.id,control.checked):key==="rights"?cloud.model.right(item.id,control.checked):cloud.model.cover(item.id)));
}
const actions=document.createElement("div");actions.className="actions";
for(const [key,label,delta] of [["up","Naik",-1],["down","Turun",1]]){
const button=document.createElement("button");button.type="button";button.id="owner-"+key+"-"+item.id;button.textContent=label;button.setAttribute("aria-label",label+" "+item.label);actions.append(button);
button.addEventListener("click",()=>{edit(()=>cloud.model.move(item.id,delta));const opposite=get((key==="up"?"down":"up")+"-"+item.id);(button.disabled?(opposite.disabled?get("select-"+item.id):opposite):button).focus();});
}
li.append(actions);list.append(li);
}
}
async function operate(action){
if(busy)return;
busy=true;clearErrors();render();
try{
let reply;
if(!cloud){
reply=await transport.request("load",{});
if(reply.ok){
config=reply.config;const labels=Object.fromEntries(config.media.map(item=>[item.id,item.label]));let first=reply;
cloud=createCloudModel(()=>createModel(labels),async(method,payload)=>{if(method==="load"&&first){const value=first;first=null;return value;}return transport.request(method,payload);});
reply=await cloud.load();media();
}
}else reply=await (action==="request"?cloud.requestPublication():cloud[action]());
if(!reply.ok){showFailure(reply);return;}
connected=true;discardArmed=false;
if(action==="load"){config=transport.configuration||config;if(reply.state.snapshot===null){cloud.model.edit("title",config.service.title);cloud.model.edit("summary",config.service.summary);if(config.service.cover){cloud.model.select(config.service.cover,true);cloud.model.cover(config.service.cover);}}setFields();announce(reply.state.snapshot===null?"Konten publik saat ini dimuat sebagai edit lokal. Tinjau hak sampul, lalu simpan draf privat.":"Draf privat dimuat. Buka pratinjau untuk review revisi tersimpan.");}
else if(action==="save")announce("Draf revisi "+cloud.view().serverRevision+" tersimpan privat. Belum dipublikasikan.");
else if(action==="preview"){
const preview=reply.preview,getLabel=id=>config.media.find(item=>item.id===id).label;
get("preview-title").textContent=preview.fields.title;get("preview-summary").textContent=preview.fields.summary;
get("preview-fact").textContent=preview.fields.fact||"Belum dicantumkan";get("preview-source").textContent=preview.fields.source||"Belum dicantumkan";
get("preview-media").textContent=preview.order.length?preview.order.map(item=>getLabel(item.id)+(item.id===preview.cover?" · Sampul":"")+(item.rights?" · Hak ditinjau":" · Hak belum ditinjau")).join("\n"):"Tanpa sampul. Halaman layanan akan memakai perilaku gambar kosong yang ditinjau backend.";
announce("Pratinjau revisi tersimpan siap. Periksa teks, media, dan fakta sebelum menyetujui.");
}
else if(action==="approve")announce("Revisi tersimpan disetujui. Perubahan berikutnya membatalkan persetujuan.");
else if(action==="request")announce("Permintaan publikasi diajukan. Halaman publik belum dinyatakan berubah; tunggu bukti publisher.");
}catch(error){connected=false;showFailure({ok:false,category:"Unavailable"});}finally{busy=false;render();if(action==="preview"&&!get("output").hidden)get("preview-heading").focus();}
}
for(const key of ["title","summary","fact","source","verified"])get(key).addEventListener(key==="verified"?"change":"input",()=>{if(cloud)edit(()=>cloud.model.edit(key,key==="verified"?get(key).checked:get(key).value));});
get("load").addEventListener("click",()=>{if(cloud&&!cloud.view().saved){discardArmed=true;discardAction="load";render();announce("Muat ulang akan mengganti edit lokal. Pilih Buang edit lokal dan muat ulang bila Anda yakin.");return;}operate("load");});
function baseline(){if(!cloud||!config)return;edit(()=>{cloud.model.clear();cloud.model.edit("title",config.service.title);cloud.model.edit("summary",config.service.summary);if(config.service.cover){cloud.model.select(config.service.cover,true);cloud.model.cover(config.service.cover);}});setFields();announce("Konten publik saat ini disalin menjadi edit lokal. Tinjau hak sampul, simpan, lalu review sebelum mengajukan publikasi.");}
get("discard").addEventListener("click",()=>discardAction==="baseline"?baseline():operate("load"));
get("baseline").addEventListener("click",()=>{if(cloud&&!cloud.view().saved){discardArmed=true;discardAction="baseline";render();announce("Mengisi dari konten publik akan mengganti edit lokal. Konfirmasikan pembuangan edit untuk melanjutkan.");return;}baseline();});
for(const action of ["save","preview","approve","request"])get(action).addEventListener("click",()=>operate(action));
form.addEventListener("submit",event=>event.preventDefault());
render();operate("load");
return Object.freeze({get model(){return cloud;},ready:()=>!busy&&connected});
}

const api=Object.freeze({createModel,createCloudModel,createTransport,bind});
if(typeof module==="object"&&module.exports)module.exports=api;else root.KanCmsOwner=api;
if(root.document){const form=root.document.querySelector("[data-cms-owner]");if(form)bind(form,root);}
})(typeof globalThis==="object"?globalThis:this);
