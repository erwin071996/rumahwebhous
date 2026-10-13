<?php
declare(strict_types=1);

namespace KanCms;

/**
 * Offline NEON-BOX pilot only (PHP >= 8.1).
 * No endpoint, session, password, hosting provisioning, network or publisher.
 * OwnerContext must be produced by a future trusted server-side adapter.
 * Constructing it from request headers/forms is not authentication.
 */
final class OwnerContext
{
    public function __construct(
        public readonly ?string $serverIdentity,
        public readonly int $expiresAt,
        public readonly bool $csrfVerified
    ) {}
}

final class Denied extends \RuntimeException
{
    public function __construct() { parent::__construct('Denied'); }
}
final class Invalid extends \RuntimeException
{
    public function __construct() { parent::__construct('Invalid'); }
}
final class Conflict extends \RuntimeException
{
    public function __construct() { parent::__construct('Conflict'); }
}
final class Storage extends \RuntimeException
{
    public function __construct() { parent::__construct('Storage'); }
}

final class Pilot
{
    private const STATE = 'neon-box-state.json';
    private const LOCK = '.neon-box.lock';
    private const SERVICES = [
        'huruf-timbul', 'neon-flex', 'papan-nama', 'stiker-cutting',
        'neon-box', 'reklame', 'nametag'
    ];
    private const TOP_KEYS = [
        'domain', 'asset', 'logo', 'phone', 'services', 'cities',
        'legacy_services', 'photos', 'organization'
    ];
    private string $root;
    private array $rootIdentity;
    private array $baseline;
    private string $baselineHash;
    private string $owner;
    private array $photoIds;

    public function __construct(
        string $privateRoot,
        array $publicRoots,
        array $baseline,
        string $configuredOwner
    ) {
        $this->owner = self::text($configuredOwner, 1, 128, false);
        if (!array_is_list($publicRoots) || $publicRoots === []) {
            throw new Invalid();
        }
        $this->root = self::canonicalDirectory($privateRoot);
        foreach ($publicRoots as $publicRoot) {
            if (!is_string($publicRoot)) {
                throw new Invalid();
            }
            $public = self::canonicalDirectory($publicRoot);
            if ($this->root === $public || str_starts_with($this->root, $public . '/')) {
                throw new Invalid();
            }
        }
        $identity = @lstat($this->root);
        if ($identity === false || !is_readable($this->root) || !is_writable($this->root)
            || ($identity['mode'] & 0077) !== 0) {
            throw new Storage();
        }
        $this->rootIdentity = ['dev' => $identity['dev'], 'ino' => $identity['ino']];
        self::keys($baseline, self::TOP_KEYS);
        if (($baseline['domain'] ?? null) !== 'https://www.3dkanadvertising.store'
            || !is_array($baseline['services']) || array_is_list($baseline['services'])
            || !is_array($baseline['photos']) || !array_is_list($baseline['photos'])) {
            throw new Invalid();
        }
        self::keys($baseline['services'], self::SERVICES);
        $this->photoIds = [];
        foreach ($baseline['photos'] as $photo) {
            if (!is_array($photo) || !isset($photo['id']) || !is_string($photo['id'])) {
                throw new Invalid();
            }
            $id = self::text($photo['id'], 1, 128);
            if (isset($this->photoIds[$id])) {
                throw new Invalid();
            }
            $this->photoIds[$id] = true;
        }
        foreach ($baseline['services'] as $service) {
            if (!is_array($service) || array_is_list($service)) {
                throw new Invalid();
            }
        }
        $this->normalizeService($baseline['services']['neon-box']);
        $this->baseline = $baseline;
        $this->baselineHash = hash('sha256', self::encode($baseline));
    }

    public function load(OwnerContext $ctx, int $now): ?array
    {
        $this->authorize($ctx, $now, false);
        return $this->locked(fn() => $this->readState());
    }

