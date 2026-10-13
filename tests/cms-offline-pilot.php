<?php
declare(strict_types=1);
/*
 * Offline, synthetic PHP CLI checks only. No HTTP endpoint, hosting auth or publisher.
 * CMS_TEST_ROOT must be a precreated 0700 directory below RUNNER_TEMP, outside checkout.
 * Private fixtures are removed; only redacted result names/categories may be retained.
 */
require dirname(__DIR__) . '/cms/neon_box_pilot.php';

use KanCms\OwnerContext;
use KanCms\Pilot;
use KanCms\Denied;
use KanCms\Invalid;
use KanCms\Conflict;
use KanCms\Storage;

const CMS_NOW = 1700000000;
const CMS_OWNER = 'synthetic-owner';
const CMS_RELEASE = '1111111111111111111111111111111111111111';
const CMS_NEXT_RELEASE = '2222222222222222222222222222222222222222';
const CMS_PRIVATE_SENTINEL = 'SYNTHETIC_PRIVATE_NOTE_DO_NOT_EXPORT';

function cmsInside(string $path, string $root): bool {
    return $path === $root || str_starts_with($path, $root . DIRECTORY_SEPARATOR);
}
function cmsSetup(): array {
    if (PHP_SAPI !== 'cli' || PHP_VERSION_ID < 80100) {
        throw new RuntimeException('CLI_PHP_8_1_REQUIRED');
    }
    $runner = getenv('RUNNER_TEMP');
    $test = getenv('CMS_TEST_ROOT');
    $runnerReal = is_string($runner) ? realpath($runner) : false;
    $testReal = is_string($test) ? realpath($test) : false;
    $repo = realpath(dirname(__DIR__));
    if ($runnerReal === false || $testReal === false || $repo === false ||
        $test !== $testReal || is_link($testReal) || !is_dir($testReal) ||
        !cmsInside($testReal, $runnerReal) || $testReal === $runnerReal ||
        cmsInside($testReal, $repo) || (fileperms($testReal) & 0777) !== 0700) {
        throw new RuntimeException('PRIVATE_TEST_ROOT_REQUIRED');
    }
    return [$testReal, $repo];
}
function cmsBaseline(): array {
    $services = [];
    foreach (['huruf-timbul', 'neon-flex', 'papan-nama', 'stiker-cutting', 'neon-box', 'reklame', 'nametag'] as $id) {
        $services[$id] = [
            'name' => 'Synthetic ' . $id,
            'symbol' => 'N',
            'intro' => 'Synthetic introduction.',
            'body' => 'Synthetic service description.',
            'options' => ['Synthetic choice A', 'Synthetic choice B'],
            'guide' => 'Confirm synthetic requirements.',
            'image' => $id === 'neon-box' ? 'synthetic-approved-photo' : null,
        ];
    }
    return [
        'domain' => 'https://www.3dkanadvertising.store',
        'asset' => '/assets/synthetic',
        'logo' => '/assets/synthetic/logo.svg',
        'phone' => '0000000000',
        'services' => $services,
        'cities' => ['synthetic-city' => ['name' => 'Synthetic City']],
        'legacy_services' => ['synthetic-legacy'],
        'photos' => [[
            'id' => 'synthetic-approved-photo', 'category' => 'Synthetic', 'slug' => 'synthetic',
            'subcategory' => 'Synthetic', 'title' => 'Synthetic approved illustration',
            'kind' => 'Synthetic fixture', 'src' => '/assets/synthetic/photo.webp',
            'large' => '/assets/synthetic/photo-large.webp', 'original' => '/assets/synthetic/photo-original.webp',
            'aliases' => [], 'width' => 480, 'height' => 854,
        ]],
        'organization' => ['name' => 'Synthetic organization', 'url' => 'https://www.3dkanadvertising.store'],
    ];
}
function cmsService(): array {
    $service = cmsBaseline()['services']['neon-box'];
    $service['name'] = 'Synthetic pilot neon box';
    $service['intro'] = 'Synthetic approved introduction.';
    $service['seo_title'] = 'Synthetic neon box guide';
    $service['seo_description'] = 'Synthetic guidance, without price, warranty or project claims.';
    $service['detail_heading'] = 'Synthetic planning notes';
    $service['detail_sections'] = [[
        'id' => 'synthetic-guide', 'heading' => 'Synthetic guide',
        'paragraphs' => ['Synthetic plain text with literal punctuation.'],
        'links' => [['label' => 'Approved existing project reference', 'href' => '/projects.html#gadget-solution']],
    ]];
    return $service;
}
function cmsCtx(?string $identity = CMS_OWNER, int $expires = CMS_NOW + 3600, bool $csrf = true): OwnerContext {
    return new OwnerContext($identity, $expires, $csrf);
}
function cmsRequire(bool $condition): void {
    if (!$condition) {
        throw new RuntimeException('ASSERTION');
    }
}
function cmsExpect(string $class, callable $action): void {
    try {
        $action();
    } catch (Throwable $error) {
        cmsRequire(get_class($error) === $class);
        $category = substr($class, strrpos($class, '\\') + 1);
        cmsRequire($error->getMessage() === $category);
        cmsRequire(!str_contains($error->getMessage(), CMS_PRIVATE_SENTINEL));
        return;
    }
    throw new RuntimeException('EXPECTED_REJECTION');
}
function cmsFiles(string $root): array {
    $entries = array_values(array_diff(scandir($root) ?: [], ['.', '..']));
    sort($entries);
    return $entries;
}
function cmsPath(string $testRoot, string $name): string {
    if (!preg_match('/^case-[a-z0-9-]+$/D', $name)) {
        throw new RuntimeException('TEST_NAME');
    }
    return $testRoot . DIRECTORY_SEPARATOR . $name;
}
function cmsMkdir(string $root): void {
    if (file_exists($root) || is_link($root) || !mkdir($root, 0700)) {
        throw new RuntimeException('TEST_DIRECTORY');
    }
    chmod($root, 0700);
}
function cmsClean(string $path, string $testRoot): void {
    if (!str_starts_with($path, $testRoot . DIRECTORY_SEPARATOR)) {
        throw new RuntimeException('CLEANUP_BOUNDARY');
    }
    if (is_link($path) || is_file($path)) {
        if (!unlink($path)) throw new RuntimeException('CLEANUP');
        return;
    }
    if (!is_dir($path)) return;
    foreach (array_diff(scandir($path) ?: [], ['.', '..']) as $entry) {
        cmsClean($path . DIRECTORY_SEPARATOR . $entry, $testRoot);
    }
    if (!rmdir($path)) throw new RuntimeException('CLEANUP');
}
function cmsPilot(string $root, string $repo, ?array $baseline = null): Pilot {
    return new Pilot($root, [$repo . '/public_html'], $baseline ?? cmsBaseline(), CMS_OWNER);
}
function cmsApproved(Pilot $pilot): array {
    $saved = $pilot->save(cmsCtx(), CMS_NOW, 0, cmsService(), CMS_RELEASE, CMS_PRIVATE_SENTINEL);
    cmsRequire($saved['revision'] === 1 && $saved['status'] === 'draft' && $saved['approval'] === null);
    return $pilot->approve(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
}
function cmsWriteState(string $root, array $state): void {
    $path = $root . '/neon-box-state.json';
    cmsRequire(!is_link($path));
    cmsRequire(file_put_contents($path, json_encode($state, JSON_THROW_ON_ERROR) . "\n") !== false);
    chmod($path, 0600);
}
function cmsWorker(string $testRoot, string $repo): never {
    $race = $GLOBALS['argv'][2] ?? '';
    $who = $GLOBALS['argv'][3] ?? '';
    $raceReal = realpath($race);
    if (!is_string($raceReal) || $race !== $raceReal ||
        !str_starts_with($raceReal, $testRoot . DIRECTORY_SEPARATOR) ||
        !in_array($who, ['a', 'b'], true) || is_link($raceReal)) {
        fwrite(STDOUT, "{\"status\":\"FAIL\",\"category\":\"WorkerBoundary\"}\n");
        exit(2);
    }
    try {
        $pilot = cmsPilot($raceReal . '/private', $repo);
        file_put_contents($raceReal . '/ready-' . $who, 'ready');
        $deadline = microtime(true) + 10;
        while (is_file($raceReal . '/barrier') && microtime(true) < $deadline) usleep(10000);
        cmsRequire(!is_file($raceReal . '/barrier'));
        $service = cmsService();
        $service['body'] = 'Synthetic concurrent body ' . $who . '.';
        try {
            $saved = $pilot->save(cmsCtx(), CMS_NOW, 0, $service, CMS_RELEASE, CMS_PRIVATE_SENTINEL);
            fwrite(STDOUT, json_encode(['status' => 'saved', 'revision' => $saved['revision']], JSON_THROW_ON_ERROR) . "\n");
        } catch (Conflict $error) {
            cmsRequire($error->getMessage() === 'Conflict');
            fwrite(STDOUT, "{\"status\":\"conflict\",\"category\":\"Conflict\"}\n");
        }
        exit(0);
    } catch (Throwable $error) {
        fwrite(STDOUT, "{\"status\":\"FAIL\",\"category\":\"WorkerFailure\"}\n");
        exit(2);
    }
}
$results = [];
$created = [];
function cmsCheck(string $name, callable $action): void {
    global $results;
    try {
        $action();
        $results[] = ['name' => $name, 'status' => 'PASS'];
    } catch (Throwable $error) {
        $known = [Denied::class, Invalid::class, Conflict::class, Storage::class];
        $results[] = ['name' => $name, 'status' => 'FAIL', 'category' => in_array(get_class($error), $known, true)
            ? substr(get_class($error), strrpos(get_class($error), '\\') + 1) : 'AssertionOrRuntime'];
    }
}
function cmsNotRun(string $name, string $category): void {
    global $results;
    $results[] = ['name' => $name, 'status' => 'NOT RUN', 'category' => $category];
}
function cmsCase(string $name, callable $action): void {
    global $created, $testRoot, $repo;
    cmsCheck($name, function () use ($name, $action, &$created, $testRoot, $repo): void {
        $root = cmsPath($testRoot, 'case-' . $name);
        cmsMkdir($root);
        $created[] = $root;
        $action(cmsPilot($root, $repo), $root);
    });
}
try {
    [$testRoot, $repo] = cmsSetup();
    if (($argv[1] ?? '') === '--worker') cmsWorker($testRoot, $repo);

    foreach ([
        'missing-owner' => cmsCtx(null),
        'wrong-owner' => cmsCtx('synthetic-other'),
        'expired-owner' => cmsCtx(CMS_OWNER, CMS_NOW - 1),
        'expiry-boundary' => cmsCtx(CMS_OWNER, CMS_NOW),
    ] as $label => $context) {
        cmsCase('auth-' . $label, function (Pilot $pilot, string $root) use ($context): void {
            foreach ([
                fn() => $pilot->load($context, CMS_NOW),
                fn() => $pilot->save($context, CMS_NOW, 0, cmsService(), CMS_RELEASE, CMS_PRIVATE_SENTINEL),
                fn() => $pilot->approve($context, CMS_NOW, 0, CMS_RELEASE),
                fn() => $pilot->export($context, CMS_NOW, 0, CMS_RELEASE),
            ] as $action) cmsExpect(Denied::class, $action);
            cmsRequire(cmsFiles($root) === []);
        });
    }
    cmsCase('csrf-mutation-and-export', function (Pilot $pilot, string $root): void {
        $context = cmsCtx(CMS_OWNER, CMS_NOW + 3600, false);
        cmsExpect(Denied::class, fn() => $pilot->save($context, CMS_NOW, 0, cmsService(), CMS_RELEASE));
        cmsExpect(Denied::class, fn() => $pilot->approve($context, CMS_NOW, 0, CMS_RELEASE));
        cmsExpect(Denied::class, fn() => $pilot->export($context, CMS_NOW, 0, CMS_RELEASE));
        cmsRequire(cmsFiles($root) === []);
        cmsRequire($pilot->load($context, CMS_NOW) === null);
    });
    cmsCase('missing-state-contract', function (Pilot $pilot): void {
        cmsRequire($pilot->load(cmsCtx(), CMS_NOW) === null);
        cmsExpect(Conflict::class, fn() => $pilot->approve(cmsCtx(), CMS_NOW, 1, CMS_RELEASE));
        cmsExpect(Conflict::class, fn() => $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE));
    });

    $invalid = [
        'unknown-field' => static function (array $s): array { $s['private_note'] = CMS_PRIVATE_SENTINEL; return $s; },
        'missing-required-field' => static function (array $s): array { unset($s['body']); return $s; },
        'wrong-string-type' => static function (array $s): array { $s['name'] = ['synthetic']; return $s; },
        'options-not-array' => static function (array $s): array { $s['options'] = 'synthetic'; return $s; },
        'options-item-type' => static function (array $s): array { $s['options'] = [['synthetic']]; return $s; },
        'raw-html' => static function (array $s): array { $s['body'] = '<script>' . CMS_PRIVATE_SENTINEL . '</script>'; return $s; },
        'nul-text' => static function (array $s): array { $s['intro'] = "synthetic\0text"; return $s; },
        'invalid-utf8' => static function (array $s): array { $s['intro'] = "\xff"; return $s; },
        'new-media-id' => static function (array $s): array { $s['image'] = 'unapproved-synthetic-photo'; return $s; },
        'media-url' => static function (array $s): array { $s['image'] = 'https://example.invalid/photo.webp'; return $s; },
        'sections-not-array' => static function (array $s): array { $s['detail_sections'] = 'synthetic'; return $s; },
        'section-unknown-field' => static function (array $s): array { $s['detail_sections'][0]['script'] = 'synthetic'; return $s; },
        'section-paragraph-type' => static function (array $s): array { $s['detail_sections'][0]['paragraphs'] = [17]; return $s; },
        'unsafe-link-origin' => static function (array $s): array { $s['detail_sections'][0]['links'][0]['href'] = 'https://example.invalid/'; return $s; },
        'unsafe-link-script' => static function (array $s): array { $s['detail_sections'][0]['links'][0]['href'] = 'javascript:synthetic'; return $s; },
        'unsafe-link-traversal' => static function (array $s): array { $s['detail_sections'][0]['links'][0]['href'] = '/../private.json'; return $s; },
        'unsafe-link-query' => static function (array $s): array { $s['detail_sections'][0]['links'][0]['href'] = '/projects.html?synthetic=1'; return $s; },
        'unapproved-link-anchor' => static function (array $s): array { $s['detail_sections'][0]['links'][0]['href'] = '/projects.html#synthetic-unapproved'; return $s; },
    ];
    foreach ($invalid as $label => $change) {
        cmsCase('validate-' . $label, function (Pilot $pilot) use ($change): void {
            cmsExpect(Invalid::class, fn() => $pilot->save(cmsCtx(), CMS_NOW, 0, $change(cmsService()), CMS_RELEASE, CMS_PRIVATE_SENTINEL));
            cmsRequire($pilot->load(cmsCtx(), CMS_NOW) === null);
        });
    }
    cmsCase('invalid-release', function (Pilot $pilot): void {
        cmsExpect(Invalid::class, fn() => $pilot->save(cmsCtx(), CMS_NOW, 0, cmsService(), '../synthetic', CMS_PRIVATE_SENTINEL));
        cmsRequire($pilot->load(cmsCtx(), CMS_NOW) === null);
    });
    cmsCase('invalid-expected-revision', function (Pilot $pilot): void {
        cmsExpect(Invalid::class, fn() => $pilot->save(cmsCtx(), CMS_NOW, -1, cmsService(), CMS_RELEASE));
    });
    cmsCase('canonical-existing-service-link', function (Pilot $pilot): void {
        $service = cmsService();
        $service['detail_sections'][0]['links'][] = ['label' => 'Existing canonical service', 'href' => '/layanan/huruf-timbul'];
        $saved = $pilot->save(cmsCtx(), CMS_NOW, 0, $service, CMS_RELEASE);
        cmsRequire($saved['public_service']['detail_sections'][0]['links'][1]['href'] === '/layanan/huruf-timbul');
        $pilot->approve(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
        $export = $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
        $decoded = json_decode($export['bytes'], true, 512, JSON_THROW_ON_ERROR);
        cmsRequire($decoded['services']['neon-box']['detail_sections'][0]['links'][1]['href'] === '/layanan/huruf-timbul');
    });
    cmsCase('unverified-legacy-service-link', function (Pilot $pilot): void {
        $service = cmsService();
        $service['detail_sections'][0]['links'][0]['href'] = '/huruf-timbul.html';
        cmsExpect(Invalid::class, fn() => $pilot->save(cmsCtx(), CMS_NOW, 0, $service, CMS_RELEASE));
    });
    cmsCase('current-public-baseline-compatibility', function (Pilot $unused, string $root) use ($repo): void {
        // This file is already public and reviewed; no config, API or private source is read.
        $bytes = file_get_contents($repo . '/public_html/includes/refresh-data.json');
        cmsRequire(is_string($bytes) && strlen($bytes) <= 1000000);
        $baseline = json_decode($bytes, true, 32, JSON_THROW_ON_ERROR);
        cmsRequire(count($baseline['services']) === 7 && isset($baseline['services']['neon-box']['detail_sections']));
        $pilot = cmsPilot($root, $repo, $baseline);
        $saved = $pilot->save(cmsCtx(), CMS_NOW, 0, $baseline['services']['neon-box'], CMS_RELEASE);
        cmsRequire($saved['public_service'] == $baseline['services']['neon-box']);
        $pilot->approve(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
        $export = $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
        cmsRequire(json_decode($export['bytes'], true, 32, JSON_THROW_ON_ERROR) == $baseline);
        cmsRequire(!str_contains($export['bytes'], CMS_PRIVATE_SENTINEL));
    });
    cmsCase('approved-existing-media-and-null', function (Pilot $pilot): void {
        $service = cmsService();
        $service['image'] = null;
        $saved = $pilot->save(cmsCtx(), CMS_NOW, 0, $service, CMS_RELEASE);
        cmsRequire($saved['public_service']['image'] === null);
        $service['image'] = 'synthetic-approved-photo';
        $next = $pilot->save(cmsCtx(), CMS_NOW, 1, $service, CMS_RELEASE);
        cmsRequire($next['public_service']['image'] === 'synthetic-approved-photo');
    });
    cmsCase('persist-reload-and-file-privacy', function (Pilot $pilot, string $root) use ($repo): void {
        $saved = $pilot->save(cmsCtx(), CMS_NOW, 0, cmsService(), CMS_RELEASE, CMS_PRIVATE_SENTINEL);
        $loaded = cmsPilot($root, $repo)->load(cmsCtx(CMS_OWNER, CMS_NOW + 3600, false), CMS_NOW);
        cmsRequire($loaded == $saved);
        cmsRequire($loaded['private_note'] === CMS_PRIVATE_SENTINEL);
        foreach (cmsFiles($root) as $file) {
            cmsRequire(!is_link($root . '/' . $file) && (fileperms($root . '/' . $file) & 0777) === 0600);
        }
    });
    cmsCase('stale-revision-does-not-overwrite', function (Pilot $pilot): void {
        $first = $pilot->save(cmsCtx(), CMS_NOW, 0, cmsService(), CMS_RELEASE);
        $changed = cmsService();
        $changed['body'] = 'Synthetic changed content.';
        cmsExpect(Conflict::class, fn() => $pilot->save(cmsCtx(), CMS_NOW, 0, $changed, CMS_RELEASE));
        cmsRequire($pilot->load(cmsCtx(), CMS_NOW) == $first);
    });
    cmsCase('approve-exact-revision-and-release', function (Pilot $pilot): void {
        $pilot->save(cmsCtx(), CMS_NOW, 0, cmsService(), CMS_RELEASE);
        cmsExpect(Conflict::class, fn() => $pilot->approve(cmsCtx(), CMS_NOW, 2, CMS_RELEASE));
        cmsExpect(Conflict::class, fn() => $pilot->approve(cmsCtx(), CMS_NOW, 1, CMS_NEXT_RELEASE));
        $approved = $pilot->approve(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
        cmsRequire($approved['status'] === 'approved' && $approved['approval']['revision'] === 1 &&
            $approved['approval']['prev_release'] === CMS_RELEASE &&
            preg_match('/^[a-f0-9]{64}$/D', $approved['approval']['output_sha256']) === 1);
    });
    cmsCase('export-deterministic-and-whitelisted', function (Pilot $pilot): void {
        $approved = cmsApproved($pilot);
        $a = $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE);
        $b = $pilot->export(cmsCtx(), CMS_NOW + 1, 1, CMS_RELEASE);
        cmsRequire($a === $b);
        $keys = array_keys($a); sort($keys);
        cmsRequire($keys === ['bytes', 'path', 'prev_release', 'sha256', 'source_rev']);
        cmsRequire($a['path'] === 'includes/refresh-data.json' && $a['source_rev'] === 1 && $a['prev_release'] === CMS_RELEASE);
        cmsRequire(str_ends_with($a['bytes'], "\n") && hash('sha256', $a['bytes']) === $a['sha256']);
        cmsRequire($a['sha256'] === $approved['approval']['output_sha256']);
        $decoded = json_decode($a['bytes'], true, 512, JSON_THROW_ON_ERROR);
        $expected = cmsBaseline();
        $expected['services']['neon-box'] = $approved['public_service'];
        cmsRequire($decoded == $expected);
        cmsRequire(!str_contains($a['bytes'], CMS_PRIVATE_SENTINEL));
        foreach (['private_note', 'approval', 'baseline_sha256', 'configuredOwner'] as $privateKey) {
            cmsRequire(!array_key_exists($privateKey, $decoded));
        }
    });
    cmsCase('edit-revokes-approval-and-stale-export', function (Pilot $pilot): void {
        cmsApproved($pilot);
        $next = cmsService();
        $next['body'] = 'Synthetic second revision.';
        $saved = $pilot->save(cmsCtx(), CMS_NOW, 1, $next, CMS_RELEASE, CMS_PRIVATE_SENTINEL);
        cmsRequire($saved['revision'] === 2 && $saved['status'] === 'draft' && $saved['approval'] === null);
        cmsExpect(Conflict::class, fn() => $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE));
        cmsExpect(Conflict::class, fn() => $pilot->export(cmsCtx(), CMS_NOW, 2, CMS_RELEASE));
        $pilot->approve(cmsCtx(), CMS_NOW, 2, CMS_RELEASE);
        $export = $pilot->export(cmsCtx(), CMS_NOW, 2, CMS_RELEASE);
        cmsRequire($export['source_rev'] === 2 && json_decode($export['bytes'], true, 512, JSON_THROW_ON_ERROR)['services']['neon-box']['body'] === $next['body']);
    });
    cmsCase('current-release-mismatch', function (Pilot $pilot): void {
        cmsApproved($pilot);
        cmsExpect(Conflict::class, fn() => $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_NEXT_RELEASE));
    });
    cmsCase('baseline-drift-invalidates-approval', function (Pilot $pilot, string $root) use ($repo): void {
        cmsApproved($pilot);
        $baseline = cmsBaseline();
        $baseline['services']['papan-nama']['body'] = 'Synthetic changed baseline.';
        $changed = cmsPilot($root, $repo, $baseline);
        cmsExpect(Conflict::class, fn() => $changed->load(cmsCtx(), CMS_NOW));
        cmsExpect(Conflict::class, fn() => $changed->approve(cmsCtx(), CMS_NOW, 1, CMS_RELEASE));
        cmsExpect(Conflict::class, fn() => $changed->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE));
    });
    foreach ([
        'approved-public-content' => static function (array $s): array { $s['public_service']['body'] = 'Synthetic unauthorized state edit.'; return $s; },
        'approval-revision' => static function (array $s): array { $s['approval']['revision'] = 2; return $s; },
        'approval-output-hash' => static function (array $s): array { $s['approval']['output_sha256'] = str_repeat('0', 64); return $s; },
        'unknown-state-key' => static function (array $s): array { $s['unknown_private_key'] = CMS_PRIVATE_SENTINEL; return $s; },
    ] as $label => $tamper) {
        cmsCase('tamper-' . $label, function (Pilot $pilot, string $root) use ($tamper): void {
            cmsWriteState($root, $tamper(cmsApproved($pilot)));
            cmsExpect(Invalid::class, fn() => $pilot->load(cmsCtx(), CMS_NOW));
            cmsExpect(Invalid::class, fn() => $pilot->export(cmsCtx(), CMS_NOW, 1, CMS_RELEASE));
        });
    }
    cmsCase('malformed-state-fails-closed', function (Pilot $pilot, string $root): void {
        cmsApproved($pilot);
        file_put_contents($root . '/neon-box-state.json', '{"synthetic":');
        cmsExpect(Invalid::class, fn() => $pilot->load(cmsCtx(), CMS_NOW));
    });
    cmsCase('private-root-public-descendant', function (Pilot $unused, string $root) use ($repo): void {
        $public = $root . '/public';
        $private = $public . '/cms';
        cmsMkdir($public);
        cmsMkdir($private);
        cmsExpect(Invalid::class, fn() => new Pilot($private, [$repo . '/public_html', $public], cmsBaseline(), CMS_OWNER));
        cmsRequire(cmsFiles($private) === []);
    });
    cmsCase('private-root-relative', function (Pilot $unused) use ($repo): void {
        cmsExpect(Invalid::class, fn() => new Pilot('relative-synthetic-root', [$repo . '/public_html'], cmsBaseline(), CMS_OWNER));
    });
    cmsCase('private-root-open-permissions', function (Pilot $unused, string $root) use ($repo): void {
        $open = $root . '/open';
        cmsMkdir($open);
        chmod($open, 0777);
        cmsExpect(Storage::class, fn() => cmsPilot($open, $repo));
        cmsRequire(cmsFiles($open) === []);
        chmod($open, 0700);
    });

    if (function_exists('symlink')) {
        cmsCase('private-root-symlink', function (Pilot $unused, string $root) use ($repo): void {
            $target = $root . '/target';
            cmsMkdir($target);
            cmsRequire(symlink($target, $root . '/link'));
            cmsExpect(Invalid::class, fn() => cmsPilot($root . '/link', $repo));
            cmsRequire(cmsFiles($target) === []);
        });
        cmsCase('state-symlink-rejected', function (Pilot $pilot, string $root): void {
            $target = $root . '/target.txt';
            file_put_contents($target, 'Synthetic protected sentinel.');
            chmod($target, 0600);
            cmsRequire(symlink($target, $root . '/neon-box-state.json'));
            cmsExpect(Storage::class, fn() => $pilot->load(cmsCtx(), CMS_NOW));
            cmsRequire(file_get_contents($target) === 'Synthetic protected sentinel.');
        });
    } else {
        cmsNotRun('private-root-symlink', 'SymlinkUnavailable');
        cmsNotRun('state-symlink-rejected', 'SymlinkUnavailable');
    }
    if (function_exists('link')) {
        cmsCase('state-hardlink-rejected', function (Pilot $pilot, string $root): void {
            $target = $root . '/target.txt';
            file_put_contents($target, 'Synthetic protected sentinel.');
            chmod($target, 0600);
            cmsRequire(link($target, $root . '/neon-box-state.json'));
            cmsExpect(Storage::class, fn() => $pilot->load(cmsCtx(), CMS_NOW));
            cmsRequire(file_get_contents($target) === 'Synthetic protected sentinel.');
        });
    } else {
        cmsNotRun('state-hardlink-rejected', 'HardlinkUnavailable');
    }
    if (function_exists('proc_open')) {
        cmsCase('two-process-compare-and-swap', function (Pilot $unused, string $root) use ($repo): void {
            $private = $root . '/private';
            cmsMkdir($private);
            file_put_contents($root . '/barrier', 'wait');
            $workers = [];
            try {
                foreach (['a', 'b'] as $who) {
                    $pipes = [];
                    $process = proc_open([PHP_BINARY, __FILE__, '--worker', $root, $who],
                        [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, $repo);
                    cmsRequire(is_resource($process));
                    fclose($pipes[0]);
                    $workers[] = [$process, $pipes];
                }
                $deadline = microtime(true) + 10;
                while ((!is_file($root . '/ready-a') || !is_file($root . '/ready-b')) && microtime(true) < $deadline) usleep(10000);
                cmsRequire(is_file($root . '/ready-a') && is_file($root . '/ready-b'));
                unlink($root . '/barrier');
                $outcomes = [];
                foreach ($workers as [$process, $pipes]) {
                    stream_set_blocking($pipes[1], false);
                    stream_set_blocking($pipes[2], false);
                    $stdout = ''; $stderr = ''; $exitCode = null;
                    $deadline = microtime(true) + 20;
                    do {
                        $stdout .= stream_get_contents($pipes[1]);
                        $stderr .= stream_get_contents($pipes[2]);
                        $status = proc_get_status($process);
                        if (!$status['running']) {
                            $exitCode = $status['exitcode'];
                            $stdout .= stream_get_contents($pipes[1]);
                            $stderr .= stream_get_contents($pipes[2]);
                            break;
                        }
                        usleep(10000);
                    } while (microtime(true) < $deadline);
                    cmsRequire($exitCode === 0 && $stderr === '');
                    fclose($pipes[1]); fclose($pipes[2]);
                    proc_close($process);
                    $message = json_decode($stdout, true, 512, JSON_THROW_ON_ERROR);
                    cmsRequire(in_array($message['status'], ['saved', 'conflict'], true));
                    $outcomes[] = $message['status'];
                }
                $workers = [];
                sort($outcomes);
                cmsRequire($outcomes === ['conflict', 'saved']);
                $loaded = cmsPilot($private, $repo)->load(cmsCtx(), CMS_NOW);
                cmsRequire($loaded['revision'] === 1 && $loaded['status'] === 'draft');
                cmsRequire(in_array($loaded['public_service']['body'], ['Synthetic concurrent body a.', 'Synthetic concurrent body b.'], true));
            } finally {
                foreach ($workers as [$process, $pipes]) {
                    if (is_resource($process)) proc_terminate($process);
                    foreach ($pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
                    if (is_resource($process)) proc_close($process);
                }
            }
        });
    } else {
        cmsNotRun('two-process-compare-and-swap', 'ProcessUnavailable');
    }
} catch (Throwable $error) {
    $results[] = ['name' => 'offline-suite-setup', 'status' => 'FAIL', 'category' => 'Setup'];
} finally {
    if (isset($testRoot)) {
        foreach (array_reverse($created) as $root) {
            try { cmsClean($root, $testRoot); }
            catch (Throwable $error) { $results[] = ['name' => 'private-fixture-cleanup', 'status' => 'FAIL', 'category' => 'Cleanup']; }
        }
    }
}
$report = [
    'scope' => 'offline synthetic PHP CLI only; no hosting authentication, endpoint or publisher',
    'passed' => count(array_filter($results, fn(array $r): bool => $r['status'] === 'PASS')),
    'failed' => count(array_filter($results, fn(array $r): bool => $r['status'] === 'FAIL')),
    'not_run' => count(array_filter($results, fn(array $r): bool => $r['status'] === 'NOT RUN')),
    'results' => $results,
    'limitations' => [
        'OwnerContext values are trusted mock adapter inputs, not evidence of hosting authentication.',
        'Concurrent CAS is tested with two PHP processes when proc_open is available.',
        'Interrupted write/crash durability and hosting permissions/open_basedir are not proved by this suite.',
        'No private state, note, draft or exported JSON payload is retained as an artifact.',
    ],
];
$json = json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
cmsRequire(!str_contains($json, CMS_PRIVATE_SENTINEL));
$reportPath = getenv('CMS_RESULT_PATH');
if (is_string($reportPath) && $reportPath !== '') {
    $allowedReport = isset($repo) ? $repo . DIRECTORY_SEPARATOR . 'artifacts' . DIRECTORY_SEPARATOR . 'cms-offline' . DIRECTORY_SEPARATOR . 'results.json' : '';
    if (!isset($repo) || $reportPath !== $allowedReport || is_link(dirname($reportPath)) || is_link($reportPath)) {
        fwrite(STDERR, "REPORT_PATH_REJECTED\n");
        exit(1);
    }
    if (!is_dir(dirname($reportPath)) && !mkdir(dirname($reportPath), 0700, true)) exit(1);
    if (file_put_contents($reportPath, $json) === false) exit(1);
}
fwrite(STDOUT, $json);
exit($report['failed'] === 0 && $report['not_run'] === 0 ? 0 : 1);
