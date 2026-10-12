<?php
// File untuk testing semua URL SEO
require_once 'includes/config.php';

echo "<h1>Daftar Semua URL SEO yang Akan Terindex</h1>";
echo "<p>Total: " . (count($produk) * count($kota_sulsel) + count($produk) + count($kota_sulsel) + 1) . " halaman</p>";

echo "<h2>1. Halaman Utama</h2>";
echo "<a href='{$config['site_url']}' target='_blank'>{$config['site_url']}</a>";

echo "<h2>2. Halaman Produk</h2>";
foreach ($produk as $slug => $data) {
    echo "<a href='{$config['site_url']}/layanan/$slug' target='_blank'>{$config['site_url']}/layanan/$slug</a><br>";
}

echo "<h2>3. Halaman Kota</h2>";
foreach ($kota_sulsel as $slug => $nama) {
    echo "<a href='{$config['site_url']}/kota/$slug' target='_blank'>{$config['site_url']}/kota/$slug</a><br>";
}

echo "<h2>4. Halaman Produk + Kota</h2>";
foreach ($produk as $p_slug => $p_data) {
    foreach ($kota_sulsel as $k_slug => $k_nama) {
        echo "<a href='{$config['site_url']}/layanan/$p_slug/$k_slug' target='_blank'>{$config['site_url']}/layanan/$p_slug/$k_slug</a><br>";
    }
}

echo "<h2>5. Sitemap</h2>";
echo "<a href='{$config['site_url']}/sitemap.xml' target='_blank'>{$config['site_url']}/sitemap.xml</a>";
?>