<?php
declare(strict_types=1);

namespace KanCms;

require_once __DIR__ . '/neon_box_pilot.php';

/** A review receipt is content binding, never authentication or publication. */
final class DraftReview
{
    public function __construct(
        public readonly int $revision,
        public readonly string $fingerprint
    ) {}
}

/**
 * Offline bridge for the existing prototype and Pilot. No HTTP/session/publisher.
 * Caller supplies a trusted context, baseline, photo map and successful release.
 * Private editorial metadata uses Pilot's existing private_note field.
 */
final class DraftAdapter
{
    private ?DraftReview $issuedReview = null;

    public function __construct(
        private readonly Pilot $pilot,
        private readonly array $baselineService,
        private readonly array $photoMap,
        private readonly string $currentRelease
    ) {
        if (count($photoMap) < 1 || count($photoMap) > 3
            || array_diff(array_keys($photoMap), ['a', 'b', 'c']) !== []) throw new Invalid();
        if (count(array_unique(array_values($photoMap), SORT_REGULAR)) !== count($photoMap)
            || preg_match('/\A[a-f0-9]{40}\z/', $currentRelease) !== 1) {
            throw new Invalid();
        }
        foreach ($photoMap as $id) {
            if (!is_string($id) || $id === '') throw new Invalid();
        }
    }

    public function load(OwnerContext $ctx, int $now): array
    {
        $state = $this->state($ctx, $now);
        return $state === null
            ? ['revision' => 0, 'status' => 'empty', 'snapshot' => null]
            : $this->view($state);
    }

    public function save(OwnerContext $ctx, int $now, int $expectedRevision, array $snapshot): array
    {
        $current = $this->state($ctx, $now);
        if (($current['revision'] ?? 0) !== $expectedRevision) throw new Conflict();
        if ($current !== null) $this->view($current);
        $snapshot = $this->normalize($snapshot);
        $note = self::encode(['schema_version' => 1, 'snapshot' => $snapshot]);
        if (strlen($note) > 4000) throw new Invalid();
        $state = $this->pilot->save($ctx, $now, $expectedRevision,
            $this->service($snapshot), $this->currentRelease, $note);
        $this->issuedReview = null;
        return $this->view($state);
    }

    public function review(OwnerContext $ctx, int $now, int $expectedRevision): DraftReview
    {
        $state = $this->current($ctx, $now, $expectedRevision);
        // Decode/check the stored private metadata as well as the public content.
        $this->view($state);
        return $this->issuedReview = new DraftReview($state['revision'], self::fingerprint($state));
    }

    public function approve(OwnerContext $ctx, int $now, int $expectedRevision, ?DraftReview $review): array
    {
        $state = $this->current($ctx, $now, $expectedRevision);
        if ($review === null || $review !== $this->issuedReview
            || $review->revision !== $state['revision']
            || !hash_equals($review->fingerprint, self::fingerprint($state))) {
            throw new Conflict();
        }
        $snapshot = $this->view($state)['snapshot'];
        if (($snapshot['order'] !== [] && $snapshot['cover'] === null)
            || $snapshot['rights'] !== $snapshot['order']
            || (trim($snapshot['fields']['fact']) !== '' && !$snapshot['fields']['verified'])) {
            throw new Invalid();
        }
        return $this->view($this->pilot->approve($ctx, $now, $expectedRevision, $this->currentRelease));
    }

    private function state(OwnerContext $ctx, int $now): ?array
    {
        $state = $this->pilot->load($ctx, $now);
        if ($state !== null && $state['prev_release'] !== $this->currentRelease) throw new Conflict();
        return $state;
    }

    private function current(OwnerContext $ctx, int $now, int $expectedRevision): array
    {
        $state = $this->state($ctx, $now);
        if ($state === null || $state['revision'] !== $expectedRevision) throw new Conflict();
        return $state;
    }

    private function view(array $state): array
    {
        try {
            $note = json_decode($state['private_note'], true, 16, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new Invalid();
        }
        if (!is_array($note)) throw new Invalid();
        self::keys($note, ['schema_version', 'snapshot']);
        if ($note['schema_version'] !== 1 || !is_array($note['snapshot'])) throw new Invalid();
        $snapshot = $this->normalize($note['snapshot']);
        if ($this->service($snapshot) != $state['public_service']) throw new Invalid();
        return ['revision' => $state['revision'], 'status' => $state['status'], 'snapshot' => $snapshot];
    }

    private function service(array $snapshot): array
    {
        $service = $this->baselineService;
        $service['name'] = $snapshot['fields']['title'];
        $service['intro'] = $snapshot['fields']['summary'];
        $service['image'] = $snapshot['cover'] === null ? null : $this->photoMap[$snapshot['cover']];
        return $service;
    }

    private function normalize(array $snapshot): array
    {
        self::keys($snapshot, ['fields', 'order', 'rights', 'cover']);
        if (!is_array($snapshot['fields'])) throw new Invalid();
        $fields = $snapshot['fields'];
        self::keys($fields, ['kind', 'title', 'summary', 'fact', 'source', 'verified']);
        if ($fields['kind'] !== 'Layanan' || !is_bool($fields['verified'])) throw new Invalid();
        $normalizedFields = ['kind' => 'Layanan'];
        foreach (['title' => 120, 'summary' => 500, 'fact' => 2000, 'source' => 500] as $key => $max) {
            $text = $fields[$key];
            if (!is_string($text) || strlen($text) > $max || preg_match('//u', $text) !== 1
                || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', $text) === 1) throw new Invalid();
            $normalizedFields[$key] = $text;
        }
        $normalizedFields['verified'] = $fields['verified'];
        foreach (['order', 'rights'] as $key) {
            $list = $snapshot[$key];
            if (!is_array($list) || !array_is_list($list) || count($list) > 3) throw new Invalid();
            $seen = [];
            foreach ($list as $id) {
                if (!is_string($id) || !array_key_exists($id, $this->photoMap) || isset($seen[$id])) throw new Invalid();
                $seen[$id] = true;
            }
        }
        foreach ($snapshot['rights'] as $id) {
            if (!in_array($id, $snapshot['order'], true)) throw new Invalid();
        }
        $cover = $snapshot['cover'];
        if ($cover !== null && (!is_string($cover) || !in_array($cover, $snapshot['order'], true))) throw new Invalid();
        return [
            'fields' => $normalizedFields,
            'order' => $snapshot['order'],
            'rights' => array_values(array_filter($snapshot['order'], fn($id) => in_array($id, $snapshot['rights'], true))),
            'cover' => $cover
        ];
    }

    private static function keys(array $value, array $expected): void
    {
        $keys = array_keys($value);
        sort($keys, SORT_STRING);
        sort($expected, SORT_STRING);
        if ($keys !== $expected) throw new Invalid();
    }

    private static function encode(array $value): string
    {
        try {
            return json_encode($value, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        } catch (\JsonException $error) {
            throw new Invalid();
        }
    }

    private static function fingerprint(array $state): string
    {
        return hash('sha256', self::encode([
            $state['revision'], $state['prev_release'], $state['public_service'], $state['private_note']
        ]));
    }
}
