/* Progressive enhancement: links, page content and FAQ work without JavaScript. */
(() => {
  'use strict';
  const phone = '6285340382029';
  const whatsapp = text => `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
  const nav = document.getElementById('site-nav');
  const toggle = document.querySelector('.menu-toggle');
  function closeMenu() { if(nav) nav.removeAttribute('data-open'); if(toggle) toggle.setAttribute('aria-expanded','false'); }
  if(toggle && nav) {
    toggle.addEventListener('click', () => { const open=toggle.getAttribute('aria-expanded')!=='true'; toggle.setAttribute('aria-expanded',String(open)); nav.toggleAttribute('data-open',open); });
    nav.addEventListener('click', e => { if(e.target.closest('a')) closeMenu(); });
    document.addEventListener('click', e => { if(!e.target.closest('.site-header')) closeMenu(); });
    window.matchMedia('(min-width:961px)').addEventListener('change',closeMenu);
  }
  document.addEventListener('keydown', e => { if(e.key==='Escape') closeMenu(); });

  // Preserve the owner's existing Google Ads conversion ID. Never hold navigation hostage to tracking.
  function trackWhatsApp(label) {
    try { if(typeof window.gtag==='function') window.gtag('event','conversion', {send_to:'AW-467644163/EkKjCNSo_90bEIPe_t4B', event_label:label||'website_whatsapp', transport_type:'beacon'}); } catch (_) { /* Chat still works when analytics is blocked. */ }
  }
  document.addEventListener('click', e => { const a=e.target.closest('a[href]'); if(a && a.href.startsWith(`https://wa.me/${phone}`)) trackWhatsApp((a.textContent||'WhatsApp').trim()); });
  const form=document.getElementById('quote-form');
  if(form) form.addEventListener('submit', e => {
    e.preventDefault(); if(!form.reportValidity()) return;
    const data=new FormData(form);
    const text=`Halo 3DKan Advertising, saya ingin konsultasi:\n\nNama/usaha: ${String(data.get('nama')||'').trim()}\nKebutuhan: ${data.get('layanan')}\nUkuran: ${String(data.get('ukuran')||'').trim()||'Belum ditentukan'}\nLokasi: ${String(data.get('lokasi')||'').trim()}\nCatatan: ${String(data.get('catatan')||'').trim()||'-'}\n\nMohon informasi pilihan bahan, estimasi biaya, dan jadwal pengerjaan.`;
    trackWhatsApp('form_konsultasi'); window.location.assign(whatsapp(text));
  });

  const dialog=document.getElementById('gallery-dialog'); let lastTrigger=null;
  if(dialog && typeof dialog.showModal==='function') {
    document.addEventListener('click', e => {
      const a=e.target.closest('a[data-gallery]'); if(!a) return;
      e.preventDefault(); lastTrigger=a;
      const img=document.getElementById('dialog-image'); img.src=a.href; img.alt=a.dataset.title||'Contoh produk 3DKan';
      document.getElementById('dialog-title').textContent=a.dataset.title||'Contoh produk';
      document.getElementById('dialog-kind').textContent=a.dataset.kind||'Contoh visual';
      document.getElementById('dialog-wa').href=whatsapp(`Halo 3DKan Advertising, saya ingin konsultasi model ${a.dataset.title||'produk'} ini.\nReferensi: ${a.href}\nUkuran dan lokasi pemasangan: `);
      dialog.showModal(); document.documentElement.style.overflow='hidden';
    });
    dialog.querySelector('.dialog-close').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('click',e=>{ if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();} });
    dialog.addEventListener('close',()=>{document.documentElement.style.overflow='';if(lastTrigger)lastTrigger.focus();});
  }

  const grid=document.getElementById('project-grid'); if(!grid) return;
  const search=document.getElementById('gallery-search'); const count=document.getElementById('gallery-count'); const empty=document.getElementById('gallery-empty'); const subBox=document.getElementById('subcategory-filters');
  let active='all', sub='all';
  const cards=()=>Array.from(grid.querySelectorAll('.project-card'));
  function apply(){const term=(search?.value||'').trim().toLocaleLowerCase('id');let n=0;cards().forEach(card=>{const visible=(active==='all'||card.dataset.category===active)&&(sub==='all'||card.dataset.subcategory===sub)&&((card.dataset.search||'').includes(term));card.hidden=!visible;if(visible)n++;});if(count)count.textContent=`${n} visual ditampilkan`;if(empty)empty.hidden=n!==0;}
  function subFilters(){if(!subBox)return;subBox.replaceChildren();if(active==='all')return;const values=[...new Set(cards().filter(x=>x.dataset.category===active).map(x=>x.dataset.subcategory))];if(values.length<2)return;['all',...values].forEach(value=>{const b=document.createElement('button');b.type='button';b.className='filter'+(value==='all'?' active':'');b.textContent=value==='all'?'Semua bahan':value;b.setAttribute('aria-pressed',String(value==='all'));b.addEventListener('click',()=>{sub=value;subBox.querySelectorAll('button').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});apply();});subBox.appendChild(b);});}
  document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{active=b.dataset.filter;sub='all';document.querySelectorAll('[data-filter]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});subFilters();apply();}));
  if(search){search.addEventListener('input',apply);const initial=new URLSearchParams(location.search).get('q');if(initial)search.value=initial;}
  apply();
  // Keep the original auto-discovery behaviour, without fictional placeholder images.
  const seed=document.getElementById('gallery-seed'); let aliases=new Set();
  try{JSON.parse(seed?.textContent||'[]').forEach(p=>(p.aliases||[]).forEach(a=>aliases.add(a)));}catch(_){/* Existing HTML remains available. */}
  fetch('/portfolio.php',{credentials:'same-origin',cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('Gallery endpoint unavailable');return r.json();}).then(paths=>{
    if(!Array.isArray(paths))return;
    for(const path of paths){
      if(typeof path!=='string'||aliases.has(path)||path.includes('..')||path.startsWith('/')||path.includes('://')||path.includes('\\')||path.startsWith('Testimoni/'))continue;
      aliases.add(path);const parts=path.split('/');let category=parts[0]==='Huruf-Timbul'?'Huruf Timbul':parts[0]==='Neon-Box'?'Neon Box':parts[0]==='Nametage akrilik'?'Nametag':parts[0].replace(/[-_]/g,' ');
      const material=(parts.length>2?parts[1]:'Custom').replace(/^(Huruf|Hurur|HURUF)-[Tt][Ii][Mm][Bb][Uu][Ll]-/,'').replace(/[-_]/g,' ');const title=`${category} ${material}`;
      const url='/foto-produk/'+parts.map(encodeURIComponent).join('/');const card=document.createElement('article');card.className='project-card';card.dataset.category=category;card.dataset.subcategory=material;card.dataset.search=(title+' '+category).toLowerCase();
      const a=document.createElement('a');a.className='project-image';a.href=url;a.dataset.gallery='auto';a.dataset.title=title;a.dataset.kind='Visual tambahan';a.setAttribute('aria-label',`Lihat ${title}`);
      const img=document.createElement('img');img.src=url;img.alt=title;img.loading='lazy';img.decoding='async';a.appendChild(img);
      const caption=document.createElement('div');caption.className='project-caption';const label=document.createElement('span');label.className='eyebrow';label.textContent='Visual tambahan';const h=document.createElement('h3');h.textContent=title;const p=document.createElement('p');p.textContent='Spesifikasi dikonfirmasi saat pemesanan';caption.append(label,h,p);card.append(a,caption);grid.appendChild(card);
    }
    apply();
  }).catch(()=>{ /* Keep server-rendered verified images. */ });
})();

