<?php
// Generated public presentation adapter. No authentication, storage writer or network.
function kan_shared_brand() {
    static $brand = null;
    if ($brand === null) {
        $raw = file_get_contents(__DIR__ . '/site-brand.json');
        $brand = json_decode($raw === false ? '' : $raw, true);
        if (!is_array($brand) || ($brand['schema_version'] ?? null) !== 1) {
            http_response_code(503); exit('Halaman sementara tidak tersedia.');
        }
    }
    return $brand;
}
function kan_shared_fragment($name) {
    $files = ['header' => 'refresh-header.html', 'footer' => 'refresh-footer.html', 'head' => 'refresh-brand-head.html'];
    if (!isset($files[$name])) throw new InvalidArgumentException('Unknown presentation fragment');
    $value = file_get_contents(__DIR__ . '/' . $files[$name]);
    if ($value === false) { http_response_code(503); exit('Halaman sementara tidak tersedia.'); }
    return $value;
}
function kan_shared_active_href($path) {
    $brand = kan_shared_brand();
    if ($path === '/') return '/';
    foreach ($brand['navigation']['items'] as $item) {
        if (parse_url($item['href'], PHP_URL_PATH) === $path) return $item['href'];
    }
    foreach ($brand['navigation']['active_path_rules'] as $target => $rules) {
        foreach ($rules as $rule) {
            if (str_ends_with($rule, '/') ? str_starts_with($path, $rule) : $path === $rule) return $target;
        }
    }
    return null;
}
function kan_shared_header($path) {
    $active = kan_shared_active_href($path);
    echo preg_replace_callback('/<a\b[^>]*href="([^"]*)"[^>]*>/', function ($match) use ($active) {
        $url = html_entity_decode($match[1], ENT_QUOTES | ENT_HTML5, 'UTF-8');
        if ($active !== null && $url === $active && strpos($match[0], 'aria-current=') === false) {
            return substr($match[0], 0, -1) . ' aria-current="page">';
        }
        return $match[0];
    }, kan_shared_fragment('header'));
}
function kan_shared_footer() { echo kan_shared_fragment('footer'); }
function kan_shared_head() { echo kan_shared_fragment('head'); }
function kan_shared_whatsapp($message) {
    $brand = kan_shared_brand();
    return 'https://wa.me/' . ltrim($brand['contact']['phone_e164'], '+') . '?text=' . rawurlencode($message);
}
