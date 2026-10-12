<?php
require_once __DIR__ . '/includes/tracking-query.php';
// Existing /layanan/... and /kota/... URLs are preserved. No user-provided HTML is rendered.
$data = json_decode(file_get_contents(__DIR__ . '/includes/refresh-data.json'), true);
if (!is_array($data)) { http_response_code(503); exit('Halaman sementara tidak tersedia.'); }
function e($value) { return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function j($value) { return json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT); }
function wa_link($message) { return 'https://wa.me/6285340382029?text=' . rawurlencode($message); }
$domain = $data['domain']; $asset = $data['asset'];
$prod = isset($_GET['produk']) && is_string($_GET['produk']) ? strtolower($_GET['produk']) : '';
$city = isset($_GET['kota']) && is_string($_GET['kota']) ? strtolower($_GET['kota']) : '';
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if (preg_match('~^/layanan/([a-z0-9-]+)(?:/([a-z0-9-]+))?/?$~i', $path, $m)) { $prod = strtolower($m[1]); $city = isset($m[2]) ? strtolower($m[2]) : ''; }
elseif (preg_match('~^/kota/([a-z0-9-]+)/?$~i', $path, $m)) { $city = strtolower($m[1]); $prod = ''; }
$invalid = (isset($_GET['produk']) && !is_string($_GET['produk'])) || (isset($_GET['kota']) && !is_string($_GET['kota'])) || ($prod !== '' && !isset($data['services'][$prod])) || ($city !== '' && !isset($data['cities'][$city])) || ($prod === '' && $city === '');
if ($invalid) { http_response_code(404); header('X-Robots-Tag: noindex, follow'); readfile(__DIR__ . '/404.html'); exit; }
if ($city !== '') { header('Location: ' . $domain . '/kota/' . $city . kan_tracking_query() . ($prod !== '' ? '#layanan-' . $prod : ''), true, 301); exit; }
$service = $prod !== '' ? $data['services'][$prod] : null;
$cityName = $city !== '' ? $data['cities'][$city] : '';
$canonical = $domain . ($prod !== '' ? '/layanan/' . $prod . ($city !== '' ? '/' . $city : '') : '/kota/' . $city);
if ($path !== parse_url($canonical, PHP_URL_PATH)) { header('Location: ' . $canonical . kan_tracking_query(), true, 301); exit; }
$title = ($service ? 'Jasa ' . $service['name'] : 'Jasa Signage') . ($cityName ? ' di ' . $cityName : '') . ' | 3DKan Advertising';
$h1 = ($service ? $service['name'] : 'Signage untuk usaha Anda') . ($cityName ? ' di ' . $cityName : '. Dibuat sesuai kebutuhan Anda.');
$description = $service ? 'Konsultasi ' . strtolower($service['name']) . ($cityName ? ' untuk ' . $cityName : ' di Sulawesi Selatan') . '. Bahas desain, bahan, ukuran, biaya, serta pemasangan bersama 3DKan Advertising.' : 'Layanan huruf timbul, neon box, papan nama, dan signage untuk ' . $cityName . '. Konfirmasi produksi, pengiriman, serta pemasangan lewat WhatsApp 3DKan.';
$image = null;
if ($service && $service['image']) { foreach ($data['photos'] as $photo) { if ($photo['id'] === $service['image']) { $image = $photo; break; } } }
$crumbs = [['@type'=>'ListItem','position'=>1,'name'=>'Beranda','item'=>$domain.'/']];
if ($service) { $crumbs[] = ['@type'=>'ListItem','position'=>2,'name'=>$service['name'],'item'=>$domain.'/layanan/'.$prod]; }
if ($cityName) { $crumbs[] = ['@type'=>'ListItem','position'=>count($crumbs)+1,'name'=>$cityName,'item'=>$canonical]; }
$graph = [$data['organization'], ['@context'=>'https://schema.org','@type'=>'BreadcrumbList','itemListElement'=>$crumbs]];
if ($service) { $graph[] = ['@context'=>'https://schema.org','@type'=>'Service','name'=>$service['name'] . ($cityName ? ' untuk '.$cityName : ''),'serviceType'=>$service['name'],'url'=>$canonical,'description'=>$description,'provider'=>['@id'=>$domain.'/#organization'],'areaServed'=>['@type'=>'AdministrativeArea','name'=>$cityName ?: 'Sulawesi Selatan']]; }
// New service/city combinations remain usable but are not promoted as mass-created landing pages.
$robots = $prod && $city && !in_array($prod,$data['legacy_services'],true) ? 'noindex,follow' : 'index,follow,max-image-preview:large';
?>
<!doctype html><html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($title) ?></title><meta name="description" content="<?= e($description) ?>"><meta name="robots" content="<?= e($robots) ?>">
<link rel="canonical" href="<?= e($canonical) ?>"><meta name="theme-color" content="#14202e">
<link rel="icon" href="<?= e($asset) ?>/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/marketing-20261006/site.css"><script src="/assets/marketing-20261006/site.js" defer></script>
<meta property="og:type" content="website"><meta property="og:locale" content="id_ID"><meta property="og:site_name" content="3DKan Advertising"><meta property="og:title" content="<?= e($title) ?>"><meta property="og:description" content="<?= e($description) ?>"><meta property="og:url" content="<?= e($canonical) ?>"><meta property="og:image" content="<?= e($domain . ($image ? $image['large'] : $data['photos'][0]['large'])) ?>"><meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json"><?= j($graph) ?></script>
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-467644163"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','AW-467644163');</script>
</head><body><?php readfile(__DIR__.'/includes/refresh-header.html'); ?>
<main id="main"><section class="page-intro"><div class="container"><nav class="breadcrumbs" aria-label="Jejak halaman"><a href="/">Beranda</a><span aria-hidden="true">/</span><?php if ($service): ?><a href="<?= e('/layanan/'.$prod) ?>"><?= e($service['name']) ?></a><?php endif; ?><?php if ($cityName): ?><span><?= e($cityName) ?></span><?php endif; ?></nav>
<p class="eyebrow"><?= $cityName ? 'WILAYAH LAYANAN · '.e($cityName) : 'LAYANAN 3DKAN' ?></p><h1><?= e($h1) ?></h1><p><?= e($service ? $service['intro'] : 'Desain, produksi, dan pemasangan huruf timbul, neon box, serta identitas usaha. Kirim kebutuhan dan lokasi untuk membahas penawaran yang sesuai.') ?></p></div></section>
<section class="section"><div class="container">
<?php if ($service): ?>
<div class="service-detail-grid"><div class="service-copy"><p class="eyebrow">PILIHAN UNTUK USAHA ANDA</p><h2><?= e($service['name']) ?> sesuai desain dan bidang pemasangan.</h2><p><?= e($service['body']) ?></p>
<ul class="options-list"><?php foreach ($service['options'] as $option): ?><li><?= e($option) ?></li><?php endforeach; ?></ul>
<div class="service-note"><h3>Yang perlu disiapkan sebelum memesan</h3><p><?= e($service['guide']) ?></p></div>
<?php if ($cityName): ?><h2 style="margin-top:32px">Koordinasi proyek di <?= e($cityName) ?></h2><p>Kirim foto bidang, ukuran, dan alamat titik pemasangan di <?= e($cityName) ?>. Untuk pengiriman atau pemasangan, akses kendaraan, ketinggian pekerjaan, kondisi bidang, serta kesiapan lokasi akan dibahas sebelum jadwal disepakati.</p><p class="area-note">Halaman ini menjelaskan wilayah layanan. Tidak menyatakan adanya cabang atau workshop di <?= e($cityName) ?>.</p><?php endif; ?>
</div><aside class="service-aside">
<?php if ($image): ?><div class="service-photo"><img src="<?= e($image['src']) ?>" srcset="<?= e($image['src']) ?> 640w, <?= e($image['large']) ?> 1200w" sizes="(max-width:760px) 90vw, 480px" width="<?= e($image['width']) ?>" height="<?= e($image['height']) ?>" alt="<?= e($image['title']) ?>" loading="eager" decoding="async"></div><p class="image-footnote"><?= e($image['kind']) ?>. Bahan dan hasil akhir disesuaikan dengan pesanan.</p><?php endif; ?>
<div class="info-card"><h2>Bahas spesifikasi & penawaran</h2><p>Harga mengikuti bahan, ukuran, jumlah, detail desain, serta lingkup pengiriman dan pemasangan. Ketentuan pembayaran dan garansi dikonfirmasi dalam penawaran.</p><a class="btn btn-primary" href="<?= e(wa_link('Halo 3DKan Advertising, saya ingin konsultasi '.$service['name'].($cityName ? ' untuk lokasi '.$cityName : '').'. Ukuran dan kebutuhan saya: ')) ?>" target="_blank" rel="noopener noreferrer">Konsultasi WhatsApp ↗</a><a class="text-link" href="/projects.html">Lihat galeri produk ↗</a></div></aside></div>
<?php else: ?>
<div class="value-grid"><div><p class="eyebrow">KONSULTASI UNTUK <?= e($cityName) ?></p><h2>Mulai dari kebutuhan di lokasi Anda.</h2><p class="section-lead">Kebutuhan penanda toko, kantor, dan organisasi di <?= e($cityName) ?> bisa dibahas sejak tahap desain. Pilih jenis layanan lalu kirim ukuran, foto bidang, serta titik pemasangan.</p><p>Pengiriman, survei, dan pemasangan tidak otomatis termasuk dalam semua harga produk. Kami merinci lingkup pekerjaan, akses lokasi, serta biaya dalam penawaran.</p><p class="area-note">Daftar wilayah layanan bukan daftar cabang. Kunjungan workshop dan jadwal kerja perlu dikonfirmasi terlebih dahulu.</p></div><div class="info-card"><h2>Sebelum menghubungi kami</h2><ul class="options-list"><li>Logo atau teks yang ingin dibuat</li><li>Ukuran dan jumlah produk</li><li>Foto bidang serta alamat lokasi</li><li>Pilihan bahan atau referensi desain</li><li>Target waktu penggunaan</li></ul><a class="btn btn-primary" href="<?= e(wa_link('Halo 3DKan Advertising, saya ingin konsultasi signage untuk lokasi '.$cityName.'.')) ?>" target="_blank" rel="noopener noreferrer">Konsultasi untuk <?= e($cityName) ?> ↗</a></div></div>
<h2 style="margin-top:56px">Layanan yang bisa Anda diskusikan.</h2><div class="service-grid"><?php foreach ($data['services'] as $slug=>$item): ?><a class="service-card" href="<?= e('/layanan/'.$slug.(in_array($slug,$data['legacy_services'],true) ? '/'.$city : '')) ?>"><span class="service-symbol" aria-hidden="true"><?= e($item['symbol']) ?></span><h3><?= e($item['name']) ?></h3><p><?= e($item['intro']) ?></p><span class="text-link">Lihat layanan ↗</span></a><?php endforeach; ?></div>
<?php endif; ?>
</div></section><section class="section section-soft"><div class="container"><p class="eyebrow">JELAJAHI LEBIH LANJUT</p><h2><?= $service && !$cityName ? 'Koordinasi layanan di Sulawesi Selatan.' : 'Pilihan lain untuk identitas usaha Anda.' ?></h2><div class="related-links">
<?php if ($service && !$cityName): foreach ($data['cities'] as $slug=>$name): ?><a href="<?= e('/kota/'.$slug) ?>"><?= e($name) ?></a><?php endforeach; else: foreach ($data['services'] as $slug=>$item): if($slug===$prod)continue; ?><a href="<?= e('/layanan/'.$slug) ?>"><?= e($item['name']) ?></a><?php endforeach; endif; ?>
<a href="/wilayah.html">Semua wilayah layanan ↗</a></div></div></section></main>
<?php readfile(__DIR__.'/includes/refresh-footer.html'); ?></body></html>