(()=>{const menu=document.querySelector(".nav-services");if(!menu)return;document.addEventListener("click",e=>{if(!menu.contains(e.target)||e.target.closest("a"))menu.open=false});document.addEventListener("keydown",e=>{if(e.key==="Escape")menu.open=false})})();

/* Search adds no remote analytics or form submission; all results come from this site's public index. */
(()=>{
 'use strict';
 const bp=window.matchMedia('(min-width:1021px)');bp.addEventListener('change',()=>{document.querySelector('#site-nav')?.removeAttribute('data-open');document.querySelector('.menu-toggle')?.setAttribute('aria-expanded','false');});
 const form=document.querySelector('.knowledge-search');if(!form)return;
 const input=document.querySelector('#knowledge-query'),box=document.querySelector('#knowledge-results'),status=document.querySelector('#search-status');let data=null,filtered=[],shown=0,delay;
 const more=document.createElement('button');more.type='button';more.className='btn btn-outline search-more';more.textContent='Tampilkan lebih banyak';more.hidden=true;box.after(more);
 const norm=s=>String(s).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('id');
 function renderNext(){const end=Math.min(shown+18,filtered.length);for(let i=shown;i<end;i++){const row=filtered[i];if(!/^\/[a-zA-Z0-9/._-]*$/.test(row.url))continue;const a=document.createElement('a');a.className='article-card';a.href=row.url;const k=document.createElement('span');k.className='eyebrow';k.textContent=row.category==='tutorial'?'Panduan praktis':row.category;const h=document.createElement('h3');h.textContent=row.title;const p=document.createElement('p');p.textContent=row.description;const link=document.createElement('span');link.className='text-link';link.textContent='Buka halaman ↗';a.append(k,h,p,link);box.append(a);}shown=end;more.hidden=shown>=filtered.length;}
 async function search(){const q=input.value.trim().slice(0,120);status.textContent='Memuat indeks panduan…';try{if(!data){const r=await fetch('/assets/marketing-20261006/search-index.json',{credentials:'same-origin'});if(!r.ok)throw Error('index');data=await r.json();if(!Array.isArray(data))throw Error('format');}const words=norm(q).split(/\s+/).filter(Boolean);filtered=data.filter(x=>typeof x.url==='string'&&typeof x.title==='string'&&words.every(w=>norm(x.title+' '+x.description+' '+x.category).includes(w)));box.replaceChildren();shown=0;status.textContent=q?`${filtered.length} halaman untuk “${q}”.`:`${filtered.length} halaman tersedia. Ketik topik untuk mempersempit hasil.`;renderNext();}catch(_){status.textContent='Pencarian belum dapat dimuat. Jelajahi kategori dan alat di bawah; halaman panduan tetap tersedia.';more.hidden=true;}}
 form.addEventListener('submit',e=>{e.preventDefault();clearTimeout(delay);search();});input.addEventListener('input',()=>{clearTimeout(delay);delay=setTimeout(search,220);});more.addEventListener('click',renderNext);const initial=new URLSearchParams(location.search).get('q');if(initial)input.value=initial.slice(0,120);search();
})();
