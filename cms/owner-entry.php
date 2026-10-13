<?php
declare(strict_types=1);

namespace KanCms;

require_once __DIR__ . '/owner-gateway.php';

/** Trusted host configuration is never part of the source or public package. */
function ownerBinding(): array
{
    $path = getenv('CMS_OWNER_BOOTSTRAP');
    if (!is_string($path) || $path === '' || $path[0] !== '/' || str_contains($path, "\0")
        || str_contains($path, '\\') || str_contains($path, '//')
        || preg_match('~/(?:\\.|\\.\\.)(?:/|$)~', $path) === 1
        || realpath($path) !== $path || !is_file($path) || is_link($path)) throw new Storage();
    for ($part = dirname($path); $part !== '/'; $part = dirname($part)) {
        if (is_link($part)) throw new Storage();
    }
    $root = realpath($_SERVER['DOCUMENT_ROOT'] ?? '');
    if ($root === false || $path === $root || str_starts_with($path, rtrim($root, '/') . '/')) throw new Storage();
    $stat = lstat($path);
    if ($stat === false || ($stat['mode'] & 0170000) !== 0100000
        || ($stat['mode'] & 0077) !== 0 || $stat['nlink'] !== 1) throw new Storage();
    $level = ob_get_level();
    ob_start();
    try {
        $binding = require $path;
        if (ob_get_length() !== 0) throw new Storage();
    } finally {
        while (ob_get_level() > $level) ob_end_clean();
    }
    if (!is_array($binding) || array_keys($binding) !== ['config', 'owner']
        || !$binding['config'] instanceof GatewayConfig || !$binding['owner'] instanceof TrustedOwner) throw new Storage();
    $config = $binding['config'];
    $owner = $binding['owner'];
    if (!in_array($root, $config->publicRoots, true)) throw new Storage();
    foreach ([...$config->publicRoots, ...$config->repositoryRoots] as $boundary) {
        $boundary = GatewayConfig::directory($boundary);
        if ($path === $boundary || str_starts_with($path, $boundary . '/')) throw new Storage();
    }
    if ($owner->identity === null || !hash_equals($config->configuredOwner, $owner->identity)
        || $owner->expiresAt <= time()) throw new Denied();
    return $binding;
}

function ownerUnavailable(int $status): never
{
    http_response_code($status);
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");
    echo $status === 401 ? 'Akses Owner diperlukan.' : 'CMS belum tersedia.';
    exit;
}
