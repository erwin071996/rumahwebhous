# 3DKan Advertising website

Repository utama source website https://www.3dkanadvertising.store.

Source yang diunggah ke Rumahweb berada di public_html/. Baseline diambil
langsung melalui FTPS baca-saja pada 12 Oktober 2026, setelah website memiliki
500 URL, 11 sitemap, 400 panduan baru, 14 alat bantu, dan 3 halaman toko.
Hash, ukuran, dan waktu perubahan source tersimpan di
deployment/live-baseline.json.

Pengembangan dilakukan melalui branch dan pull request. CI memeriksa source,
sitemap, dependensi, dan mekanisme rollback. Merge ke main menjalankan
**Deploy to Rumahweb via FTPS**. Deploy pertama mencocokkan baseline terhadap
server, memverifikasi halaman live, lalu mencatat commit baseline yang berhasil.
Perubahan uji baru boleh dideploy setelah pencatatan baseline berhasil.
Deploy selanjutnya membandingkan source dengan commit terakhir yang berhasil
di server, kemudian hanya mengunggah file yang berubah setelah isi server cocok
dengan source commit tersebut. Perubahan dari commit yang gagal tetap ikut dalam
deploy berikutnya. Source yang berubah di luar GitHub membuat deploy berhenti
sebelum penimpaan.

Commit deploy sukses tersimpan hanya di server pada
includes/.3dkan-deployment-state.json, di dalam direktori yang diblokir dari HTTP.
File ini tidak masuk source publik. State baru ditulis setelah verifikasi FTPS
dan halaman live berhasil; SHA dari push sebelumnya tidak dianggap bukti deploy
sukses. Commit state harus tersedia dalam riwayat Git checkout dan menjadi
ancestor commit yang akan dideploy.

File khusus hosting, log, state FTP, ACME, dan dokumen pribadi tidak masuk ke
source publik dan tetap berada di server. Workflow tidak melakukan pembersihan
file server. Workflow terpisah dari pekerjaan sebelumnya disimpan sebagai teks
di docs/legacy-workflows/; hanya workflow utama yang menulis ke hosting.

Validasi lokal:

    python scripts/check_site.py
    python -m unittest discover -s tests -v

Kredensial FTP_USERNAME dan FTP_PASSWORD tetap berada di GitHub Secrets.
Tujuan Rumahweb ditetapkan pada workflow dan diperiksa sebelum koneksi.
Jangan menaruh kredensial pada source, laporan, atau PR.

Jika unggahan, verifikasi, atau penulisan state gagal, deploy memulihkan file
yang disentuh beserta state sebelumnya, kemudian membandingkan kembali isinya
melalui FTPS. Bukti deploy, rollback-plan.json, dan salinan sebelum perubahan
tersimpan sebagai artifact GitHub Actions selama 14 hari.

Lihat docs/rollback.md untuk pemulihan perubahan uji.
