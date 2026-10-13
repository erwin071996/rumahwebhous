<?php
declare(strict_types=1);
ini_set('display_errors', '0');
ini_set('log_errors', '0');
set_error_handler(static function (int $severity): bool {
    if ((error_reporting() & $severity) === 0) return true;
    throw new RuntimeException('Unavailable');
});
try {
    require dirname(__DIR__) . '/includes/cms-owner/owner-entry.php';
    if (($_SERVER['HTTPS'] ?? '') !== 'on' && ($_SERVER['HTTPS'] ?? '') !== '1') throw new KanCms\Denied();
    KanCms\ownerBinding();
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
    readfile(__DIR__ . '/owner-ui.html');
} catch (Throwable $error) {
    http_response_code($error instanceof KanCms\Denied ? 401 : 503);
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');
    echo $error instanceof KanCms\Denied ? 'Akses Owner diperlukan.' : 'CMS belum tersedia.';
}
