# 3DKan Advertising website

Repository utama source website https://www.3dkanadvertising.store.

Source yang diunggah ke Rumahweb berada di public_html/. Baseline diambil
langsung melalui FTPS baca-saja pada 12 Oktober 2026, setelah website memiliki
500 URL, 11 sitemap, 400 panduan baru, 14 alat bantu, dan 3 halaman toko.
Hash, ukuran, dan waktu perubahan source tersimpan di
deployment/live-baseline.json.

Pengembangan dilakukan melalui branch dan pull request. CI memeriksa source,
sitemap, dependensi, dan mekanisme rollback. Merge ke main menjalankan
**Deploy to Rumahweb via FTPS**. Deploy pertama hanya mencocokkan baseline
terhadap server. Deploy selanjutnya hanya mengunggah file website yang berubah,
setelah isi server cocok dengan source sebelum perubahan. Source yang berubah
di luar GitHub membuat deploy berhenti sebelum penimpaan.

File khusus hosting, log, state FTP, ACME, dan dokumen pribadi tidak masuk ke
source publik dan tetap berada di server. Workflow tidak melakukan pembersihan
file server. Workflow terpisah dari pekerjaan sebelumnya disimpan sebagai teks
di docs/legacy-workflows/; hanya workflow utama yang menulis ke hosting.

Validasi lokal:

    python scripts/check_site.py
    python -m unittest discover -s tests -v

Kredensial tetap berada di GitHub Secrets: FTP_SERVER, FTP_USERNAME,
FTP_PASSWORD. Jangan menaruh kredensial pada source, laporan, atau PR.

Jika unggahan atau verifikasi gagal, deploy memulihkan file yang disentuh dan
membandingkan kembali isinya melalui FTPS. Bukti deploy dan salinan sebelum
perubahan tersimpan sebagai artifact GitHub Actions selama 14 hari.

Lihat docs/rollback.md untuk pemulihan perubahan uji.
