<?php
declare(strict_types=1);

/* Focused, synthetic gateway cases; no hosting/auth secrets or draft logging. */
require_once __DIR__ . '/../cms/owner-gateway.php';

use KanCms\GatewayConfig;
use KanCms\OwnerGateway;
use KanCms\TrustedOwner;
use KanCms\DraftAdapter;
use KanCms\Pilot;
use KanCms\Invalid;

$repo = realpath(__DIR__ . '/..');
$baseline = json_decode(file_get_contents($repo . '/public_html/includes/refresh-data.json'), true, 32, JSON_THROW_ON_ERROR);
$release = str_repeat('a', 40);
$now = 1700000000;
$roots = [];
$results = [];
$cases = [];
$skipped = 0;

function must(bool $condition): void { if (!$condition) throw new LogicException('Assertion'); }
function clean(string $path): void {
    foreach (new DirectoryIterator($path) as $item) {
        if ($item->isDot()) continue;
        $child = $item->getPathname();
        if ($item->isDir() && !$item->isLink()) clean($child); else unlink($child);
    }
    rmdir($path);
}
function fixture(bool $enabled = true, ?array $map = null): array {
    global $repo, $baseline, $release, $now, $roots;
    $root = realpath(sys_get_temp_dir()) . '/kan-owner-fixture-' . bin2hex(random_bytes(12));
    if (!mkdir($root, 0700)) throw new RuntimeException('Fixture');
    $roots[] = $root;
    $map ??= ['a' => 'produk-39db8e80530c', 'b' => 'produk-fcf95321686c'];
    $config = new GatewayConfig($root, [$repo . '/public_html'], [$repo], $baseline, 'synthetic-owner', $release, $map, $enabled);
    $snapshot = ['fields' => ['kind' => 'Layanan', 'title' => 'Synthetic Neon Draft',
        'summary' => 'Synthetic public summary', 'fact' => 'PRIVATE_FACT_DO_NOT_EXPORT',
        'source' => 'PRIVATE_SOURCE_DO_NOT_EXPORT', 'verified' => true],
        'order' => ['a', 'b'], 'rights' => ['a', 'b'], 'cover' => 'a'];
    return ['root' => $root, 'config' => $config, 'snapshot' => $snapshot];
}
function gateway(array $f, ?string $identity = 'synthetic-owner', ?int $expiry = null): OwnerGateway {
    global $now;
    return new OwnerGateway($f['config'], new TrustedOwner($identity, $expiry ?? $now + 86400));
}
function loadDraft(array $f, array &$session, ?int $time = null): array {
    global $now;
    return gateway($f)->dispatch('GET', ['action' => 'load'], '', null, null, '', $session, $time ?? $now);
}
function postDraft(array $f, array &$session, string $action, array $payload, ?int $time = null,
    ?string $csrf = null, ?string $origin = 'https://www.3dkanadvertising.store'): array {
    global $now;
    $csrf ??= $session['kan_cms_owner']['csrf'] ?? null;
    return gateway($f)->dispatch('POST', [], 'application/json', $origin, $csrf,
        json_encode(['action' => $action, 'payload' => $payload], JSON_THROW_ON_ERROR), $session, $time ?? $now);
}
function saveDraft(array $f, array &$session, int $revision = 0, ?array $snapshot = null): array {
    return postDraft($f, $session, 'save', ['expected_revision' => $revision, 'snapshot' => $snapshot ?? $f['snapshot']]);
}
function prepared(array $f, array &$session): void {
    must(loadDraft($f, $session)['status'] === 200);
    must(saveDraft($f, $session)['status'] === 200);
}
function approved(array $f, array &$session, int $revision = 1): void {
    must(postDraft($f, $session, 'preview', ['expected_revision' => $revision])['status'] === 200);
    must(postDraft($f, $session, 'approve', ['expected_revision' => $revision])['status'] === 200);
}
function invalidMap(array $map): void {
    $f = fixture();
    global $baseline, $release;
    $pilot = new Pilot($f['root'], $f['config']->publicRoots, $baseline, 'synthetic-owner');
    try { new DraftAdapter($pilot, $baseline['services']['neon-box'], $map, $release); }
    catch (Invalid $error) { return; }
    throw new LogicException('Expected Invalid');
}
function test(string $name, callable $fn): void {
    global $cases;
    if (isset($cases[$name])) throw new LogicException('Duplicate case');
    $cases[$name] = $fn;
}

