<?php
require_once __DIR__ . '/includes/tracking-query.php';
// Public content router. Only pre-approved manifest files can be served.
$index = json_decode(file_get_contents(__DIR__ . '/includes/content-index.json'), true);
if (!is_array($index)) { http_response_code(503); exit('Halaman sementara tidak tersedia.'); }
function kan_not_found() {
    http_response_code(404);
    header('X-Robots-Tag: noindex, follow');
    readfile(__DIR__ . '/404.html');
    exit;
}
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if (!is_string($path)) { kan_not_found(); }
$normalized = strtolower(rtrim($path, '/'));
if (isset($index['aliases'][$normalized])) {
    header('Location: ' . $index['domain'] . $index['aliases'][$normalized] . kan_tracking_query(), true, 301);
    exit;
}
if (!isset($index['routes'][$normalized])) { kan_not_found(); }
if ($path !== $normalized) {
    header('Location: ' . $index['domain'] . $normalized . kan_tracking_query(), true, 301);
    exit;
}
$route = $index['routes'][$normalized];
$file = realpath(__DIR__ . '/' . $route['file']);
$base = realpath(__DIR__ . '/includes/content-v2');
if (!$base || !$file || strpos($file, $base . DIRECTORY_SEPARATOR) !== 0 || !is_file($file)) {
    http_response_code(503); exit('Halaman sementara tidak tersedia.');
}
header('Content-Type: text/html; charset=UTF-8');
header('Content-Language: id');
header('X-Content-Type-Options: nosniff');
readfile($file);
