# Mengubah konten dan aset terpusat

Panduan ini memakai SharedBrand dan Pilot NEON-BOX yang sudah ada. Backend
tetap satu-satunya integrator dan penerbit. Fixture CMS berjalan di cloud CLI;
belum ada antarmuka CMS produksi atau endpoint untuk Owner.

| Perubahan | Sumber yang dikendalikan | Hasil / batas saat ini |
| --- | --- | --- |
| Nama merek, warna, tipografi, navigasi, footer, kontak, CTA, label shell | `config/site-brand.json`: `brand`, `colors`, `typography`, `navigation`, `footer`, `contact`, `cta`, `layout`, `shell` | Backend membangun shell bersama untuk 500 route; tidak perlu mengedit setiap halaman. |
| Logo dan favicon | Path publik dalam `brand.logo_primary` dan `brand.favicon_path`, beserta berkas aset yang dirujuk | Logo memiliki dimensi, revisi, SHA-256 master dan identitas turunan layar. Penggantian aset/hash ditinjau Backend sesuai guard yang berlaku. |
| Konten layanan dan foto yang disetujui | `public_html/includes/refresh-data.json`: `services` dan `photos` | Sumber publik terkontrol; foto memiliki ID dan path aset. Penambahan foto/hak pakai masuk review Backend, bukan unggahan dari fixture. |
| Draf NEON-BOX | `cms/neon_box_draft_adapter.php` → `cms/neon_box_pilot.php`, state privat fixture | Hanya jenis `Layanan`, record `neon-box`: `title` → `name`, `summary` → `intro`, sampul → `image`. Fakta/sumber/verifikasi/urutan/hak media tetap metadata privat. |

`public_html/includes/site-brand.json`, `refresh-header.html`,
`refresh-footer.html`, `refresh-brand-head.html`, `shared-brand.php`,
`public_html/assets/ui/brand-tokens.css`, binding shell halaman, dan
`docs/shared-brand-build.json` adalah keluaran build SharedBrand. Ubah input
terpusat lalu bangun ulang melalui Backend; jangan mengedit salinan keluaran
secara terpisah. Template/pipeline/shared/theme juga berada dalam kepemilikan Backend.

## Alur perubahan merek/aset

1. Tentukan perubahan publik dan aset yang hak pakainya sudah jelas.
2. Backend memperbarui sumber terpusat beserta identitas aset yang tepat.
3. Backend membangun, memeriksa diff dan menjalankan guard terhadap baseline
   yang dipin; konten utama, SEO, route dan sumber beku tetap dilindungi.
4. Serahkan draft PR dengan SHA dan bukti uji. Backend melakukan merge/rilis;
   status live baru dicatat setelah rilis dan pemeriksaan hosting berhasil.

Perintah dari root repo, untuk digunakan Backend pada checkout integrasi:

```sh
python scripts/build_shared_brand.py --repo .
python scripts/build_shared_brand.py --repo . --check
```

Jika build memerlukan sumber baseline asli, gunakan checkout terpisah pada SHA
`base_commit` di `config/shared-brand-inputs.json` (saat ini `dd31d730…`):

```sh
python scripts/build_shared_brand.py --repo . --baseline /tmp/shared-brand-baseline
python scripts/check_shared_brand.py --baseline-dir /tmp/shared-brand-baseline/public_html --candidate-dir public_html --repo-dir . --output /tmp/shared-brand-check.json
```

`--baseline` menerima root checkout; `--baseline-dir` menerima `public_html`
baseline. Guard saat ini membekukan sejumlah aset dan `refresh-data.json`;
perubahan konten/logo di luar scope rilis memerlukan kontrak review Backend
yang sesuai, bukan penggantian baseline atau penghapusan assertion agar lolos.

## Alur draf NEON-BOX dalam fixture

Buat/edit → simpan → muat ulang → preview revisi tersimpan → approve revisi
yang sama. Setiap simpan membatalkan persetujuan. Pada `Conflict`, edit lokal
dipertahankan dan `needsReload` menandai perlunya muat ulang sebelum review ulang.

`symbol`, `body`, `options`, `guide` dan SEO/detail tetap berasal dari baseline;
fixture tidak menyediakan editor untuk bidang tersebut, artikel atau proyek.
Media `a`/`b`/`c` adalah data sintetis uji, bukan daftar foto produksi. Approval
memerlukan hak setiap media terpilih, sampul bila ada pilihan, dan verifikasi
fakta yang diisi. Pemetaan foto nyata serta perilaku tanpa sampul perlu keputusan
integrasi Backend. Tidak ada uploader atau galeri publik dari urutan media.

Preview/approval mengikat revisi dan keluaran; export hanya menghasilkan JSON
publik tersanitasi untuk penerbit Backend. Draf, hasil uji dan export belum
berarti terpublikasi. Mock `OwnerContext` bukan autentikasi Owner nyata.
Kontrak dan cara uji fokus tersedia di [CLOUD_FIXTURE.md](CLOUD_FIXTURE.md).

## Baseline paket integrasi CMS

Paket ini diselaraskan dengan `main` pada `c700dae84430ceae55ab6746e9fe51cbebfa2eda`;
tree `public_html` identik dan Pilot/suite49/README tetap cocok dengan hash guard.
Workflow CMS masih memakai `059a441…`. Handoff Backend: pin baseline public-tree
ke `c700dae…`, dengan scope seluruh `public_html`, exact-head dan hash tetap utuh.
Pin CMS ini berbeda dari pin sumber build SharedBrand `dd31d730…` di atas.
