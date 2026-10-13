<?php
declare(strict_types=1);

namespace KanCms;

require_once __DIR__ . '/neon_box_draft_adapter.php';

/**
 * The hosting bootstrap supplies this object ONLY after its existing
 * server-side Owner boundary has authenticated the request. Never construct
 * it from request headers, JSON, query parameters or a client identity.
 */
final class TrustedOwner
{
    public function __construct(
        public readonly ?string $identity,
        public readonly int $expiresAt
    ) {}
}

final class GatewayConfig
{
    public readonly string $root;

    public function __construct(
        string $privateRoot,
        public readonly array $publicRoots,
        public readonly array $repositoryRoots,
        public readonly array $baseline,
        public readonly string $configuredOwner,
        public readonly string $currentRelease,
        public readonly array $photoMap,
        public readonly bool $publicationEnabled = false
    ) {
        $this->root = self::directory($privateRoot);
        if (!array_is_list($publicRoots) || $publicRoots === []
            || !array_is_list($repositoryRoots)
            || preg_match('/\A[a-f0-9]{40}\z/', $currentRelease) !== 1
            || $configuredOwner === '' || strlen($configuredOwner) > 128) throw new Invalid();
        foreach ([...$publicRoots, ...$repositoryRoots] as $boundary) {
            if (!is_string($boundary)) throw new Invalid();
            $canonical = self::directory($boundary);
            if ($this->root === $canonical || str_starts_with($this->root, $canonical . '/')) throw new Invalid();
        }
        $stat = @lstat($this->root);
        if ($stat === false || ($stat['mode'] & 0077) !== 0
            || !is_readable($this->root) || !is_writable($this->root)) throw new Storage();
    }

    public static function directory(string $path): string
    {
        if ($path === '' || $path[0] !== '/' || str_contains($path, "\0")
            || str_contains($path, '\\') || str_contains($path, '//')
            || preg_match('~/(?:\.|\.\.)(?:/|$)~', $path) === 1) throw new Invalid();
        $path = rtrim($path, '/');
        if ($path === '' || $path === '/' || @realpath($path) !== $path || !is_dir($path)) throw new Invalid();
        for ($part = $path; $part !== '/'; $part = dirname($part)) {
            if (is_link($part)) throw new Invalid();
        }
        return $path;
    }
}

/**
 * Session/HTTP adapter around the existing Pilot and DraftAdapter.
 * No login, password, HTTP authentication implementation, upload or publisher.
 * Missing hosting bootstrap must produce a generic 503 and never instantiate
 * this gateway. Its request file is private handoff, NOT publication.
 */
final class OwnerGateway
{
    private const ORIGIN = 'https://www.3dkanadvertising.store';
    private const SESSION = 'kan_cms_owner';
    private const LOCK = '.owner-gateway.lock';
    private const REQUEST = 'neon-box-publication-request.json';
    private const TTL = 1800;
    private const IDLE = 900;
    private Pilot $pilot;
    private DraftAdapter $adapter;
    private array $rootIdentity;
    private array $media;

    public function __construct(
        private readonly GatewayConfig $config,
        private readonly TrustedOwner $owner
    ) {
        $this->pilot = new Pilot($config->root, $config->publicRoots, $config->baseline, $config->configuredOwner);
        $this->adapter = new DraftAdapter($this->pilot, $config->baseline['services']['neon-box'],
            $config->photoMap, $config->currentRelease);
        $stat = @lstat($config->root);
        if ($stat === false) throw new Storage();
        $this->rootIdentity = ['dev' => $stat['dev'], 'ino' => $stat['ino']];
        $this->media = [];
        foreach ($config->photoMap as $id => $photoId) {
            $matches = array_values(array_filter($config->baseline['photos'], fn($photo) => $photo['id'] === $photoId));
            if (count($matches) !== 1) throw new Invalid();
            $photo = $matches[0];
            if (!is_string($photo['title'] ?? null) || !is_string($photo['src'] ?? null)
                || preg_match('~\A/assets/[a-zA-Z0-9/_-]+\.(?:webp|jpg|jpeg|png)\z~', $photo['src']) !== 1) throw new Invalid();
            $this->media[] = ['id' => $id, 'label' => $photo['title'], 'src' => $photo['src']];
        }
        $cover = $config->baseline['services']['neon-box']['image'];
        if ($cover !== null && !in_array($cover, $config->photoMap, true)) throw new Invalid();
    }

