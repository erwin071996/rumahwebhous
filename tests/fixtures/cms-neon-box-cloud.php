<?php
declare(strict_types=1);
/** Synthetic JSON-line CLI fixture only. Never install as an HTTP endpoint. */
require dirname(__DIR__, 2) . '/cms/neon_box_draft_adapter.php';

use KanCms\{Pilot, DraftAdapter, DraftReview, OwnerContext, Denied, Invalid, Conflict, Storage};

const FIXTURE_NOW = 1700000000;
const FIXTURE_OWNER = 'synthetic-owner';
const FIXTURE_RELEASE = '1111111111111111111111111111111111111111';

function fixtureKeys(array $value, array $expected): void {
    $keys = array_keys($value);
    sort($keys, SORT_STRING);
    sort($expected, SORT_STRING);
    if ($keys !== $expected) throw new Invalid();
}
function fixtureBaseline(): array {
    $services = [];
    foreach (['huruf-timbul', 'neon-flex', 'papan-nama', 'stiker-cutting', 'neon-box', 'reklame', 'nametag'] as $id) {
        $services[$id] = [
            'name' => 'Synthetic ' . $id, 'symbol' => 'N',
            'intro' => 'Synthetic introduction.', 'body' => 'Synthetic service description.',
            'options' => ['Synthetic choice A', 'Synthetic choice B'],
            'guide' => 'Confirm synthetic requirements.', 'image' => null,
            'seo_title' => 'Synthetic retained SEO title'
        ];
    }
    return [
        'domain' => 'https://www.3dkanadvertising.store',
        'asset' => '/assets/synthetic', 'logo' => '/assets/synthetic/logo.svg', 'phone' => '0000000000',
        'services' => $services, 'cities' => ['synthetic-city' => ['name' => 'Synthetic City']],
        'legacy_services' => ['synthetic-legacy'],
        'photos' => array_map(fn($id) => ['id' => 'fixture-photo-' . $id, 'src' => '/assets/synthetic/' . $id . '.webp'], ['a', 'b', 'c']),
        'organization' => ['name' => 'Synthetic organization', 'url' => 'https://www.3dkanadvertising.store']
    ];
}
function fixtureSetup(): array {
    if (PHP_SAPI !== 'cli' || PHP_VERSION_ID < 80300 || PHP_VERSION_ID >= 80400) throw new RuntimeException();
    $runner = getenv('RUNNER_TEMP');
    $root = getenv('CMS_TEST_ROOT');
    $repo = realpath(dirname(__DIR__, 2));
    $runnerReal = is_string($runner) ? realpath($runner) : false;
    $rootReal = is_string($root) ? realpath($root) : false;
    if ($repo === false || $runnerReal === false || $runner !== $runnerReal || $rootReal === false
        || $root !== $rootReal || is_link($root) || !is_dir($root)
        || !str_starts_with($root, $runnerReal . '/') || $root === $runnerReal
        || $root === $repo || str_starts_with($root, $repo . '/') || (fileperms($root) & 0777) !== 0700) {
        throw new RuntimeException();
    }
    return [$root, $repo];
}
function fixtureEmit(array $reply): void {
    fwrite(STDOUT, json_encode($reply, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");
}
try {
    [$root, $repo] = fixtureSetup();
    $mode = $argv[1] ?? 'owner';
    if (count($argv) > 2 || !in_array($mode, ['owner', 'anonymous', 'other', 'expired', 'csrf-missing', 'next-release'], true)) throw new RuntimeException();
    // Trusted test driver constructs mocks here; request JSON never supplies identity or CSRF.
    $ctx = new OwnerContext(
        $mode === 'anonymous' ? null : ($mode === 'other' ? 'synthetic-other' : FIXTURE_OWNER),
        $mode === 'expired' ? FIXTURE_NOW : FIXTURE_NOW + 3600,
        $mode !== 'csrf-missing'
    );
    $release = $mode === 'next-release' ? str_repeat('2', 40) : FIXTURE_RELEASE;
    $baseline = fixtureBaseline();
    $pilot = new Pilot($root, [$repo . '/public_html'], $baseline, FIXTURE_OWNER);
    $adapter = new DraftAdapter($pilot, $baseline['services']['neon-box'],
        ['a' => 'fixture-photo-a', 'b' => 'fixture-photo-b', 'c' => 'fixture-photo-c'], $release);
    $review = null;
} catch (Throwable $error) {
    fixtureEmit(['ok' => false, 'category' => 'FixtureBoundary']);
    exit(2);
}
while (($line = fgets(STDIN, 16386)) !== false) {
    try {
        if (strlen($line) > 16384) throw new Invalid();
        $request = json_decode($line, true, 16, JSON_THROW_ON_ERROR);
        if (!is_array($request)) throw new Invalid();
        fixtureKeys($request, ['action', 'payload']);
        if (!is_string($request['action']) || !is_array($request['payload'])) throw new Invalid();
        $action = $request['action'];
        $payload = $request['payload'];
        $keys = match ($action) {
            'load' => [], 'save' => ['expected_revision', 'snapshot'],
            'preview', 'approve', 'export' => ['expected_revision'],
            default => throw new Invalid()
        };
        fixtureKeys($payload, $keys);
        if ($action !== 'load' && (!is_int($payload['expected_revision']) || $payload['expected_revision'] < 0)) throw new Invalid();
        if ($action === 'save' && !is_array($payload['snapshot'])) throw new Invalid();
        $revision = $payload['expected_revision'] ?? 0;
        if ($action === 'preview') {
            $review = $adapter->review($ctx, FIXTURE_NOW, $revision);
            $reply = ['review' => ['revision' => $review->revision, 'fingerprint' => $review->fingerprint]];
        } elseif ($action === 'export') {
            // Assertion-only fixture operation; no queue, file write or network publisher.
            $reply = ['export' => $pilot->export($ctx, FIXTURE_NOW, $revision, $release)];
        } else {
            $state = match ($action) {
                'load' => $adapter->load($ctx, FIXTURE_NOW),
                'save' => $adapter->save($ctx, FIXTURE_NOW, $revision, $payload['snapshot']),
                'approve' => $adapter->approve($ctx, FIXTURE_NOW, $revision, $review)
            };
            $reply = ['state' => $state];
        }
        fixtureEmit(['ok' => true] + $reply);
    } catch (Throwable $error) {
        $categories = [Denied::class => 'Denied', Invalid::class => 'Invalid', Conflict::class => 'Conflict', Storage::class => 'Storage'];
        fixtureEmit(['ok' => false, 'category' => $categories[get_class($error)] ?? 'Invalid']);
        if (strlen($line) > 16384) exit(2);
    }
}
