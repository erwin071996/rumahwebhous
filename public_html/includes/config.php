<?php
// ============================================
// KONFIGURASI DATA UNTUK SEO OTOMATIS
// SEMUA DATA DIAMBIL DARI WEBSITE ASLI
// ============================================

$config = [
    'site_url' => 'https://www.3dkanadvertising.store',
    'site_name' => '3DKan Advertising',
    'phone' => '0853-4038-2029',
    'email' => 'info@3dkanadvertising.store',
    'whatsapp' => '6285340382029',
    'instagram' => 'https://www.instagram.com/3dkan.advertising?igsh=MXJsMTc1MHF1Zm0zYw==',
    'tiktok' => 'https://www.tiktok.com/@3dkan.advertising?_r=1&_t=ZS-92WZNMirC9Q',
    'google_maps' => 'https://maps.app.goo.gl/AocDFawAFkoxcevT7',
    'address' => 'Workshop: Jl. Poros Makassar-Maros, Sulawesi Selatan'
];

// Data produk/layanan (diambil dari index.html)
$produk = [
    'huruf-timbul' => [
        'nama' => 'Huruf Timbul',
        'icon' => 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
        'deskripsi' => 'Huruf timbul akrilik, stainless steel, kuningan dengan pencahayaan LED untuk usaha dan kantor.',
        'keyword' => 'huruf timbul, akrilik, stainless steel, signage, branding',
        'kategori' => [
            'Huruf Timbul Stainless Steel 304',
            'Huruf Timbul Akrilik Premium',
            'Huruf Timbul ACP (Aluminum Composite Panel)',
            'Huruf Timbul Kuningan & Tembaga',
            'Huruf Timbul Backlit (Cahaya dari Dalam)',
            'Custom Desain Huruf Timbul 3D'
        ]
    ],
    'neon-box' => [
        'nama' => 'Neon Box',
        'icon' => 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
        'deskripsi' => 'Neon box advertising dengan pencahayaan terang untuk promosi usaha 24 jam.',
        'keyword' => 'neon box, lightbox, akrilik, LED, pencahayaan',
        'kategori' => [
            'Neon Box Akrilik Backlit LED',
            'Neon Box Full Color RGB',
            'Neon Box Custom Shape (Bulat, Oval, Unik)',
            'Neon Box dengan Remote Control',
            'Neon Box Waterproof untuk Outdoor',
            'Neon Box dengan Efek Animasi'
        ]
    ],
    'reklame' => [
        'nama' => 'Reklame',
        'icon' => 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
        'deskripsi' => 'Reklame indoor outdoor, billboard, spanduk, banner untuk promosi skala besar.',
        'keyword' => 'reklame, billboard, spanduk, banner, papan iklan',
        'kategori' => [
            'Reklame Billboard Outdoor',
            'Reklame Spanduk & Banner',
            'Reklame Digital Printing',
            'Reklame UV Printing pada Akrilik',
            'Reklame Lightbox (Kotak Cahaya)',
            'Reklame Pylon Sign (Tiang Tinggi)'
        ]
    ],
    'nametag' => [
        'nama' => 'Nametag',
        'icon' => 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
        'deskripsi' => 'Papan nama usaha, kantor, instansi dengan material premium dan desain custom.',
        'keyword' => 'nametag, akrilik, signage, kantor, office',
        'kategori' => [
            'Nametag Akrilik Illuminasi',
            'Nametag Stainless Steel',
            'Nametag Kayu dengan Laser Cut',
            'Nametag LED Backlit',
            'Nametag Marmer & Granit',
            'Nametag Custom 3D'
        ]
    ]
];

