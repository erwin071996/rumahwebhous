<?php
declare(strict_types=1);

require_once __DIR__ . '/../cms/owner-request-guard.php';
// Optional CLI source path allows this three-file patch to be checked before
// integration. Normal repository runs use the existing Pilot beside the guard.
require_once $argv[1] ?? __DIR__ . '/../cms/neon_box_pilot.php';

use KanCms\OwnerRequestGuard;
use KanCms\OwnerContext;
use KanCms\Pilot;

// Synthetic Pilot fixture only. No HTTP, sessions, queue or publication.
$release = str_repeat('a', 40);
$otherRelease = str_repeat('b', 40);
$service = [
    'name' => 'Contoh Neon Box', 'symbol' => 'N', 'intro' => 'Konten sintetis.',
    'body' => 'Dokumentasi pengujian.', 'options' => ['Opsi contoh'],
    'guide' => 'Brief contoh.', 'image' => null
];
$baseline = ['domain' => 'https://www.3dkanadvertising.store', 'asset' => [],
    'logo' => null, 'phone' => '0000000000',
    'services' => array_fill_keys(['huruf-timbul', 'neon-flex', 'papan-nama',
        'stiker-cutting', 'neon-box', 'reklame', 'nametag'], $service),
    'cities' => [], 'legacy_services' => [], 'photos' => [], 'organization' => []];
$fixture = sys_get_temp_dir() . '/kan-request-guard-' . bin2hex(random_bytes(12));
$private = $fixture . '/private';
$public = $fixture . '/public';
try {
    if (!mkdir($fixture, 0700) || !mkdir($private, 0700) || !mkdir($public, 0700)) {
        throw new RuntimeException('Fixture');
    }
    $pilot = new Pilot($private, [$public], $baseline, 'synthetic-owner');
    $context = new OwnerContext('synthetic-owner', 5000, true);
    $pilot->save($context, 1000, 0, $service, $release,
        'Catatan sintetis yang tidak boleh keluar.');
    $pilot->approve($context, 1001, 1, $release);
    $state = $pilot->load($context, 1002);
    $export = $pilot->export($context, 1002, $state['revision'], $release);
} finally {
    // Only paths created by this synthetic fixture, never caller storage.
    foreach (['neon-box-state.json', '.neon-box.lock'] as $file) {
        $path = $private . '/' . $file;
        if (is_file($path)) unlink($path);
    }
    foreach ([$private, $public, $fixture] as $directory) {
        if (is_dir($directory)) rmdir($directory);
    }
}
$bytes = $export['bytes'];
$sha = $export['sha256'];
$request = ['schema_version' => 1,
    'request_id' => hash('sha256', $release . "\n1\n" . $sha), 'status' => 'requested',
    'source_rev' => 1, 'prev_release' => $release, 'output_sha256' => $sha,
    'path' => 'includes/refresh-data.json', 'bytes' => $bytes];
$tuple = [$request, $state, $export, $release];
$passed = 0;
$failed = 0;

function check(string $name, bool $passed): void
{
    global $failed;
    if ($passed) {
        $GLOBALS['passed']++;
    } else {
        $failed++;
        fwrite(STDERR, 'FAIL ' . $name . "\n");
    }
}

function reject(string $name, array $tuple, string $category): void
{
    check($name, OwnerRequestGuard::validate(...$tuple) === ['ok' => false, 'category' => $category]);
}

function change(array $tuple, int $argument, array $path, mixed $value): array
{
    $target =& $tuple[$argument];
    foreach ($path as $key) $target =& $target[$key];
    $target = $value;
    return $tuple;
}

function resign(array $tuple): array
{
    $tuple[0]['output_sha256'] = hash('sha256', $tuple[0]['bytes']);
    $tuple[0]['request_id'] = hash('sha256', $tuple[0]['prev_release'] . "\n"
        . $tuple[0]['source_rev'] . "\n" . $tuple[0]['output_sha256']);
    return $tuple;
}

$accepted = OwnerRequestGuard::validate(...$tuple);
$receipt = ['schema_version' => 1, 'request_id' => $request['request_id'],
    'source_rev' => 1, 'prev_release' => $release, 'output_sha256' => $sha,
    'path' => 'includes/refresh-data.json'];