try {
    test('anonymous-denied-before-private-write', function (): void {
        $f = fixture(); $session = [];
        $r = gateway($f, null)->dispatch('GET', ['action' => 'load'], '', null, null, '', $session, 1700000000);
        must($r['status'] === 401 && $r['body'] === ['ok' => false, 'category' => 'Access']);
        must(array_diff(scandir($f['root']), ['.', '..']) === []);
    });
    test('non-owner-and-expired-boundary-denied', function (): void {
        $f = fixture(); $session = [];
        foreach ([gateway($f, 'other-owner'), gateway($f, 'synthetic-owner', 1700000000)] as $g) {
            must($g->dispatch('GET', ['action' => 'load'], '', null, null, '', $session, 1700000000)['status'] === 401);
        }
    });
    test('no-post-session-bootstrap', function (): void {
        $f = fixture(); $session = [];
        must(postDraft($f, $session, 'save', ['expected_revision' => 0, 'snapshot' => $f['snapshot']])['status'] === 401);
        must(!file_exists($f['root'] . '/neon-box-state.json'));
    });
    test('load-two-real-approved-media-and-opaque-csrf', function (): void {
        $f = fixture(); $session = []; $r = loadDraft($f, $session);
        must($r['status'] === 200 && $r['body']['state'] === ['revision' => 0, 'status' => 'empty', 'snapshot' => null]);
        must(preg_match('/\A[a-f0-9]{64}\z/', $r['body']['csrf']) === 1);
        must(array_column($r['body']['config']['media'], 'id') === ['a', 'b']);
        must($r['body']['config']['service']['cover'] === 'a');
        $bytes = json_encode($r['body']);
        must(!str_contains($bytes, $f['root']) && !str_contains($bytes, 'synthetic-owner'));
    });
    test('csrf-missing-or-wrong-and-cross-origin-rejected', function (): void {
        $f = fixture(); $session = []; loadDraft($f, $session);
        foreach ([['wrong', 'https://www.3dkanadvertising.store'], [$session['kan_cms_owner']['csrf'], 'https://example.invalid']] as [$token, $origin]) {
            must(postDraft($f, $session, 'save', ['expected_revision' => 0, 'snapshot' => $f['snapshot']], null, $token, $origin)['status'] === 403);
        }
        must(!file_exists($f['root'] . '/neon-box-state.json'));
    });
    test('exact-payload-rejects-client-receipt-and-identity', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        foreach (['review', 'identity', 'approved', 'current_release'] as $field) {
            must(postDraft($f, $session, 'approve', ['expected_revision' => 1, $field => 'forged'])['status'] === 422);
        }
    });
    test('wrong-content-type-method-query-and-oversized-body', function (): void {
        $f = fixture(); $session = []; loadDraft($f, $session); $g = gateway($f);
        must($g->dispatch('POST', [], 'text/plain', null, null, '{}', $session, 1700000000)['status'] === 422);
        must($g->dispatch('PUT', [], '', null, null, '', $session, 1700000000)['status'] === 405);
        must($g->dispatch('GET', ['action' => 'load', 'owner' => 'forged'], '', null, null, '', $session, 1700000000)['status'] === 422);
        must($g->dispatch('POST', [], 'application/json', null, null, str_repeat('x', 16385), $session, 1700000000)['status'] === 422);
    });
    test('save-load-new-object-preserves-private-draft', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); $r = loadDraft($f, $session);
        must($r['body']['state']['revision'] === 1 && $r['body']['state']['snapshot'] === $f['snapshot']);
    });
    test('approve-without-preview-is-conflict', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        must(postDraft($f, $session, 'approve', ['expected_revision' => 1])['status'] === 409);
    });
    test('separate-http-object-preview-approve-binding', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); approved($f, $session);
        must($session['kan_cms_owner']['review'] === null && is_array($session['kan_cms_owner']['approved']));
    });
    test('session-b-cannot-use-session-a-review', function (): void {
        $f = fixture(); $a = []; $b = []; prepared($f, $a); loadDraft($f, $b);
        must(postDraft($f, $a, 'preview', ['expected_revision' => 1])['status'] === 200);
        $b['kan_cms_owner']['review'] = $a['kan_cms_owner']['review'];
        must(postDraft($f, $b, 'approve', ['expected_revision' => 1])['status'] === 409);
        must(postDraft($f, $a, 'approve', ['expected_revision' => 1])['status'] === 200);
    });
    test('receipt-expiry-requires-new-preview', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        postDraft($f, $session, 'preview', ['expected_revision' => 1]);
        must(postDraft($f, $session, 'approve', ['expected_revision' => 1], 1700000601)['status'] === 409);
    });
    test('session-idle-and-absolute-expiry-enforced', function (): void {
        foreach ([1700000901, 1700001801] as $time) {
            $f = fixture(); $session = []; prepared($f, $session);
            must(postDraft($f, $session, 'preview', ['expected_revision' => 1], $time)['status'] === 401);
            must(!isset($session['kan_cms_owner']));
        }
    });
    test('new-release-invalidates-old-session-and-state', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        $c = $f['config'];
        $f['config'] = new GatewayConfig($c->root, $c->publicRoots, $c->repositoryRoots, $c->baseline,
            $c->configuredOwner, str_repeat('b', 40), $c->photoMap, true);
        must(postDraft($f, $session, 'preview', ['expected_revision' => 1])['status'] === 401);
        must(loadDraft($f, $session)['status'] === 409);
    });
    test('private-only-edit-invalidates-review', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        postDraft($f, $session, 'preview', ['expected_revision' => 1]);
        $edit = $f['snapshot']; $edit['fields']['source'] = 'PRIVATE_EDIT'; $edit['fields']['verified'] = false;
        must(saveDraft($f, $session, 1, $edit)['body']['state']['revision'] === 2);
        must(postDraft($f, $session, 'approve', ['expected_revision' => 2])['status'] === 409);
    });
    test('concurrent-newer-revision-clears-stale-review', function (): void {
        $f = fixture(); $a = []; $b = []; prepared($f, $a); loadDraft($f, $b);
        postDraft($f, $a, 'preview', ['expected_revision' => 1]);
        must(saveDraft($f, $b, 1)['status'] === 200);
        must(postDraft($f, $a, 'approve', ['expected_revision' => 1])['status'] === 409);
        must($a['kan_cms_owner']['review'] === null);
    });
    test('rights-and-fact-blockers-remain-server-side', function (): void {
        $f = fixture(); $session = []; loadDraft($f, $session);
        $draft = $f['snapshot']; $draft['rights'] = []; $draft['fields']['verified'] = false;
        must(saveDraft($f, $session, 0, $draft)['status'] === 200);
        must(postDraft($f, $session, 'preview', ['expected_revision' => 1])['status'] === 200);
        must(postDraft($f, $session, 'approve', ['expected_revision' => 1])['status'] === 422);
    });
    test('private-handoff-disabled-by-default', function (): void {
        $f = fixture(false); $session = []; prepared($f, $session); approved($f, $session);
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 1])['status'] === 503);
        must(!file_exists($f['root'] . '/neon-box-publication-request.json'));
    });
    test('request-idempotent-sanitized-private-not-live', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); approved($f, $session);
        $a = postDraft($f, $session, 'request-publication', ['expected_revision' => 1]);
        $b = postDraft($f, $session, 'request-publication', ['expected_revision' => 1]);
        must($a['status'] === 200 && $a === $b && $a['body']['request']['status'] === 'requested');
        must(array_keys($a['body']) === ['ok', 'request']);
        $path = $f['root'] . '/neon-box-publication-request.json';
        must((fileperms($path) & 0077) === 0);
        $stored = file_get_contents($path);
        must(!str_contains($stored, 'PRIVATE_FACT') && !str_contains($stored, 'PRIVATE_SOURCE')
            && !str_contains($stored, 'synthetic-owner') && !str_contains($stored, '"snapshot"'));
        $request = json_decode($stored, true, 32, JSON_THROW_ON_ERROR);
        must(hash('sha256', $request['bytes']) === $request['output_sha256']);
        global $baseline;
        $output = json_decode($request['bytes'], true, 32, JSON_THROW_ON_ERROR);
        $output['services']['neon-box'] = $baseline['services']['neon-box'];
        must($output === $baseline);
    });
    test('new-save-invalidates-pending-handoff', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); approved($f, $session);
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 1])['status'] === 200);
        must(saveDraft($f, $session, 1)['status'] === 200);
        must(!file_exists($f['root'] . '/neon-box-publication-request.json'));
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 2])['status'] === 409);
    });
    test('load-clears-old-session-preview', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        postDraft($f, $session, 'preview', ['expected_revision' => 1]); loadDraft($f, $session);
        must(postDraft($f, $session, 'approve', ['expected_revision' => 1])['status'] === 409);
    });
    test('public-root-and-repository-root-not-private-storage', function (): void {
        global $repo, $baseline, $release;
        foreach ([$repo, $repo . '/public_html'] as $root) {
            try { new GatewayConfig($root, [$repo . '/public_html'], [$repo], $baseline,
                'synthetic-owner', $release, ['a' => 'produk-39db8e80530c']); }
            catch (Invalid $error) { continue; }
            throw new LogicException('Expected Invalid');
        }
    });
    test('verified-host-without-checkout-repository-list', function (): void {
        $f = fixture(); $c = $f['config']; $session = [];
        $f['config'] = new GatewayConfig($c->root, $c->publicRoots, [], $c->baseline,
            $c->configuredOwner, $c->currentRelease, $c->photoMap, true);
        must(loadDraft($f, $session)['status'] === 200);
    });
    test('cancel-failure-does-not-advance-draft', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); approved($f, $session);
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 1])['status'] === 200);
        $path = $f['root'] . '/neon-box-publication-request.json';
        $held = $f['root'] . '/.held-request.json';
        $requestBefore = file_get_contents($path);
        $statePath = $f['root'] . '/neon-box-state.json';
        $stateBefore = file_get_contents($statePath);
        $g = gateway($f);
        must(rename($path, $held) && mkdir($path, 0700));
        $edit = $f['snapshot']; $edit['fields']['title'] = 'Synthetic cancellation edit';
        $r = $g->dispatch('POST', [], 'application/json', 'https://www.3dkanadvertising.store',
            $session['kan_cms_owner']['csrf'], json_encode(['action' => 'save', 'payload' =>
                ['expected_revision' => 1, 'snapshot' => $edit]], JSON_THROW_ON_ERROR), $session, 1700000000);
        must($r['status'] === 503);
        must(file_get_contents($statePath) === $stateBefore && file_get_contents($held) === $requestBefore);
        $loaded = loadDraft($f, $session)['body']['state'];
        must($loaded['revision'] === 1 && $loaded['status'] === 'approved' && $loaded['snapshot'] === $f['snapshot']);
    });
    test('invalid-snapshot-retains-private-request', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); approved($f, $session);
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 1])['status'] === 200);
        $path = $f['root'] . '/neon-box-publication-request.json';
        $before = file_get_contents($path);
        $statePath = $f['root'] . '/neon-box-state.json';
        $stateBefore = file_get_contents($statePath);
        foreach (['title', 'summary'] as $field) {
            foreach (['', '   ', '<b>bad</b>', 'javascript:bad', 'vbscript:bad', 'data:bad'] as $bad) {
                $edit = $f['snapshot']; $edit['fields'][$field] = $bad;
                must(saveDraft($f, $session, 1, $edit)['status'] === 422);
                must(file_get_contents($path) === $before && file_get_contents($statePath) === $stateBefore);
            }
        }
        $edit = $f['snapshot']; $edit['fields']['fact'] = str_repeat('\\', 2000);
        must(saveDraft($f, $session, 1, $edit)['status'] === 422);
        must(file_get_contents($path) === $before && file_get_contents($statePath) === $stateBefore);
        must(saveDraft($f, $session, 0)['status'] === 409);
        must(file_get_contents($path) === $before && file_get_contents($statePath) === $stateBefore);
    });
    test('revision-ceiling-retains-private-request', function (): void {
        $f = fixture(); $session = []; prepared($f, $session); approved($f, $session);
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 1])['status'] === 200);
        $statePath = $f['root'] . '/neon-box-state.json';
        $requestPath = $f['root'] . '/neon-box-publication-request.json';
        $state = json_decode(file_get_contents($statePath), true, 32, JSON_THROW_ON_ERROR);
        $request = json_decode(file_get_contents($requestPath), true, 32, JSON_THROW_ON_ERROR);
        $state['revision'] = PHP_INT_MAX - 1;
        $state['approval']['revision'] = $state['revision'];
        $request['source_rev'] = $state['revision'];
        $request['request_id'] = hash('sha256', $request['prev_release'] . "\n"
            . $request['source_rev'] . "\n" . $request['output_sha256']);
        must(file_put_contents($statePath, json_encode($state, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE
            | JSON_UNESCAPED_SLASHES) . "\n") !== false);
        must(file_put_contents($requestPath, json_encode($request, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE
            | JSON_UNESCAPED_SLASHES) . "\n") !== false);
        $stateBefore = file_get_contents($statePath);
        $requestBefore = file_get_contents($requestPath);
        $edit = $f['snapshot']; $edit['fields']['title'] = 'Synthetic ceiling edit';
        must(saveDraft($f, $session, PHP_INT_MAX - 1, $edit)['status'] === 409);
        must(file_get_contents($statePath) === $stateBefore && file_get_contents($requestPath) === $requestBefore);
        $loaded = loadDraft($f, $session)['body']['state'];
        must($loaded['revision'] === PHP_INT_MAX - 1 && $loaded['status'] === 'approved');
    });
    test('absolute-expiry-after-valid-activity', function (): void {
        $f = fixture(); $session = []; prepared($f, $session);
        must(postDraft($f, $session, 'preview', ['expected_revision' => 1], 1700000899)['status'] === 200);
        must(postDraft($f, $session, 'preview', ['expected_revision' => 1], 1700001798)['status'] === 200);
        must(postDraft($f, $session, 'approve', ['expected_revision' => 1], 1700001799)['status'] === 200);
        must(postDraft($f, $session, 'request-publication', ['expected_revision' => 1], 1700001800)['status'] === 401);
        must(!isset($session['kan_cms_owner']) && !file_exists($f['root'] . '/neon-box-publication-request.json'));
    });
    test('one-and-two-approved-map-supported', function (): void {
        $f = fixture(true, ['a' => 'produk-39db8e80530c']); $session = [];
        must(count(loadDraft($f, $session)['body']['config']['media']) === 1);
        $f = fixture(); $session = [];
        must(count(loadDraft($f, $session)['body']['config']['media']) === 2);
    });
    test('empty-unknown-and-duplicate-map-rejected', function (): void {
        invalidMap([]);
        invalidMap(['z' => 'produk-39db8e80530c']);
        invalidMap(['a' => 'produk-39db8e80530c', 'b' => 'produk-39db8e80530c']);
    });
    $selected = array_slice($argv, 1);
    if (count(array_unique($selected)) !== count($selected) || array_diff($selected, array_keys($cases)) !== []) {
        echo json_encode(['runtime' => PHP_VERSION, 'passed' => 0, 'failed' => 1,
            'skipped' => count($cases), 'category' => 'SelectionError'], JSON_THROW_ON_ERROR) . "\n";
        exit(2);
    }
    foreach ($cases as $name => $fn) {
        if ($selected !== [] && !in_array($name, $selected, true)) { $skipped++; continue; }
        try { $fn(); $results[] = ['name' => $name, 'status' => 'PASS']; }
        catch (Throwable $error) { $results[] = ['name' => $name, 'status' => 'FAIL', 'category' => get_class($error)]; }
    }
} finally {
    foreach ($roots as $root) if (is_dir($root) && !is_link($root)) clean($root);
}
$failed = count(array_filter($results, fn($row) => $row['status'] !== 'PASS'));
echo json_encode(['runtime' => PHP_VERSION, 'passed' => count($results) - $failed,
    'failed' => $failed, 'skipped' => $skipped, 'results' => $results], JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT) . "\n";
exit($failed === 0 ? 0 : 1);
