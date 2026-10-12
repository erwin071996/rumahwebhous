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
dan cocok, termasuk state commit sukses sebelumnya. Penulisan state yang gagal
juga memicu rollback, walaupun unggahan source dan pemeriksaan halaman sudah
berhasil. Field previous_successful_commit dan successful_release_commit
mencatat commit sebelum dan sesudah deploy; field kedua hanya ada jika seluruh
transaksi berhasil.

Jika pemulihan gagal karena jaringan/server tidak tersedia, baca
deployment-result/rollback-plan.json. Pulihkan hanya touched_paths menggunakan
file di deployment-result/before/ ke /public_html/. File yang memiliki
before_existed: false harus dihapus jika masih ada setelah transfer gagal.
Cocokkan hash dan halaman live setelah pemulihan.

State server-only berada pada /public_html/includes/.3dkan-deployment-state.json.
Pulihkan salinan state dari before/ jika state.before_existed bernilai true.
Jika sebelumnya state belum ada, hapus hanya file state yang baru tercipta
sesuai rollback-plan.json. Jangan menebak commit sukses dari push sebelumnya
atau menyalin state ke repository publik. State yang rusak, commit yang tidak
tersedia, atau commit di luar riwayat checkout menghentikan deploy.

Saat state belum ada, workflow hanya dapat mendaftarkan baseline yang semua
hash/metadata-nya cocok dengan snapshot dan lolos verifikasi live. Workflow
akan menolak perubahan penanda metadata sampai tahap baseline tersebut sukses.

Backup lengkap sebelum sinkronisasi juga tersedia secara lokal pada arsip
sync-work/live-snapshot/3dkan-before-changes.zip di workspace pekerjaan ini.
Arsip tersebut tidak masuk ke repository publik dan mencakup seluruh regular
file hosting, termasuk file khusus server. Database dan konfigurasi akun hosting
berada di luar cakupan backup file ini.