    /** Host entry point; call only after the trusted boundary is checked. */
    public function serve(): never
    {
        try {
            if (session_status() !== PHP_SESSION_NONE || headers_sent()) throw new Denied();
            if (($_SERVER['HTTPS'] ?? '') !== 'on' && ($_SERVER['HTTPS'] ?? '') !== '1') throw new Denied();
            $this->authorize(time());
            foreach (['session.use_strict_mode' => '1', 'session.use_cookies' => '1',
                'session.save_handler' => 'files', 'session.use_only_cookies' => '1',
                'session.use_trans_sid' => '0', 'session.gc_maxlifetime' => (string)self::TTL] as $key => $value) {
                if (ini_set($key, $value) === false) throw new Storage();
            }
            session_name('KAN_CMS_OWNER');
            session_save_path('0;0600;' . $this->config->root);
            session_set_cookie_params(['lifetime' => 0, 'path' => '/cms-owner/', 'secure' => true,
                'httponly' => true, 'samesite' => 'Strict']);
            if (!session_start()) throw new Storage();
            $before = $_SESSION[self::SESSION]['csrf'] ?? null;
            $input = @file_get_contents('php://input', false, null, 0, 16385);
            if ($input === false) throw new Invalid();
            $response = $this->dispatch($_SERVER['REQUEST_METHOD'] ?? '', $_GET,
                $_SERVER['CONTENT_TYPE'] ?? '', $_SERVER['HTTP_ORIGIN'] ?? null,
                $_SERVER['HTTP_X_CSRF_TOKEN'] ?? null, $input, $_SESSION, time());
            if ($response['status'] === 200 && ($_SESSION[self::SESSION]['csrf'] ?? null) !== $before
                && !session_regenerate_id(true)) throw new Storage();
            session_write_close();
        } catch (Denied $error) {
            $response = self::failure(401, 'Access');
        } catch (\Throwable $error) {
            $response = self::failure(503, 'Unavailable');
        }
        http_response_code($response['status']);
        foreach (self::headers() as $key => $value) header($key . ': ' . $value);
        echo json_encode($response['body'], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    /**
     * Pure transport seam for focused cloud tests. Session is supplied by PHP
     * server storage in serve(), never from request data.
     */
    public function dispatch(string $method, array $query, string $contentType, ?string $origin,
        ?string $csrf, string $body, array &$session, int $now): array
    {
        try {
            $this->authorize($now);
            if (strlen($body) > 16384) throw new Invalid();
            if ($method === 'GET') {
                self::keys($query, ['action']);
                if ($query['action'] !== 'load' || $body !== '') throw new Invalid();
                $this->prepareSession($session, $now);
                return $this->locked(function () use (&$session, $now): array {
                    $this->clearReview($session);
                    return self::success(['csrf' => $session[self::SESSION]['csrf'],
                        'state' => $this->adapter->load($this->context($now, false), $now),
                        'config' => $this->publicConfig()]);
                });
            }
            if ($method !== 'POST') return self::failure(405, 'Invalid');
            if ($query !== [] || preg_match('~\Aapplication/json(?:;\s*charset=utf-8)?\z~i', $contentType) !== 1) throw new Invalid();
            $this->requireSession($session, $now);
            if ($origin !== self::ORIGIN || $csrf === null
                || !hash_equals($session[self::SESSION]['csrf'], $csrf)) return self::failure(403, 'Csrf');
            try { $input = json_decode($body, true, 16, JSON_THROW_ON_ERROR); }
            catch (\JsonException $error) { throw new Invalid(); }
            if (!is_array($input)) throw new Invalid();
            self::keys($input, ['action', 'payload']);
            if (!is_string($input['action']) || !is_array($input['payload'])) throw new Invalid();
            return $this->locked(function () use ($input, &$session, $now): array {
                return $this->mutate($input['action'], $input['payload'], $session, $now);
            });
        } catch (Denied $error) {
            unset($session[self::SESSION]);
            return self::failure(401, 'Access');
        } catch (Conflict $error) {
            $this->clearReview($session);
            return self::failure(409, 'Conflict');
        } catch (Invalid|\TypeError $error) {
            return self::failure(422, 'Invalid');
        } catch (\Throwable $error) {
            return self::failure(503, 'Unavailable');
        }
    }

    private function mutate(string $action, array $payload, array &$session, int $now): array
    {
        $ctx = $this->context($now, true);
        if ($action === 'save') {
            self::keys($payload, ['expected_revision', 'snapshot']);
            if (!is_array($payload['snapshot'])) throw new Invalid();
            $revision = self::revision($payload['expected_revision'], true);
            $state = $this->adapter->save($ctx, $now, $revision, $payload['snapshot']);
            $this->clearReview($session);
            $this->invalidateRequest();
            return self::success(['state' => $state]);
        }
        self::keys($payload, ['expected_revision']);
        $revision = self::revision($payload['expected_revision'], false);
        if ($action === 'preview') {
            $review = $this->adapter->review($ctx, $now, $revision);
            $session[self::SESSION]['review'] = $this->receipt($review, $session, $now);
            $session[self::SESSION]['approved'] = null;
            return self::success(['state' => $this->adapter->load($ctx, $now),
                'review' => ['revision' => $review->revision]]);
        }
        if ($action === 'approve') {
            $review = $this->adapter->review($ctx, $now, $revision);
            $this->requireReceipt($session[self::SESSION]['review'] ?? null, $review, $session, $now);
            $state = $this->adapter->approve($ctx, $now, $revision, $review);
            $session[self::SESSION]['approved'] = $this->receipt($review, $session, $now);
            $session[self::SESSION]['review'] = null;
            return self::success(['state' => $state]);
        }
        if ($action === 'request-publication') {
            if (!$this->config->publicationEnabled) return self::failure(503, 'Unavailable');
            $review = $this->adapter->review($ctx, $now, $revision);
            $this->requireReceipt($session[self::SESSION]['approved'] ?? null, $review, $session, $now);
            $export = $this->pilot->export($ctx, $now, $revision, $this->config->currentRelease);
            $request = $this->requestPublication($export);
            return self::success(['request' => ['id' => $request['request_id'], 'status' => 'requested']]);
        }
        throw new Invalid();
    }

    private function authorize(int $now): void
    {
        if ($now < 0 || $this->owner->identity === null
            || !hash_equals($this->config->configuredOwner, $this->owner->identity)
            || $this->owner->expiresAt <= $now) throw new Denied();
    }

    private function context(int $now, bool $csrf): OwnerContext
    {
        return new OwnerContext($this->owner->identity, $this->owner->expiresAt, $csrf);
    }

    private function prepareSession(array &$session, int $now): void
    {
        $identity = hash('sha256', $this->owner->identity);
        $existing = $session[self::SESSION] ?? null;
        if (!is_array($existing) || ($existing['identity'] ?? null) !== $identity
            || !is_int($existing['expires_at'] ?? null) || $existing['expires_at'] <= $now
            || !is_int($existing['last_seen'] ?? null) || $existing['last_seen'] > $now || $now - $existing['last_seen'] > self::IDLE
            || ($existing['release'] ?? null) !== $this->config->currentRelease
            || !is_string($existing['csrf'] ?? null) || preg_match('/\A[a-f0-9]{64}\z/', $existing['csrf']) !== 1) {
            $session[self::SESSION] = ['identity' => $identity, 'expires_at' => min($this->owner->expiresAt, $now + self::TTL),
                'release' => $this->config->currentRelease, 'csrf' => bin2hex(random_bytes(32)), 'last_seen' => $now,
                'review' => null, 'approved' => null];
        }
        $session[self::SESSION]['last_seen'] = $now;
    }

    private function requireSession(array &$session, int $now): void
    {
        $entry = $session[self::SESSION] ?? null;
        if (!is_array($entry) || ($entry['identity'] ?? null) !== hash('sha256', $this->owner->identity)
            || !is_int($entry['expires_at'] ?? null) || $entry['expires_at'] <= $now
            || !is_int($entry['last_seen'] ?? null) || $entry['last_seen'] > $now || $now - $entry['last_seen'] > self::IDLE
            || ($entry['release'] ?? null) !== $this->config->currentRelease
            || !is_string($entry['csrf'] ?? null) || preg_match('/\A[a-f0-9]{64}\z/', $entry['csrf']) !== 1) throw new Denied();
        $session[self::SESSION]['last_seen'] = $now;
    }

    private function clearReview(array &$session): void
    {
        if (isset($session[self::SESSION]) && is_array($session[self::SESSION])) {
            $session[self::SESSION]['review'] = null;
            $session[self::SESSION]['approved'] = null;
        }
    }

    private function receipt(DraftReview $review, array $session, int $now): array
    {
        return ['revision' => $review->revision, 'fingerprint' => $review->fingerprint,
            'identity' => $session[self::SESSION]['identity'], 'session' => hash('sha256', $session[self::SESSION]['csrf']),
            'release' => $this->config->currentRelease,
            'expires_at' => min($session[self::SESSION]['expires_at'], $now + 600)];
    }

    private function requireReceipt(mixed $receipt, DraftReview $review, array $session, int $now): void
    {
        if (!is_array($receipt) || ($receipt['revision'] ?? null) !== $review->revision
            || !is_string($receipt['fingerprint'] ?? null) || !hash_equals($receipt['fingerprint'], $review->fingerprint)
            || ($receipt['identity'] ?? null) !== $session[self::SESSION]['identity']
            || ($receipt['session'] ?? null) !== hash('sha256', $session[self::SESSION]['csrf'])
            || ($receipt['release'] ?? null) !== $this->config->currentRelease
            || !is_int($receipt['expires_at'] ?? null) || $receipt['expires_at'] <= $now) throw new Conflict();
    }

    private function publicConfig(): array
    {
        $service = $this->config->baseline['services']['neon-box'];
        $cover = $service['image'] === null ? null : array_search($service['image'], $this->config->photoMap, true);
        return ['service' => ['title' => $service['name'], 'summary' => $service['intro'], 'cover' => $cover],
            'media' => $this->media, 'publicationEnabled' => $this->config->publicationEnabled];
    }

    private static function revision(mixed $revision, bool $zero): int
    {
        if (!is_int($revision) || $revision < ($zero ? 0 : 1) || $revision >= PHP_INT_MAX) throw new Invalid();
        return $revision;
    }

    private static function keys(array $value, array $expected): void
    {
        $actual = array_keys($value);
        sort($actual, SORT_STRING);
        sort($expected, SORT_STRING);
        if ($actual !== $expected) throw new Invalid();
    }

    private static function success(array $value): array
    {
        return ['status' => 200, 'body' => ['ok' => true, ...$value]];
    }

    private static function failure(int $status, string $category): array
    {
        return ['status' => $status, 'body' => ['ok' => false, 'category' => $category]];
    }

    public static function headers(): array
    {
        return ['Content-Type' => 'application/json; charset=utf-8', 'Cache-Control' => 'no-store, private',
            'Pragma' => 'no-cache', 'X-Content-Type-Options' => 'nosniff',
            'Content-Security-Policy' => "default-src 'none'; frame-ancestors 'none'",
            'Referrer-Policy' => 'no-referrer'];
    }

    private function rootCheck(): void
    {
        clearstatcache(true, $this->config->root);
        $stat = @lstat($this->config->root);
        if ($stat === false || is_link($this->config->root) || !is_dir($this->config->root)
            || @realpath($this->config->root) !== $this->config->root || ($stat['mode'] & 0077) !== 0
            || $stat['dev'] !== $this->rootIdentity['dev'] || $stat['ino'] !== $this->rootIdentity['ino']) throw new Storage();
    }

    private function fileStat(string $path): ?array
    {
        clearstatcache(true, $path);
        $stat = @lstat($path);
        if ($stat === false) return null;
        if (($stat['mode'] & 0170000) !== 0100000 || $stat['nlink'] !== 1 || is_link($path)
            || ($stat['mode'] & 0077) !== 0) throw new Storage();
        return $stat;
    }

    private function handleCheck($handle, string $path): void
    {
        $pathStat = $this->fileStat($path);
        $stat = @fstat($handle);
        if ($pathStat === null || $stat === false || ($stat['mode'] & 0170000) !== 0100000
            || $stat['nlink'] !== 1 || $stat['dev'] !== $pathStat['dev'] || $stat['ino'] !== $pathStat['ino']) throw new Storage();
    }

    private function locked(callable $action): mixed
    {
        $this->rootCheck();
        $path = $this->config->root . '/' . self::LOCK;
        $existing = $this->fileStat($path);
        $oldMask = umask(0077);
        try { $handle = $existing === null ? @fopen($path, 'x+b') : @fopen($path, 'r+b'); }
        finally { umask($oldMask); }
        if ($handle === false && $existing === null && $this->fileStat($path) !== null) $handle = @fopen($path, 'r+b');
        if ($handle === false) throw new Storage();
        try {
            $this->handleCheck($handle, $path);
            if (!@chmod($path, 0600) || !@flock($handle, LOCK_EX)) throw new Storage();
            $this->handleCheck($handle, $path);
            $this->rootCheck();
            return $action();
        } finally { @flock($handle, LOCK_UN); @fclose($handle); }
    }

    private function invalidateRequest(): void
    {
        $this->rootCheck();
        $path = $this->config->root . '/' . self::REQUEST;
        if ($this->fileStat($path) !== null && !@unlink($path)) throw new Storage();
    }

    private function requestPublication(array $export): array
    {
        self::keys($export, ['path', 'bytes', 'sha256', 'source_rev', 'prev_release']);
        if ($export['path'] !== 'includes/refresh-data.json' || !is_string($export['bytes'])
            || !is_string($export['sha256']) || !hash_equals($export['sha256'], hash('sha256', $export['bytes']))) throw new Invalid();
        $id = hash('sha256', $export['prev_release'] . "\n" . $export['source_rev'] . "\n" . $export['sha256']);
        $request = ['schema_version' => 1, 'request_id' => $id, 'status' => 'requested',
            'source_rev' => $export['source_rev'], 'prev_release' => $export['prev_release'],
            'output_sha256' => $export['sha256'], 'path' => $export['path'], 'bytes' => $export['bytes']];
        $path = $this->config->root . '/' . self::REQUEST;
        $stat = $this->fileStat($path);
        if ($stat !== null) {
            if ($stat['size'] < 2 || $stat['size'] > 2000000) throw new Storage();
            $handle = @fopen($path, 'rb');
            if ($handle === false) throw new Storage();
            try {
                $this->handleCheck($handle, $path);
                $bytes = @stream_get_contents($handle, 2000001);
                if ($bytes === false || strlen($bytes) > 2000000) throw new Storage();
            } finally { @fclose($handle); }
            try { $existing = json_decode($bytes, true, 32, JSON_THROW_ON_ERROR); }
            catch (\JsonException $error) { throw new Storage(); }
            if ($existing !== $request) throw new Conflict();
            return $request;
        }
        $bytes = json_encode($request, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
        if (strlen($bytes) > 2000000) throw new Invalid();
        $temporary = $this->config->root . '/.owner-request-' . bin2hex(random_bytes(16));
        $oldMask = umask(0077);
        try { $handle = @fopen($temporary, 'x+b'); }
        finally { umask($oldMask); }
        if ($handle === false) throw new Storage();
        $done = false;
        try {
            $this->handleCheck($handle, $temporary);
            if (!@chmod($temporary, 0600)) throw new Storage();
            $offset = 0;
            while ($offset < strlen($bytes)) {
                $written = @fwrite($handle, substr($bytes, $offset));
                if ($written === false || $written === 0) throw new Storage();
                $offset += $written;
            }
            if (!@fflush($handle) || (function_exists('fsync') && !@fsync($handle))) throw new Storage();
            $this->rootCheck();
            $this->handleCheck($handle, $temporary);
            if ($this->fileStat($path) !== null) throw new Conflict();
            if (!@fclose($handle)) { $handle = null; throw new Storage(); }
            $handle = null;
            if (!@rename($temporary, $path)) throw new Storage();
            $done = true;
            return $request;
        } finally {
            if (is_resource($handle)) @fclose($handle);
            if (!$done) @unlink($temporary);
        }
    }
}
