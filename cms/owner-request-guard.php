<?php
declare(strict_types=1);

namespace KanCms;

/**
 * Pure validation of the private publication handoff. Never publishes or reads
 * storage. Caller must obtain Pilot::load() and Pilot::export() afresh under
 * the same outer lock used by the gateway and the sole publisher.
 */
final class OwnerRequestGuard
{
    private const PATH = 'includes/refresh-data.json';
    private const MAX_BYTES = 2000000;

    /**
     * All arguments are trusted server-side inputs, not client payloads or
     * cached adapter views. Mixed inputs make malformed records fail closed.
     * The safe receipt is descriptive, never an approval or permission token.
     */
    public static function validate(
        mixed $request,
        mixed $currentState,
        mixed $freshExport,
        mixed $successfulRelease
    ): array {
        if (!self::keys($request, [
            'schema_version', 'request_id', 'status', 'source_rev',
            'prev_release', 'output_sha256', 'path', 'bytes'
        ]) || !self::keys($currentState, [
            'schema_version', 'service_id', 'revision', 'status', 'prev_release',
            'baseline_sha256', 'public_service', 'private_note', 'approval'
        ]) || !self::keys($freshExport, ['path', 'bytes', 'sha256', 'source_rev', 'prev_release'])
            || !self::release($successfulRelease)) {
            return self::failure('Invalid');
        }

        if ($request['schema_version'] !== 1 || $request['status'] !== 'requested'
            || !self::revision($request['source_rev']) || !self::release($request['prev_release'])
            || !self::sha256($request['request_id']) || !self::sha256($request['output_sha256'])
            || $request['path'] !== self::PATH || !self::bytes($request['bytes'])
            || $freshExport['path'] !== self::PATH || !self::bytes($freshExport['bytes'])
            || !self::sha256($freshExport['sha256']) || !self::revision($freshExport['source_rev'])
            || !self::release($freshExport['prev_release'])
            || $currentState['schema_version'] !== 1 || $currentState['service_id'] !== 'neon-box'
            || !self::revision($currentState['revision']) || !self::release($currentState['prev_release'])
            || !self::sha256($currentState['baseline_sha256'])
            || !is_array($currentState['public_service']) || array_is_list($currentState['public_service'])
            || !is_string($currentState['private_note']) || strlen($currentState['private_note']) > 4000
            || !in_array($currentState['status'], ['draft', 'approved'], true)) {
            return self::failure('Invalid');
        }

        // A saved draft invalidates approval, including when an old request
        // survived a storage failure during its cancellation.
        if ($currentState['status'] === 'draft') {
            return self::failure($currentState['approval'] === null ? 'Conflict' : 'Invalid');
        }
        $approval = $currentState['approval'];
        if (!self::keys($approval, ['revision', 'prev_release', 'output_sha256'])
            || !self::revision($approval['revision']) || !self::release($approval['prev_release'])
            || !self::sha256($approval['output_sha256'])) {
            return self::failure('Invalid');
        }

        if (!hash_equals($request['output_sha256'], hash('sha256', $request['bytes']))
            || !hash_equals($freshExport['sha256'], hash('sha256', $freshExport['bytes']))) {
            return self::failure('Invalid');
        }
        $expectedId = hash('sha256', $request['prev_release'] . "\n"
            . $request['source_rev'] . "\n" . $request['output_sha256']);
        if (!hash_equals($expectedId, $request['request_id'])) {
            return self::failure('Invalid');
        }

        if ($currentState['revision'] !== $request['source_rev']
            || $freshExport['source_rev'] !== $request['source_rev']
            || $approval['revision'] !== $currentState['revision']
            || $request['prev_release'] !== $successfulRelease
            || $currentState['prev_release'] !== $successfulRelease
            || $freshExport['prev_release'] !== $successfulRelease
            || $approval['prev_release'] !== $successfulRelease
            || !hash_equals($approval['output_sha256'], $freshExport['sha256'])
            || !hash_equals($request['output_sha256'], $freshExport['sha256'])
            || $request['bytes'] !== $freshExport['bytes']) {
            return self::failure('Conflict');
        }

        return ['ok' => true, 'receipt' => [
            'schema_version' => 1,
            'request_id' => $request['request_id'],
            'source_rev' => $request['source_rev'],
            'prev_release' => $successfulRelease,
            'output_sha256' => $freshExport['sha256'],
            'path' => self::PATH
        ]];
    }

    private static function keys(mixed $value, array $expected): bool
    {
        if (!is_array($value) || count($value) !== count($expected)) return false;
        $actual = array_keys($value);
        sort($actual, SORT_STRING);
        sort($expected, SORT_STRING);
        return $actual === $expected;
    }

    private static function revision(mixed $value): bool
    {
        return is_int($value) && $value >= 1 && $value < PHP_INT_MAX;
    }

    private static function release(mixed $value): bool
    {
        return is_string($value) && preg_match('/\A[a-f0-9]{40}\z/', $value) === 1;
    }

    private static function sha256(mixed $value): bool
    {
        return is_string($value) && preg_match('/\A[a-f0-9]{64}\z/', $value) === 1;
    }

    private static function bytes(mixed $value): bool
    {
        return is_string($value) && $value !== '' && strlen($value) <= self::MAX_BYTES;
    }

    private static function failure(string $category): array
    {
        return ['ok' => false, 'category' => $category];
    }
}
