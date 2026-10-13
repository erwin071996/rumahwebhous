# Pengujian gateway CMS: dukungan portabel

Paket Python standar ini menyiapkan 17 vektor auth, sesi, CSRF, expiry, dan
penolakan SID yang dicabut. Paket tidak mengimplementasikan gateway atau
publisher. Jalankan dari folder ini dengan Python 3.10 atau lebih baru:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 test_harness.py
PYTHONDONTWRITEBYTECODE=1 python3 gateway_harness.py backend_adapter_stub.py
```

Self-test memakai HTTP test double sintetis. Status 200/403, cookie, header,
identitas, clock, dan SHA yang dipakai self-test hanya milik fixture. Hasilnya
membuktikan kualitas harness, bukan keamanan gateway Backend atau hosting.
Stub sengaja keluar dengan **exit 2: blocked** sampai kontrak nyata tersedia.

Backend mengisi adapter fixture lokal yang menyediakan:

- `create_adapter()`, `base_url` loopback literal dengan port eksplisit, dan
  `describe()` yang mencantumkan SHA kandidat gateway, action map nyata untuk
  load/save/review/request_publish, serta fixture sesi dan clock sintetis.
- `prepare(vector_id)` yang mereset fixture dan mengembalikan `Check` berisi
  `Request` serta `Expectation`. Isi route, payload, status HTTP, dan penanda
  penolakan dari kontrak gateway; harness tidak menebaknya.
- `state_fingerprint()` yang membaca hanya state fixture: draf, outbox, dan
  counter pembacaan privat. Hash file saja tidak membuktikan bahwa penolakan
  terjadi sebelum pembacaan. Sertakan sentinel privat sintetis sebagai nilai
  yang dilarang muncul dalam respons.

Impor `Check`, `Request`, dan `Expectation` dari `gateway_harness`. Adapter
boleh memakai body JSON atau form/HTML sesuai kontrak nyata. Seluruh sesi,
cookie, CSRF, dan state harus sintetis. Jangan gunakan credential, password,
cookie login, token API, atau path hosting produksi.

Runner membatasi koneksi ke `127.0.0.1`/`::1`, menolak target publik serta
userinfo, tidak memakai proxy lingkungan, dan tidak mengikuti redirect.
Laporan hanya menampilkan nama kasus, kategori, jumlah, dan SHA kandidat.
Gateway lokal baru lulus jika 17 vektor selesai tanpa fail/blocked. Login nyata,
rotasi SID, atribut cookie, HTTPS, bukti hosting, dan publikasi tetap perlu
verifikasi terpisah oleh Backend/Pemeriksa. Backend utama tetap integrator
dan penerbit tunggal.

Pada kasus logout, seed SID revoked hanya membuktikan penolakan SID tersebut.
Untuk memeriksa handler logout kandidat, adapter harus melakukan logout
fixture sebelum permintaan reuse. Jangan logout hosting.
