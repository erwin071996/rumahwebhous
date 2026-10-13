# Paket berikutnya: Neon Box → Gadget Solution → brief

Status: **rancangan satu tahap untuk integrasi Backend; belum diterapkan atau dipublikasikan.** Marketing menyiapkan prioritas dan penerimaan. Backend adalah satu-satunya integrator/penerbit. Paket ini melengkapi konten existing; tidak membuat artikel baru atau theme terpisah.

## Satu sasaran terukur

Naikkan kelengkapan jalur terpilih dari **1/2 menjadi 2/2 tautan kontekstual yang mencapai tujuan benar**: layanan → bukti Gadget Solution → formulir brief. Tautan harus berada dekat blok bukti yang relevan; navigasi umum/header/footer tidak masuk hitungan. Ini ukuran teknis kesiapan alur, bukan conversion rate pengunjung.

Baseline source pada SHA `dd31d7305d1571b4fde960ed0b942135a88388a1`, diperiksa 13 Oktober 2026:

| Perpindahan | Bukti | Nilai |
|---|---|---|
| `/layanan/neon-box` → `/projects.html#gadget-solution` | `services.neon-box.detail_sections` di `public_html/includes/refresh-data.json` mempunyai tautan tepat; artikel dengan ID tujuan ada di `public_html/projects.html`. | 1/1 |
| Kartu `#gadget-solution` → `#brief-proyek` | Kartu mempunyai CTA WhatsApp dan tautan balik ke layanan; belum ada CTA langsung ke brief. Formulir `#brief-proyek` sudah ada di halaman yang sama. | 0/1 |

Pembacaan [layanan live](https://www.3dkanadvertising.store/layanan/neon-box) dan [proyek live](https://www.3dkanadvertising.store/projects.html#gadget-solution) mendukung isi dan arah CTA tersebut. Fragmen/href tepat dibuktikan dari repo. Bukti terarah ada di [baseline JSON](neon-box-brief-baseline-20261013.json). Permintaan HTTPS mentah dari shell diblokir proxy dengan 403; kecocokan byte source dengan live tidak diverifikasi. Tidak tersedia laporan kunjungan, penyusunan brief, chat diterima, lead, atau penjualan dalam bahan tugas ini; baseline bisnis belum diketahui.

## Prioritas dan isi paket

Prioritas tunggal: beri langkah penyusunan brief di titik pengunjung sudah melihat bukti proyek. Pertahankan blok Neon Box → Gadget yang sudah ada; cukup satu tambahan CTA dan petunjuk pada kartu proyek existing.

- CTA: **“Siapkan brief neon box”**, `href="#brief-proyek"`, dekat dokumentasi Gadget Solution pada `public_html/projects.html`. Pakai komponen shared theme Backend.
- Petunjuk: **“Pilih Neon box pada brief. Di Ringkasan kebutuhan, tulis ‘Referensi visual: Gadget Solution’, ukuran perkiraan, jumlah unit, lokasi, serta ketersediaan logo dan foto bidang. Tandai ukuran yang belum final.”**
- Caption bila diperlukan: **“Dokumentasi Gadget Solution: neon box bulat terpasang dan menyala. Foto menjadi referensi visual; ukuran, bahan, lampu, dan lingkup pesanan Anda dikonfirmasi tersendiri.”**

Pengguna memilih jenis dan menulis referensi sendiri. Rancangan ini tidak menjanjikan prefill URL, penyimpanan, atau pengiriman otomatis. Jenis “Neon box” sudah tersedia pada formulir; ukuran/jumlah unit dapat ditulis di Ringkasan kebutuhan. Kolom “Jumlah titik” tetap berarti titik pemasangan.

Gunakan foto existing `public_html/assets/portfolio-real/clean/gadget-solution-neonbox.webp`; inspeksi visual memperlihatkan bentuk bulat, tulisan Gadget Solution, dan kondisi menyala. Video existing `public_html/assets/portfolio-real/videos/gadget-solution-neonbox.mp4` boleh tetap sebagai dokumentasi pendamping; playback belum diuji pada pekerjaan Marketing ini. Kedua aset tercatat dan ditautkan kartu proyek; hash ada di baseline JSON. Tanggal 1 Mei 2026 merupakan catatan halaman, bukan verifikasi metadata pengambilan. Jangan menambah ukuran/material proyek, harga, garansi, testimoni, atau hasil bisnis yang belum terbukti. Jangan mengganti dokumentasi dengan gambar buatan.

## Pembagian pekerjaan satu tahap

**Konten & SEO:** terapkan CTA/petunjuk singkat di kartu existing menggunakan fakta/aset di atas; koordinasikan agar tidak membuka artikel atau URL kedua. **Backend:** setelah shared theme menyediakan komponen CTA dan posisi anchor yang stabil, integrasikan paket ini, catat SHA kandidat, lakukan uji terarah, dan tentukan publikasi. Marketing tidak menyunting runtime, tracking/consent, atau workflow.

**Dependensi untuk Backend dan parent:** paket siap diimplementasikan, tetapi penerimaan fungsi/tampilan menunggu kandidat shared theme. Pertahankan ID `gadget-solution`, `brief-proyek`, dan formulir yang sudah ada, atau perbarui seluruh tautan terkait dalam integrasi yang sama. Backend mengembalikan SHA kandidat serta bukti uji; parent memantau hasil melalui draft PR. Hasil uji kandidat dan bukti live setelah publikasi harus dicatat terpisah.

## Penerimaan singkat

1. Pada SHA kandidat yang dicatat, kedua perpindahan tepat mencapai kartu Gadget lalu bagian formulir: **2/2**. CTA proyek bisa difokuskan dan diaktifkan dengan keyboard; tujuan brief tidak tertutup header shared theme.
2. Pada lebar 390 dan 1280 px, foto/caption/petunjuk/CTA terbaca tanpa tumpang tindih. Dua screenshot menjadi bukti tampilan; pengaktifan tautan diuji tersendiri.
3. Uji dengan data sintetis: pilih “Neon box”, tulis “Referensi visual: Gadget Solution; diameter belum diukur; 1 unit; lokasi uji; logo tersedia”, lalu “Susun pesan”. Pratinjau mempertahankan jenis, referensi, dan status ukuran. Berhenti di pratinjau; jangan menghubungi pelanggan.
4. Instruksi memeriksa pesan dan menekan Kirim di WhatsApp tetap jelas. Penyusunan pratinjau atau pembukaan WhatsApp tidak dilaporkan sebagai chat terkirim, lead, atau penjualan. Backend mencatat hasil kandidat dan, bila sudah menerbitkan, pemeriksaan live atas jalur yang sama.

Validasi Marketing yang selesai: parsing terarah JSON/HTML atas dua perpindahan, keberadaan anchor/aset dan SHA-256, inspeksi foto, serta pembacaan teks live. Uji UI, JavaScript/form, keyboard, mobile, dan penerimaan 2/2 masih pekerjaan integrasi; tidak ada audit, backup, iklan, atau tes besar ulang. `README.md` dibaca; tidak ditemukan `AGENTS.md` atau skill repo, dan `/workspace/.agents` kosong saat diperiksa.
