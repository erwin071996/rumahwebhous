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
    $binding = KanCms\ownerBinding();
    (new KanCms\OwnerGateway($binding['config'], $binding['owner']))->serve();
} catch (Throwable $error) {
    http_response_code($error instanceof KanCms\Denied ? 401 : 503);
    foreach (['Content-Type' => 'application/json; charset=utf-8', 'Cache-Control' => 'no-store, private',
        'X-Content-Type-Options' => 'nosniff', 'Referrer-Policy' => 'no-referrer',
        'Content-Security-Policy' => "default-src 'none'; frame-ancestors 'none'"] as $name => $value) header($name . ': ' . $value);
    echo json_encode(['ok' => false, 'category' => $error instanceof KanCms\Denied ? 'Access' : 'Unavailable'], JSON_THROW_ON_ERROR);
}