// Data kota Sulawesi Selatan (24 kabupaten/kota)
$kota_sulsel = [
    'makassar' => ['nama' => 'Makassar', 'tipe' => 'Kota'],
    'gowa' => ['nama' => 'Gowa', 'tipe' => 'Kabupaten'],
    'maros' => ['nama' => 'Maros', 'tipe' => 'Kabupaten'],
    'takalar' => ['nama' => 'Takalar', 'tipe' => 'Kabupaten'],
    'jeneponto' => ['nama' => 'Jeneponto', 'tipe' => 'Kabupaten'],
    'bantaeng' => ['nama' => 'Bantaeng', 'tipe' => 'Kabupaten'],
    'bulukumba' => ['nama' => 'Bulukumba', 'tipe' => 'Kabupaten'],
    'sinjai' => ['nama' => 'Sinjai', 'tipe' => 'Kabupaten'],
    'bone' => ['nama' => 'Bone', 'tipe' => 'Kabupaten'],
    'wajo' => ['nama' => 'Wajo', 'tipe' => 'Kabupaten'],
    'soppeng' => ['nama' => 'Soppeng', 'tipe' => 'Kabupaten'],
    'parepare' => ['nama' => 'Parepare', 'tipe' => 'Kota'],
    'pangkajene-dan-kepulauan' => ['nama' => 'Pangkajene dan Kepulauan', 'tipe' => 'Kabupaten'],
    'barru' => ['nama' => 'Barru', 'tipe' => 'Kabupaten'],
    'pinrang' => ['nama' => 'Pinrang', 'tipe' => 'Kabupaten'],
    'sidenreng-rappang' => ['nama' => 'Sidenreng Rappang', 'tipe' => 'Kabupaten'],
    'enrekang' => ['nama' => 'Enrekang', 'tipe' => 'Kabupaten'],
    'luwu' => ['nama' => 'Luwu', 'tipe' => 'Kabupaten'],
    'luwu-utara' => ['nama' => 'Luwu Utara', 'tipe' => 'Kabupaten'],
    'luwu-timur' => ['nama' => 'Luwu Timur', 'tipe' => 'Kabupaten'],
    'toraja-utara' => ['nama' => 'Toraja Utara', 'tipe' => 'Kabupaten'],
    'tana-toraja' => ['nama' => 'Tana Toraja', 'tipe' => 'Kabupaten'],
    'palopo' => ['nama' => 'Palopo', 'tipe' => 'Kota']
];

// Data gambar produk dari projects.html
$gambar_produk = [
    'huruf-timbul' => [
        'foto-produk/Huruf-Timbul/Huruf-Timbul-Akrilik/akrilik1.jpg',
        'foto-produk/Huruf-Timbul/Huruf-Timbul-Stainless/stainless1.jpg',
        'foto-produk/Huruf-Timbul/Huruf-Timbul-Acp/acp1.jpg'
    ],
    'neon-box' => [
        'foto-produk/Neon-Box/Neon-Box-Akrilik/neon-akrilik1.jpg',
        'foto-produk/Neon-Box/Neon-Box-Akrilik/Bulat/neon-bulat1.jpg'
    ],
    'nametag' => [
        'foto-produk/Nametage akrilik/nametag1.jpg'
    ]
];

