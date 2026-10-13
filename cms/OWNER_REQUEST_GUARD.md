# Private publication request guard

`KanCms\OwnerRequestGuard::validate($request, $currentState, $freshExport, $successfulRelease)`
validates the private Neon Box handoff created by `OwnerGateway`. It performs no
I/O, authentication, locking, queue creation, acknowledgement, or publication.
It has no dependency on the gateway and adds no endpoint.

## Input contract

All four arguments come from the server. None may be taken from a browser,
request body, cached review receipt, or `DraftAdapter::load()` UI view.

| Argument | Source and exact keys |
| --- | --- |
| `request` | Decode the bounded private request file: `schema_version`, `request_id`, `status`, `source_rev`, `prev_release`, `output_sha256`, `path`, `bytes`. |
| `currentState` | A fresh, validated full `Pilot::load()` result: `schema_version`, `service_id`, `revision`, `status`, `prev_release`, `baseline_sha256`, `public_service`, `private_note`, `approval`. |
| `freshExport` | A fresh `Pilot::export()` result: `path`, `bytes`, `sha256`, `source_rev`, `prev_release`. |
| `successfulRelease` | The trusted current successful release identifier, a lowercase 40-character SHA from the existing publisher. |

The state must be approved. Its approval has exactly `revision`, `prev_release`,
and `output_sha256`. The guard requires schema version integer `1`, positive
integer revisions below `PHP_INT_MAX`, lowercase SHA values, status
`requested`, and path `includes/refresh-data.json`. It rejects missing or extra
envelope/approval keys and scalar coercion. Export/request byte strings must be
nonempty and at most 2,000,000 bytes; retain the gateway's separate bound on the
encoded private request file when reading it.

Pilot remains responsible for validating the baseline, service content,
allowed media, and private metadata. The guard does not reproduce that content
validator. Passing a hand-built state or cached export instead of fresh Pilot
results does not satisfy this contract, even if its hashes agree.

The request ID is exactly:

```php
hash('sha256', $prevRelease . "\n" . $sourceRevision . "\n" . $outputSha256)
```

There is no trailing newline in the ID input. Request, state, approval, and fresh
export must agree on the revision and release. Approval, request, and export
hashes must agree. The guard hashes both byte strings independently and also
requires exact byte equality with the fresh export. An old request cannot pass
after a newer draft is saved, including when deleting that old request failed.

## Caller locking and consumption

Only Backend's existing single publisher may consume a matched handoff. Before
consumption, the caller must hold the same outer exclusive lock that the gateway
uses for mutations (`.owner-gateway.lock`) and maintain its private-root and
file-identity protections. Acquire the outer gateway lock before entering Pilot
so every participant follows the same gateway-to-Pilot lock order. Direct Pilot
writers must participate in that outer lock too. Pilot's internal lock protects each call separately; it does not make
multiple `load()`/`export()` calls atomic as a group.

Inside that outer lock, obtain the trusted successful release, decode the
private request, call `Pilot::load()` again, and call `Pilot::export()` for the
current state's revision and trusted successful release. Then call the guard
before marking or consuming the request. Stop on missing state, a Pilot
exception, or any rejected result. Preserve the publisher's separate release
serialization/check so the successful release cannot change between validation
and the actual release operation. Never reuse a guard result after releasing
the lock or retrying a publication; read and validate everything again.

This helper cannot establish lock ownership, provenance, an authenticated
Owner session, or a successful deployment. Authentication, session/CSRF and
review checks remain with the gateway and the existing trusted boundary. A
request descriptor or successful guard result alone never authorizes publishing.
No integration, workflow, gateway mutation, or deployment is performed by these
three files.

## Result

Accepted inputs return `['ok' => true, 'receipt' => ...]`. The receipt contains
only `schema_version`, `request_id`, `source_rev`, `prev_release`,
`output_sha256`, and `path`; it omits content bytes, public service data, private
notes, and identity/session information. It is a descriptor, not a token.

Rejected inputs return only `['ok' => false, 'category' => 'Invalid']` for a
malformed record or damaged internal hash/ID, or category `Conflict` for a
well-formed stale/unapproved/mismatched tuple. Do not log private input records.

Validation is deterministic and has no side effects. Repeating it does not
enqueue or publish twice, but it provides no delivery idempotency mechanism;
the sole publisher still owns request acknowledgement and retry decisions.

## Focused synthetic check

```sh
php tests/cms-owner-request-guard.php
```

The standalone test obtains its synthetic approved tuple from the actual
`Pilot::save()`, `approve()`, `load()`, and `export()` APIs in disposable temporary
directories, then removes that fixture. It exercises deterministic validation,
safe output, strict record types/keys, approval binding, stale revisions,
release mismatch, fixed output path, and byte/hash/ID tampering. It touches no
real private runtime storage, HTTP endpoint, queue, or release. An optional first
CLI argument names the existing Pilot source when checking the patch outside a
full repository checkout. Use PHP 8.3 for the
release verification; another runtime is diagnostic only.
