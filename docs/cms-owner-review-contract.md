# Neon Box: kontrak review dan pengajuan publikasi

Kontrak ini memakai API foundation pada commit [`1463609379967383ff7d7f2e56e144b3a2ba8209`](https://github.com/erwin071996/rumahwebhous/tree/1463609379967383ff7d7f2e56e144b3a2ba8209). Gateway tetap bertanggung jawab atas autentikasi, sesi, CSRF, dan penyimpanan privat. Dokumen ini tidak membuktikan bahwa gateway atau hosting telah diaktifkan.

## Receipt review lintas request

`DraftReview` memiliki field `revision` dan `fingerprint`. `DraftAdapter::approve()` mensyaratkan objek review yang diterbitkan oleh **instance adapter yang sama**. Objek dari request sebelumnya atau objek baru dengan nilai identik ditolak. Jangan serialize adapter atau melemahkan pemeriksaan identitas objek.

Saat review ditampilkan, simpan receipt pada sesi server. Ikat receipt pada pemilik/sesi, `service_id` bernilai `neon-box`, `revision`, `fingerprint`, `prev_release`, dan masa berlaku. Snapshot yang ditampilkan harus cocok dengan review itu; bila `load()` dan `review()` terpisah, pastikan revisinya sama. Identity, expiry, hasil CSRF, dan receipt tidak boleh dipercaya dari form/header.

Pada request pengajuan baru, rekonstruksi konteks dari sesi tepercaya dan buat review baru. Cocokkan review baru dengan receipt yang benar-benar ditampilkan, lalu approve memakai objek baru tersebut pada instance yang sama. Contoh berikut hanya urutan kontrak; fungsi gateway merupakan pseudocode, bukan endpoint baru.

```text
ctx = trustedOwnerContextFromSession()
requireOwnerSession(ctx)
requireValidCsrfForMutation()
receipt = serverSession.review_receipt
requireReceiptOwnerSessionAndExpiry(receipt)
require(receipt.service_id == "neon-box")
expectedRevision = requireIntegerSubmittedRevision()
currentRelease = trustedLatestSuccessfulRelease()
require(expectedRevision == receipt.revision)
require(currentRelease == receipt.prev_release)
adapter = makeDraftAdapterWithTrustedBaselineAndPhotoMap(currentRelease)
freshReview = adapter.review(ctx, now, expectedRevision)
require(freshReview.revision == receipt.revision)
requireConstantTimeEqual(freshReview.fingerprint, receipt.fingerprint)
approved = adapter.approve(ctx, now, expectedRevision, freshReview)
descriptor = pilot.export(ctx, now, expectedRevision, currentRelease)
request = enqueueOnceForSolePublisher(descriptor)
showPublicationRequestedAfterDurableHandoff(request)
```

`pilot` pada pseudocode adalah instance `Pilot` yang dipakai oleh `adapter`. Receipt hilang, kedaluwarsa, berbeda, atau berasal dari sesi lain menghentikan pengajuan. Membuat fresh review lalu langsung approve tanpa membandingkan receipt lama tidak mempertahankan bukti isi yang ditinjau.

## Revisi dan pembatalan

`save()` memakai `expectedRevision`. Save berhasil menaikkan `revision`, menetapkan `status` menjadi `draft`, dan mengosongkan `approval`. Gateway harus menghapus receipt review dan membatalkan atau menandai usang pengajuan revisi sebelumnya. `Conflict` tidak boleh diatasi dengan menimpa state atau retry otomatis memakai revisi terbaru.

`prev_release` mengikat draf pada release sebelumnya; `baseline_sha256` mengikat baseline publik. Perubahan release/baseline memerlukan rekonsiliasi dan review ulang. Fingerprint review mengikat revisi, release, isi publik, dan metadata editorial privat; receipt harus tetap privat dan tidak menjadi kredensial autentikasi.

## Satu publisher dan status

`Pilot::export()` menghasilkan tepat `path`, `bytes`, `sha256`, `source_rev`, dan `prev_release`. Path publik tetap `includes/refresh-data.json`; private note, receipt, dan identitas sesi tidak masuk payload publik atau Git.

- Satu publisher tetap menggabungkan dan merilis. Gateway mencatat pengajuan privat dan tidak membuat penulis produksi kedua.
- Deduplicasikan handoff dengan tuple `(service_id, source_rev, prev_release, sha256)`. Pengajuan ulang tuple yang sama menggunakan pengajuan yang sudah ada.
- Sebelum pengajuan dikonsumsi, publisher memvalidasi ulang `status == approved`, `revision == source_rev`, release berhasil terbaru cocok dengan `prev_release`, dan hash output cocok dengan `sha256`. Descriptor lama saja tidak cukup. Edit atau perubahan release membatalkan pengajuan usang.
- `approved` adalah status internal yang membolehkan ekspor. Handoff tersimpan dapat ditampilkan sebagai **Diajukan untuk publikasi**. Ekspor atau antrean tidak berarti `published`; laporkan berhasil terbit hanya setelah commit/deployment berhasil dan output publik terverifikasi.

Kriteria integrasi: dua request terpisah berhasil untuk draf yang sama; receipt/sesi/CSRF tidak valid, revisi usang, dan release berubah ditolak; pengajuan duplikat tidak menghasilkan dua rilis; edit membatalkan pengajuan lama; status terbit membutuhkan bukti rilis.

Sumber API: [DraftAdapter dan DraftReview](https://github.com/erwin071996/rumahwebhous/blob/1463609379967383ff7d7f2e56e144b3a2ba8209/cms/neon_box_draft_adapter.php), [Pilot dan OwnerContext](https://github.com/erwin071996/rumahwebhous/blob/1463609379967383ff7d7f2e56e144b3a2ba8209/cms/neon_box_pilot.php).