check('actual Pilot load and approved export accepted', $accepted === ['ok' => true, 'receipt' => $receipt]);
check('repeat validation is deterministic', OwnerRequestGuard::validate(...$tuple) === $accepted);
$before = serialize($tuple);
OwnerRequestGuard::validate(...$tuple);
check('validation does not mutate inputs', serialize($tuple) === $before);
ob_start();
OwnerRequestGuard::validate(...$tuple);
$printed = ob_get_clean();
check('validator emits no content', $printed === '');
check('receipt excludes content and private metadata', !str_contains(json_encode($accepted, JSON_THROW_ON_ERROR),
    $state['private_note']) && !array_key_exists('bytes', $accepted['receipt'])
    && !array_key_exists('public_service', $accepted['receipt']));
$reordered = $tuple;
foreach ([0, 1, 2] as $argument) $reordered[$argument] = array_reverse($reordered[$argument], true);
$reordered[1]['approval'] = array_reverse($reordered[1]['approval'], true);
check('JSON object key order is immaterial', OwnerRequestGuard::validate(...$reordered) === $accepted);

foreach ([0, 1, 2, 3] as $argument) {
    foreach ([null, false, 1, new stdClass()] as $value) {
        $invalid = $tuple;
        $invalid[$argument] = $value;
        reject('reject nonmatching argument ' . $argument . ' type ' . get_debug_type($value), $invalid, 'Invalid');
    }
}
foreach ([0, 1, 2] as $argument) {
    foreach (array_keys($tuple[$argument]) as $key) {
        $invalid = $tuple;
        unset($invalid[$argument][$key]);
        reject('missing field ' . $argument . ':' . $key, $invalid, 'Invalid');
    }
    reject('extra field ' . $argument, change($tuple, $argument, ['unexpected'], true), 'Invalid');
    reject('numeric extra key ' . $argument, change($tuple, $argument, [0], 'unexpected'), 'Invalid');
}
foreach (array_keys($state['approval']) as $key) {
    $invalid = $tuple;
    unset($invalid[1]['approval'][$key]);
    reject('missing approval field ' . $key, $invalid, 'Invalid');
}
reject('extra approval field', change($tuple, 1, ['approval', 'unexpected'], true), 'Invalid');
foreach ([null, false, 'approved', []] as $approval) {
    reject('malformed approval ' . get_debug_type($approval), change($tuple, 1, ['approval'], $approval), 'Invalid');
}
foreach ([[0, 'source_rev'], [1, 'revision'], [2, 'source_rev'], [1, 'approval', 'revision']] as $field) {
    $argument = array_shift($field);
    foreach ([0, -1, '1', 1.0, true, null, PHP_INT_MAX] as $value) {
        reject('revision field type and bounds ' . $argument . ':' . implode('.', $field)
            . ':' . get_debug_type($value), change($tuple, $argument, $field, $value), 'Invalid');
    }
}
foreach ([0, 1] as $argument) {
    foreach (['1', true, 1.0, 2] as $version) {
        reject('strict schema version ' . $argument, change($tuple, $argument, ['schema_version'], $version), 'Invalid');
    }
}
foreach ([[0, 'prev_release'], [1, 'prev_release'], [2, 'prev_release'], [1, 'approval', 'prev_release']] as $field) {
    $argument = array_shift($field);
    foreach ([null, 1, strtoupper(str_repeat('a', 40)), str_repeat('a', 39), $release . "\n"] as $value) {
        reject('strict release ' . $argument . ':' . implode('.', $field), change($tuple, $argument, $field, $value), 'Invalid');
    }
}
foreach ([null, 1, str_repeat('a', 39), strtoupper($release), $release . "\n"] as $invalidRelease) {
    $invalid = $tuple;
    $invalid[3] = $invalidRelease;
    reject('strict trusted successful release', $invalid, 'Invalid');
}
foreach ([[0, 'request_id'], [0, 'output_sha256'], [1, 'baseline_sha256'], [2, 'sha256'],
    [1, 'approval', 'output_sha256']] as $field) {
    $argument = array_shift($field);
    foreach ([null, 1, str_repeat('d', 63), str_repeat('D', 64), $sha . "\n"] as $value) {
        reject('strict hash ' . $argument . ':' . implode('.', $field), change($tuple, $argument, $field, $value), 'Invalid');
    }
}
foreach ([0, 2] as $argument) {
    foreach (['../includes/refresh-data.json', '/includes/refresh-data.json', 'includes/other.json', null] as $path) {
        reject('fixed export path ' . $argument, change($tuple, $argument, ['path'], $path), 'Invalid');
    }
    foreach ([null, [], false, '', str_repeat('x', 2000001)] as $value) {
        reject('strict bounded bytes ' . $argument, change($tuple, $argument, ['bytes'], $value), 'Invalid');
    }
}
foreach ([null, [], new stdClass()] as $serviceValue) {
    reject('state requires Pilot service map', change($tuple, 1, ['public_service'], $serviceValue), 'Invalid');
}
foreach ([null, [], str_repeat('n', 4001)] as $note) {
    reject('state requires bounded private note', change($tuple, 1, ['private_note'], $note), 'Invalid');
}
reject('wrong service', change($tuple, 1, ['service_id'], 'neon-flex'), 'Invalid');
foreach (['published', 'draft', true] as $status) {
    reject('request only requested', change($tuple, 0, ['status'], $status), 'Invalid');
}
reject('unknown current state status', change($tuple, 1, ['status'], 'published'), 'Invalid');
$draft = change(change($tuple, 1, ['status'], 'draft'), 1, ['approval'], null);
reject('unapproved current draft', $draft, 'Conflict');
reject('draft cannot retain approval', change($tuple, 1, ['status'], 'draft'), 'Invalid');
reject('stale request left after failed cancellation', change($draft, 1, ['revision'], 2), 'Conflict');
$newApproved = change(change($tuple, 1, ['revision'], 2), 1, ['approval', 'revision'], 2);
reject('stale request versus newly approved revision', $newApproved, 'Conflict');
reject('fresh export must match revision', change($tuple, 2, ['source_rev'], 2), 'Conflict');
reject('approval must match state revision', change($tuple, 1, ['approval', 'revision'], 2), 'Conflict');
$changedRequest = change($tuple, 0, ['source_rev'], 2);
$changedRequest[0]['request_id'] = hash('sha256', $release . "\n2\n" . $sha);
reject('well-formed request for another revision', $changedRequest, 'Conflict');
foreach ([[1, 'prev_release'], [2, 'prev_release'], [1, 'approval', 'prev_release']] as $field) {
    $argument = array_shift($field);
    reject('release mismatch ' . $argument . ':' . implode('.', $field),
        change($tuple, $argument, $field, $otherRelease), 'Conflict');
}
$oldRequest = change($tuple, 0, ['prev_release'], $otherRelease);
$oldRequest[0]['request_id'] = hash('sha256', $otherRelease . "\n1\n" . $sha);
reject('well-formed request for another base release', $oldRequest, 'Conflict');
$changedRelease = $tuple;
$changedRelease[3] = $otherRelease;
reject('successful release advanced', $changedRelease, 'Conflict');
reject('approval output hash binding', change($tuple, 1, ['approval', 'output_sha256'], str_repeat('d', 64)), 'Conflict');
reject('request byte tampering', change($tuple, 0, ['bytes'], $bytes . ' '), 'Invalid');
reject('export byte tampering', change($tuple, 2, ['bytes'], $bytes . ' '), 'Invalid');
reject('request hash tampering', change($tuple, 0, ['output_sha256'], str_repeat('d', 64)), 'Invalid');
reject('export hash tampering', change($tuple, 2, ['sha256'], str_repeat('d', 64)), 'Invalid');
reject('request id tampering', change($tuple, 0, ['request_id'], str_repeat('d', 64)), 'Invalid');
$extraNewline = hash('sha256', $release . "\n1\n" . $sha . "\n");
reject('id has canonical separators without trailing newline', change($tuple, 0, ['request_id'], $extraNewline), 'Invalid');
reject('rehashed tampered request cannot match fresh export', resign(change($tuple, 0, ['bytes'], $bytes . ' ')), 'Conflict');
$changedExport = change($tuple, 2, ['bytes'], $bytes . ' ');
$changedExport[2]['sha256'] = hash('sha256', $changedExport[2]['bytes']);
reject('internally consistent different export remains a conflict', $changedExport, 'Conflict');

echo $passed . ' PASS, ' . $failed . ' FAIL on PHP ' . PHP_VERSION . "\n";
exit($failed === 0 ? 0 : 1);