// Fungsi generate konten SEO otomatis
function generateSeoContent($produk_nama = '', $kota_nama = '', $tipe_kota = '') {
    if ($produk_nama && $kota_nama) {
        $title = "Jasa {$produk_nama} di {$kota_nama} | 3DKan Advertising - Spesialis Signage Sulawesi Selatan";
        $desc = "3DKan Advertising - Jasa pembuatan {$produk_nama} profesional di {$kota_nama}. Material premium, desain custom, garansi hingga 3 Bulan. Hubungi 0853-4038-2029 untuk konsultasi gratis.";
        
        $content = "
        <h2 class=\"text-2xl sm:text-3xl font-extrabold mb-3\">Jasa Pembuatan {$produk_nama} di {$kota_nama}</h2>
        
        <div class=\"prose prose-lg max-w-none mb-6\">
            <p class=\"text-gray-600 mb-4\">
                <strong>3DKan Advertising</strong> merupakan spesialis pembuatan <strong>{$produk_nama}</strong> yang telah berpengalaman melayani berbagai klien di {$tipe_kota} <strong>{$kota_nama}</strong>, Sulawesi Selatan. Kami memahami kebutuhan signage yang tepat untuk meningkatkan visibilitas usaha Anda.
            </p>
            
            <div class=\"bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg mb-6\">
                <h3 class=\"font-bold text-gray-800 mb-2\">Mengapa Memilih Kami di {$kota_nama}?</h3>
                <ul class=\"space-y-2 text-gray-700\">
                    <li class=\"flex items-start gap-2\">
                        <svg class=\"w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M5 13l4 4L19 7\" />
                        </svg>
                        <span><strong>Produksi Lokal</strong> - Workshop kami di Sulawesi Selatan untuk proses lebih cepat</span>
                    </li>
                    <li class=\"flex items-start gap-2\">
                        <svg class=\"w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M5 13l4 4L19 7\" />
                        </svg>
                        <span><strong>Free Survey</strong> - Tim kami siap datang ke {$kota_nama} untuk survey lokasi gratis</span>
                    </li>
                    <li class=\"flex items-start gap-2\">
                        <svg class=\"w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M5 13l4 4L19 7\" />
                        </svg>
                        <span><strong>Desain Custom Gratis</strong> - 2-3 alternatif desain sesuai konsep branding Anda</span>
                    </li>
                    <li class=\"flex items-start gap-2\">
                        <svg class=\"w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M5 13l4 4L19 7\" />
                        </svg>
                        <span><strong>Garansi hingga 3 Bulan</strong> - Jaminan kualitas material dan pengerjaan</span>
                    </li>
                </ul>
            </div>
        </div>
        ";
        
    } elseif ($produk_nama && !$kota_nama) {
        $title = "Jasa Pembuatan {$produk_nama} | 3DKan Advertising - Spesialis Signage Sulawesi Selatan";
        $desc = "3DKan Advertising - Jasa pembuatan {$produk_nama} profesional untuk seluruh Sulawesi Selatan. Material premium, desain custom, harga kompetitif. Hubungi 0853-4038-2029.";
        
        $content = "
        <h2 class=\"text-2xl sm:text-3xl font-extrabold mb-3\">Jasa Pembuatan {$produk_nama} Profesional</h2>
        
        <div class=\"prose prose-lg max-w-none mb-6\">
            <p class=\"text-gray-600 mb-4\">
                Kami adalah spesialis dalam pembuatan <strong>{$produk_nama}</strong> untuk berbagai kebutuhan bisnis, usaha, dan institusi di seluruh Sulawesi Selatan. Dengan teknologi produksi modern dan material berkualitas, hasil karya kami telah teruji di berbagai kondisi.
            </p>
        </div>
        ";
        
    } elseif (!$produk_nama && $kota_nama) {
        $title = "Jasa Advertising di {$kota_nama} | 3DKan Advertising - Spesialis Signage Sulawesi Selatan";
        $desc = "3DKan Advertising - Jasa pembuatan huruf timbul, neon box, reklame, nametag di {$kota_nama}. Material premium, desain custom, garansi hingga 3 Bulan. Hubungi 0853-4038-2029.";
        
        $content = "
        <h2 class=\"text-2xl sm:text-3xl font-extrabold mb-3\">Jasa Advertising di {$kota_nama}</h2>
        
        <div class=\"prose prose-lg max-w-none mb-6\">
            <p class=\"text-gray-600 mb-4\">
                Sebagai produsen advertising terpercaya di Sulawesi Selatan, kami melayani berbagai kebutuhan percetakan dan signage untuk {$tipe_kota} <strong>{$kota_nama}</strong>. Dari usaha kecil hingga perusahaan besar, tim kami siap membantu brand Anda lebih dikenal.
            </p>
        </div>
        ";
    } else {
        $title = "3DKan Advertising - Jasa Pembuatan Huruf Timbul, Neon Box, Reklame & Nametag";
        $desc = "3DKan Advertising - Jasa pembuatan huruf timbul, neon box, reklame, nametag profesional di Sulawesi Selatan. Material premium, desain custom, garansi hingga 3 Bulan. Hubungi 0853-4038-2029.";
        $content = "";
    }
    
    $keywords = "3dkan advertising, jasa advertising sulawesi selatan";
    if ($produk_nama) $keywords .= ", " . strtolower($produk_nama);
    if ($kota_nama) $keywords .= ", " . strtolower(str_replace(' ', '-', $kota_nama));
    $keywords .= ", signage, huruf timbul, neon box, reklame, nametag";
    
    return [
        'title' => $title,
        'description' => $desc,
        'keywords' => $keywords,
        'content' => $content
    ];
}
?>