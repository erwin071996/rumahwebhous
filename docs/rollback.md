# Rollback perubahan uji

Baseline adalah source live terbaru yang diimpor pada 12 Oktober 2026.
Jangan mengembalikan seluruh PR sinkronisasi ke main lama, karena main lama
tidak memuat source 500 halaman dan memiliki beberapa workflow deploy terpisah.

Setelah baseline diterima, branch rollback/live-baseline-20261012 menyimpan
commit baseline tanpa penanda metadata pengujian.

Untuk menghapus penanda uji, buat PR yang mengembalikan hanya
public_html/index.html ke versi branch baseline, jalankan validasi, lalu merge.
Workflow utama akan mengunggah hanya file tersebut dan memverifikasi kembali
FTPS, halaman live, serta 500 URL dalam 11 sitemap.

Jika deploy gagal setelah mulai menulis, script mencoba memulihkan salinan
sebelumnya secara otomatis. Periksa deployment-result/result.json dalam
artifact Actions: rollback: verified berarti setiap file telah dibaca balik
dan cocok. Jika pemulihan gagal karena jaringan/server tidak tersedia, gunakan
file di deployment-result/before/ untuk mengembalikan hanya file yang disentuh
ke /public_html/, lalu cocokkan hash dan halaman live.

Backup lengkap sebelum sinkronisasi juga tersedia secara lokal pada arsip
sync-work/live-snapshot/3dkan-before-changes.zip di workspace pekerjaan ini.
Arsip tersebut tidak masuk ke repository publik dan mencakup seluruh regular
file hosting, termasuk file khusus server. Database dan konfigurasi akun hosting
berada di luar cakupan backup file ini.