    public function save(
        OwnerContext $ctx,
        int $now,
        int $expectedRevision,
        array $publicService,
        string $prevRelease,
        string $privateNote = ''
    ): array {
        $this->authorize($ctx, $now, true);
        $service = $this->normalizeService($publicService);
        self::release($prevRelease);
        self::text($privateNote, 0, 4000, false);
        if ($expectedRevision < 0 || $expectedRevision >= PHP_INT_MAX) {
            throw new Invalid();
        }
        return $this->locked(function () use ($expectedRevision, $service, $prevRelease, $privateNote): array {
            $current = $this->readState();
            $revision = $current === null ? 0 : $current['revision'];
            if ($expectedRevision !== $revision || $revision >= PHP_INT_MAX - 1) {
                throw new Conflict();
            }
            $state = [
                'schema_version' => 1,
                'service_id' => 'neon-box',
                'revision' => $revision + 1,
                'status' => 'draft',
                'prev_release' => $prevRelease,
                'baseline_sha256' => $this->baselineHash,
                'public_service' => $service,
                'private_note' => $privateNote,
                'approval' => null
            ];
            $this->writeState($state);
            return $state;
        });
    }

    public function approve(
        OwnerContext $ctx,
        int $now,
        int $expectedRevision,
        string $prevRelease
    ): array {
        $this->authorize($ctx, $now, true);
        self::release($prevRelease);
        if ($expectedRevision < 1) {
            throw new Invalid();
        }
        return $this->locked(function () use ($expectedRevision, $prevRelease): array {
            $state = $this->readState();
            if ($state === null || $state['revision'] !== $expectedRevision
                || $state['prev_release'] !== $prevRelease) {
                throw new Conflict();
            }
            $state['status'] = 'approved';
            $state['approval'] = [
                'revision' => $state['revision'],
                'prev_release' => $prevRelease,
                'output_sha256' => hash('sha256', $this->output($state['public_service']))
            ];
            $this->writeState($state);
            return $state;
        });
    }

    public function export(
        OwnerContext $ctx,
        int $now,
        int $expectedRevision,
        string $currentRelease
    ): array {
        $this->authorize($ctx, $now, true);
        self::release($currentRelease);
        if ($expectedRevision < 1) {
            throw new Invalid();
        }
        return $this->locked(function () use ($expectedRevision, $currentRelease): array {
            $state = $this->readState();
            if ($state === null || $state['revision'] !== $expectedRevision
                || $state['status'] !== 'approved'
                || $state['prev_release'] !== $currentRelease) {
                throw new Conflict();
            }
            $bytes = $this->output($state['public_service']);
            $sha = hash('sha256', $bytes);
            if (!hash_equals($state['approval']['output_sha256'], $sha)) {
                throw new Invalid();
            }
            return [
                'path' => 'includes/refresh-data.json',
                'bytes' => $bytes,
                'sha256' => $sha,
                'source_rev' => $state['revision'],
                'prev_release' => $state['prev_release']
            ];
        });
    }

    private function authorize(OwnerContext $ctx, int $now, bool $csrf): void
    {
        if ($now < 0 || $ctx->serverIdentity === null
            || !hash_equals($this->owner, $ctx->serverIdentity)
            || $ctx->expiresAt <= $now || ($csrf && !$ctx->csrfVerified)) {
            throw new Denied();
        }
    }

    private static function keys(array $value, array $expected): void
    {
        $keys = array_keys($value);
        sort($keys, SORT_STRING);
        sort($expected, SORT_STRING);
        if ($keys !== $expected) {
            throw new Invalid();
        }
    }

    private static function text(string $value, int $min, int $max, bool $public = true): string
    {
        if (strlen($value) < $min || strlen($value) > $max
            || preg_match('//u', $value) !== 1
            || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', $value) === 1
            || ($min > 0 && trim($value) === '')
            || ($public && (str_contains($value, '<') || str_contains($value, '>')
                || preg_match('/(?:javascript|vbscript|data)\s*:/i', $value) === 1))) {
            throw new Invalid();
        }
        return $value;
    }

    private static function release(string $release): void
    {
        if (preg_match('/\A[a-f0-9]{40}\z/', $release) !== 1) {
            throw new Invalid();
        }
    }

