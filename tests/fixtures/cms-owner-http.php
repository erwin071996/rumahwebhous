<?php
declare(strict_types=1);

/* SYNTHETIC LOOPBACK-ONLY router, not a production bootstrap or login. */
if (PHP_SAPI !== 'cli-server'
    || !in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1', '::1'], true)) {
    http_response_code(404); exit;
}
set_error_handler(static function (int $severity): bool {
    if ((error_reporting() & $severity) === 0) return true;
    throw new RuntimeException('Unavailable');
});
require_once __DIR__ . '/../../cms/owner-gateway.php';
use KanCms\GatewayConfig;
use KanCms\OwnerGateway;
use KanCms\TrustedOwner;
$path = parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH);
$routes = ['/cms-owner/endpoint.php', '/cms-owner/anonymous.php', '/cms-owner/other.php',
    '/cms-owner/expired.php', '/cms-owner/unavailable.php', '/cms-owner/plain.php'];
if (!in_array($path, $routes, true)) { http_response_code(404); exit; }
if ($path === '/cms-owner/unavailable.php') {
    http_response_code(503);
    foreach (OwnerGateway::headers() as $key => $value) header($key . ': ' . $value);
    echo '{"ok":false,"category":"Unavailable"}'; exit;
}
try {
    $repo = realpath(__DIR__ . '/../..');
    $root = getenv('CMS_OWNER_FIXTURE_ROOT');
    if (!is_string($root) || !str_starts_with($root, realpath(sys_get_temp_dir()) . '/kan-owner-http-')) throw new RuntimeException('Fixture');
    $baseline = json_decode(file_get_contents($repo . '/public_html/includes/refresh-data.json'), true, 32, JSON_THROW_ON_ERROR);
    $config = new GatewayConfig($root, [$repo . '/public_html'], [$repo], $baseline,
        'synthetic-owner', str_repeat('a', 40),
        ['a' => 'produk-39db8e80530c', 'b' => 'produk-fcf95321686c'], true);
    $identity = match ($path) {
        '/cms-owner/anonymous.php' => null,
        '/cms-owner/other.php' => 'synthetic-other',
        default => 'synthetic-owner'
    };
    $expiry = $path === '/cms-owner/expired.php' ? time() : time() + 3600;
    /* Trusted server fact is simulated only in this isolated loopback fixture. */
    $_SERVER['HTTPS'] = $path === '/cms-owner/plain.php' ? 'off' : 'on';
    (new OwnerGateway($config, new TrustedOwner($identity, $expiry)))->serve();
} catch (Throwable $error) {
    http_response_code(503);
    foreach (OwnerGateway::headers() as $key => $value) header($key . ': ' . $value);
    echo '{"ok":false,"category":"Unavailable"}'; exit;
}
