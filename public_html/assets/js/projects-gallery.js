/* ===================================================
   PROJECTS GALLERY – FINAL STABLE VERSION
   Aman untuk masonry + lazyload + rename folder
=================================================== */

document.addEventListener('DOMContentLoaded', () => {

  const grid   = document.getElementById('projectGrid');
  const catBox = document.getElementById('categoryFilters');
  const subBox = document.getElementById('subcategoryFilters');
  const search = document.getElementById('searchInput');

  if(!grid) return;

  let ALL = [];
  let ACTIVE = 'ALL';
  let ACTIVE_SUB = 'ALL';

  /* ================= UTIL ================= */

  function formatLabel(t){
    return t.replace(/[-_]/g,' ')
            .replace(/\b\w/g,c=>c.toUpperCase());
  }

  function parseImage(path){
    const p = path.split('/');
    p.pop(); // filename

    const category = p[0] || 'Produk';
    const subcategory = p[1] || p[0];

   return {
  url: '/' + path.replace(/^\/+/,''),
  category: formatLabel(category),
  subcategory: formatLabel(subcategory)
};
  }

  function finalName(i){
    return (i.category === i.subcategory)
      ? i.category
      : `${i.category} ${i.subcategory}`;
  }

  /* ================= RENDER ================= */

  function render(list){
    grid.innerHTML = '';

    list.forEach(i=>{
      const title = finalName(i);

      const wrap = document.createElement('div');
      wrap.className = 'masonry-item';
      wrap.innerHTML = `
        <div class="pin shadow hover:shadow-xl cursor-pointer">
          <img
            src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300'%3E%3C/svg%3E"
            data-src="${i.url}"
            alt="${title}"
            title="${title}"
            class="lazy w-full bg-slate-300 rounded-xl">
          <div class="overlay">
            <div class="flex justify-end">
              <span class="bg-white/90 text-slate-800 px-3 py-1 rounded-full text-sm">
                Lihat
              </span>
            </div>
            <div>
              <h3 class="font-semibold leading-tight">${title}</h3>
              <p class="text-xs opacity-80">${i.category} • ${i.subcategory}</p>
            </div>
          </div>
        </div>
      `;
      wrap.onclick = ()=> openModal(i, title);
      grid.appendChild(wrap);
    });

    lazyLoad();
  }

  /* ================= LAZY LOAD ================= */

  function lazyLoad(){
    const imgs = document.querySelectorAll('img.lazy');

    const io = new IntersectionObserver(entries=>{
      entries.forEach(e=>{
        if(e.isIntersecting){
          e.target.src = e.target.dataset.src;
          e.target.classList.remove('lazy');
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: '200px' });

    imgs.forEach(img=>io.observe(img));
  }

  /* ================= FILTER ================= */

  function setupCategories(){
    catBox.innerHTML = '';
    subBox.innerHTML = '';

    const cats = [...new Set(ALL.map(i=>i.category))];

    addCat('Semua', ()=>{
      ACTIVE='ALL'; ACTIVE_SUB='ALL';
      subBox.innerHTML='';
      apply();
    }, true);

    cats.forEach(c=>{
      addCat(c, ()=>{
        ACTIVE=c; ACTIVE_SUB='ALL';
        buildSub(c); apply();
      });
    });
  }

  function buildSub(cat){
    subBox.innerHTML='';
    const subs=[...new Set(
      ALL.filter(i=>i.category===cat).map(i=>i.subcategory)
    )];

    if(subs.length<=1) return;

    subs.forEach(s=>{
      const b=document.createElement('button');
      b.textContent=s;
      b.className='px-4 py-1 rounded-full bg-slate-200 hover:bg-slate-300 text-sm';
      b.onclick=()=>{ACTIVE_SUB=s; apply();};
      subBox.appendChild(b);
    });
  }

  function addCat(t, fn, active){
    const b=document.createElement('button');
    b.textContent=t;
    b.className=active
      ?'px-4 py-2 rounded-full bg-blue-600 text-white'
      :'px-4 py-2 rounded-full bg-slate-200 hover:bg-slate-300';
    b.onclick=()=>{
      [...catBox.children].forEach(x=>
        x.className='px-4 py-2 rounded-full bg-slate-200 hover:bg-slate-300'
      );
      b.className='px-4 py-2 rounded-full bg-blue-600 text-white';
      fn();
    };
    catBox.appendChild(b);
  }

  /* ================= SEARCH ================= */

  if(search){
    search.addEventListener('input', apply);
  }

  function apply(){
    const q = search.value.toLowerCase();
    let r = ALL;

    if(ACTIVE!=='ALL') r = r.filter(i=>i.category===ACTIVE);
    if(ACTIVE_SUB!=='ALL') r = r.filter(i=>i.subcategory===ACTIVE_SUB);
    if(q) r = r.filter(i=>finalName(i).toLowerCase().includes(q));

    render(r);
  }

  /* ================= INIT ================= */

  fetch('portfolio.php')
    .then(r=>r.json())
    .then(list=>{
      ALL = list.map(parseImage);
      setupCategories();
      render(ALL);
    })
    .catch(()=>{
      grid.innerHTML = '<p class="text-center text-slate-500">Gagal memuat galeri.</p>';
    });

});