    private function normalizeService(array $input): array
    {
        $required = ['name', 'symbol', 'intro', 'body', 'options', 'guide', 'image'];
        $optional = ['seo_title', 'seo_description', 'detail_heading', 'detail_sections'];
        foreach ($required as $key) {
            if (!array_key_exists($key, $input)) {
                throw new Invalid();
            }
        }
        foreach (array_keys($input) as $key) {
            if (!is_string($key) || !in_array($key, [...$required, ...$optional], true)) {
                throw new Invalid();
            }
        }
        $output = [];
        foreach (['name' => 120, 'symbol' => 24, 'intro' => 500, 'body' => 6000] as $key => $max) {
            if (!is_string($input[$key])) {
                throw new Invalid();
            }
            $output[$key] = self::text($input[$key], 1, $max);
        }
        if (!is_array($input['options']) || !array_is_list($input['options'])
            || count($input['options']) < 1 || count($input['options']) > 20) {
            throw new Invalid();
        }
        $output['options'] = [];
        foreach ($input['options'] as $option) {
            if (!is_string($option)) {
                throw new Invalid();
            }
            $output['options'][] = self::text($option, 1, 250);
        }
        if (!is_string($input['guide'])) {
            throw new Invalid();
        }
        $output['guide'] = self::text($input['guide'], 1, 3000);
        $image = $input['image'];
        if ($image !== null && (!is_string($image) || !isset($this->photoIds[$image]))) {
            throw new Invalid();
        }
        $output['image'] = $image;
        foreach (['seo_title' => 180, 'seo_description' => 320, 'detail_heading' => 200] as $key => $max) {
            if (array_key_exists($key, $input)) {
                if (!is_string($input[$key])) {
                    throw new Invalid();
                }
                $output[$key] = self::text($input[$key], 1, $max);
            }
        }
        if (array_key_exists('detail_sections', $input)) {
            if (!is_array($input['detail_sections']) || !array_is_list($input['detail_sections'])
                || count($input['detail_sections']) > 12) {
                throw new Invalid();
            }
            $sections = [];
            $ids = [];
            foreach ($input['detail_sections'] as $section) {
                if (!is_array($section)) {
                    throw new Invalid();
                }
                self::keys($section, ['id', 'heading', 'paragraphs', 'links']);
                if (!is_string($section['id'])
                    || preg_match('/\A[a-z0-9][a-z0-9-]{0,63}\z/', $section['id']) !== 1
                    || isset($ids[$section['id']]) || !is_string($section['heading'])
                    || !is_array($section['paragraphs']) || !array_is_list($section['paragraphs'])
                    || count($section['paragraphs']) < 1 || count($section['paragraphs']) > 12
                    || !is_array($section['links']) || !array_is_list($section['links'])
                    || count($section['links']) > 8) {
                    throw new Invalid();
                }
                $ids[$section['id']] = true;
                $paragraphs = [];
                foreach ($section['paragraphs'] as $paragraph) {
                    if (!is_string($paragraph)) {
                        throw new Invalid();
                    }
                    $paragraphs[] = self::text($paragraph, 1, 4000);
                }
                $links = [];
                foreach ($section['links'] as $link) {
                    if (!is_array($link)) {
                        throw new Invalid();
                    }
                    self::keys($link, ['label', 'href']);
                    if (!is_string($link['label']) || !is_string($link['href'])) {
                        throw new Invalid();
                    }
                    $links[] = [
                        'label' => self::text($link['label'], 1, 180),
                        'href' => self::link($link['href'])
                    ];
                }
                $sections[] = [
                    'id' => $section['id'],
                    'heading' => self::text($section['heading'], 1, 200),
                    'paragraphs' => $paragraphs,
                    'links' => $links
                ];
            }
            $output['detail_sections'] = $sections;
        }
        // Aggregate encoding bound prevents many individually valid blocks from exhausting storage.
        if (strlen(self::encode($output)) > 96000) {
            throw new Invalid();
        }
        return $output;
    }

    private static function link(string $href): string
    {
        $paths = ['/projects.html', '/cara-pemesanan.html', '/kontak.html'];
        foreach (self::SERVICES as $service) {
            $paths[] = '/layanan/' . $service;
        }
        $allowed = $paths;
        foreach (['gadget-solution', 'shop-sign-retail', 'studi-kasus', 'project-gallery', 'brief-proyek'] as $fragment) {
            $allowed[] = '/projects.html#' . $fragment;
        }
        if (!in_array($href, $allowed, true)) {
            throw new Invalid();
        }
        return $href;
    }

    private static function encode(array $value): string
    {
        try {
            return json_encode($value, JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT
                | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
        } catch (\JsonException $error) {
            throw new Invalid();
        }
    }

    private function output(array $service): string
    {
        $copy = $this->baseline;
        $copy['services']['neon-box'] = $this->normalizeService($service);
        return self::encode($copy);
    }

    private static function canonicalDirectory(string $path): string
    {
        if ($path === '' || $path[0] !== '/' || str_contains($path, "\0")
            || str_contains($path, '\\') || str_contains($path, '//')
            || preg_match('~/(?:\.|\.\.)(?:/|$)~', $path) === 1) {
            throw new Invalid();
        }
        $path = rtrim($path, '/');
        $real = @realpath($path);
        if ($real === false || $real === '/' || $real !== $path || !is_dir($real)) {
            throw new Invalid();
        }
        for ($part = $path; $part !== '/'; $part = dirname($part)) {
            if (is_link($part)) {
                throw new Invalid();
            }
        }
        return $real;
    }

    private function checkRoot(): void
    {
        clearstatcache(true, $this->root);
        $stat = @lstat($this->root);
        if ($stat === false || is_link($this->root) || !is_dir($this->root)
            || $stat['dev'] !== $this->rootIdentity['dev']
            || $stat['ino'] !== $this->rootIdentity['ino'] || ($stat['mode'] & 0077) !== 0
            || @realpath($this->root) !== $this->root) {
            throw new Storage();
        }
    }

    private function checkedStat(string $path): ?array
    {
        clearstatcache(true, $path);
        $stat = @lstat($path);
        if ($stat === false) {
            return null;
        }
        if (($stat['mode'] & 0170000) !== 0100000 || $stat['nlink'] !== 1 || is_link($path)) {
            throw new Storage();
        }
        return $stat;
    }

    private function checkedHandle($handle, string $path): array
    {
        $pathStat = $this->checkedStat($path);
        $handleStat = @fstat($handle);
        if ($pathStat === null || $handleStat === false
            || $pathStat['dev'] !== $handleStat['dev'] || $pathStat['ino'] !== $handleStat['ino']
            || ($handleStat['mode'] & 0170000) !== 0100000 || $handleStat['nlink'] !== 1) {
            throw new Storage();
        }
        return $handleStat;
    }

    private function locked(callable $action): mixed
    {
        $this->checkRoot();
        $path = $this->root . '/' . self::LOCK;
        $existing = $this->checkedStat($path);
        $handle = $existing === null ? @fopen($path, 'x+b') : @fopen($path, 'r+b');
        // Another authorized process may create the lock between lstat and exclusive create.
        if ($handle === false && $existing === null && $this->checkedStat($path) !== null) {
            $handle = @fopen($path, 'r+b');
        }
        if ($handle === false) {
            throw new Storage();
        }
        try {
            $this->checkedHandle($handle, $path);
            if (!@chmod($path, 0600) || !@flock($handle, LOCK_EX)) {
                throw new Storage();
            }
            $this->checkedHandle($handle, $path);
            $this->checkRoot();
            return $action();
        } finally {
            @flock($handle, LOCK_UN);
            @fclose($handle);
        }
    }

    private function readState(): ?array
    {
        $path = $this->root . '/' . self::STATE;
        $stat = $this->checkedStat($path);
        if ($stat === null) {
            return null;
        }
        if ($stat['size'] < 2 || $stat['size'] > 110000) {
            throw new Invalid();
        }
        $handle = @fopen($path, 'rb');
        if ($handle === false) {
            throw new Storage();
        }
        try {
            $this->checkedHandle($handle, $path);
            $bytes = @stream_get_contents($handle, 110001);
            if ($bytes === false) {
                throw new Storage();
            }
            if (strlen($bytes) > 110000) {
                throw new Invalid();
            }
        } finally {
            @fclose($handle);
        }
        try {
            $state = json_decode($bytes, true, 32, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new Invalid();
        }
        if (!is_array($state) || array_is_list($state)) {
            throw new Invalid();
        }
        return $this->validateState($state);
    }

    private function validateState(array $state): array
    {
        self::keys($state, [
            'schema_version', 'service_id', 'revision', 'status', 'prev_release',
            'baseline_sha256', 'public_service', 'private_note', 'approval'
        ]);
        if ($state['schema_version'] !== 1 || $state['service_id'] !== 'neon-box'
            || !is_int($state['revision']) || $state['revision'] < 1 || $state['revision'] >= PHP_INT_MAX
            || !in_array($state['status'], ['draft', 'approved'], true)
            || !is_string($state['prev_release']) || !is_string($state['baseline_sha256'])
            || preg_match('/\A[a-f0-9]{64}\z/', $state['baseline_sha256']) !== 1
            || !is_array($state['public_service']) || !is_string($state['private_note'])) {
            throw new Invalid();
        }
        self::release($state['prev_release']);
        self::text($state['private_note'], 0, 4000, false);
        $service = $this->normalizeService($state['public_service']);
        if (!hash_equals($this->baselineHash, $state['baseline_sha256'])) {
            throw new Conflict();
        }
        if ($state['status'] === 'draft') {
            if ($state['approval'] !== null) {
                throw new Invalid();
            }
        } else {
            $approval = $state['approval'];
            if (!is_array($approval)) {
                throw new Invalid();
            }
            self::keys($approval, ['revision', 'prev_release', 'output_sha256']);
            if ($approval['revision'] !== $state['revision']
                || $approval['prev_release'] !== $state['prev_release']
                || !is_string($approval['output_sha256'])
                || preg_match('/\A[a-f0-9]{64}\z/', $approval['output_sha256']) !== 1
                || !hash_equals($approval['output_sha256'], hash('sha256', $this->output($service)))) {
                throw new Invalid();
            }
        }
        $state['public_service'] = $service;
        return $state;
    }

    private function writeState(array $state): void
    {
        $this->validateState($state);
        $bytes = self::encode($state);
        if (strlen($bytes) > 110000) {
            throw new Invalid();
        }
        $this->checkRoot();
        $target = $this->root . '/' . self::STATE;
        $this->checkedStat($target);
        try {
            $temporary = $this->root . '/.neon-box.tmp-' . bin2hex(random_bytes(16));
        } catch (\Throwable $error) {
            throw new Storage();
        }
        $handle = @fopen($temporary, 'x+b');
        if ($handle === false) {
            throw new Storage();
        }
        $renamed = false;
        try {
            $this->checkedHandle($handle, $temporary);
            if (!@chmod($temporary, 0600)) {
                throw new Storage();
            }
            $offset = 0;
            while ($offset < strlen($bytes)) {
                $written = @fwrite($handle, substr($bytes, $offset));
                if ($written === false || $written === 0) {
                    throw new Storage();
                }
                $offset += $written;
            }
            if (!@fflush($handle) || (function_exists('fsync') && !@fsync($handle))) {
                throw new Storage();
            }
            $this->checkedHandle($handle, $temporary);
            $this->checkRoot();
            $this->checkedStat($target);
            if (!@fclose($handle)) {
                $handle = null;
                throw new Storage();
            }
            $handle = null;
            if (!@rename($temporary, $target)) {
                throw new Storage();
            }
            $renamed = true;
        } finally {
            if (is_resource($handle)) {
                @fclose($handle);
            }
            if (!$renamed) {
                @unlink($temporary);
            }
        }
    }
}
