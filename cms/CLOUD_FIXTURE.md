# Cloud fixture: prototype to offline NEON-BOX pilot

This fixture connects the existing `createModel()` in
`tests/fixtures/cms-posting-prototype.html` to the existing `KanCms\Pilot` in
`cms/neon_box_pilot.php`. Neither original implementation is replaced. The new
`DraftAdapter` and test transport exercise draft persistence and review in a
synthetic cloud CLI process. They introduce no HTTP endpoint, login, browser
storage, upload facility or publisher. Nothing activates the public CMS.

## Files and contract

- `cms/neon_box_draft_adapter.php`: maps the prototype snapshot to the Pilot and
  holds a review receipt in adapter memory.
- `tests/fixtures/cms-neon-box-cloud.php`: synthetic CLI fixture using JSON-line
  requests and responses. Identity, expiry and CSRF context come from fixture
  constants, not request payloads.
- `tests/fixtures/cms-neon-box-bridge.cjs`: wraps the unchanged prototype model;
  transport is supplied by the test runner, without adding a browser API.
- `tests/cms-neon-box-cloud.cjs`: focused cross-language checks and temporary
  fixture cleanup.

Requests use `{action, payload}`. `load` takes an empty payload. `save` takes
`expected_revision` and `snapshot`, with exactly `fields`, `order`, `rights` and
`cover`. `preview` and `approve` take only `expected_revision`; callers cannot
provide an approval flag or review receipt. `load` and successful mutations
return `revision`, `status` and `snapshot`. Missing state has revision `0`,
status `empty` and a null snapshot. `export` exists only for fixture assertions;
the JavaScript bridge exposes no export method and its queue remains disabled.

## Draft mapping and media

Only kind `Layanan` maps to the fixed `neon-box` record. A draft title replaces
`name` and its summary replaces `intro`; the supplied baseline retains its
`symbol`, `body`, `options`, `guide` and optional SEO/detail fields. This is not
an article or project CMS.

The versioned snapshot is encoded in the Pilot's existing `private_note`, with
a total limit of 4,000 bytes. Fact text, provenance/source text, verification,
selected placeholder order and rights stay private. Sources remain literal
text and are never promoted to public links. Public text still passes the
Pilot's existing validator. Unknown schema keys, malformed stored metadata,
public/private mismatches and oversized metadata fail without becoming a new
saved revision.

The only fixture media IDs are `a`, `b` and `c`, mapped to synthetic approved
photo references. Selection and rights lists cannot contain duplicate or
unknown IDs; rights must belong to selected media and the cover must be selected.
Only the cover maps to the backend's single `image` field. An absent cover maps
to `image: null`, including an empty selection. Ordered media does not create a
public gallery, and no URLs, paths or uploaded files are accepted as media IDs.
These synthetic references must not be used as a live media allowlist.

Drafts can retain incomplete rights, a missing cover or an unverified fact.
Approval requires rights for every selected item, a cover when media is selected,
and explicit verification when fact text is nonempty. Editing fact or source in
the existing model clears its verification mark. Fact/source stay out of export
even when verified; marking a fact verified in a fixture establishes no real
world evidence.

## Save, reload and review

The bridge tracks the backend revision separately from the model's session
revision. Each successful save increments the backend revision and clears its
approval, including edits that affect only private metadata. Expected revisions
prevent stale saves from replacing a newer draft.
The bridge also refuses delayed replies from superseded operations and preserves
local edits made while a load is pending; an old approval reply cannot approve
a newer backend revision.
If the current operation receives a backend `Conflict`, the bridge clears local
preview/approval and reports `needsReload`, preserving fields and revisions until
reload. A late conflict from an older operation leaves newer confirmed state intact.

Reload reconstructs a fresh `createModel()` through its existing edit/select/
rights/cover methods and prepares a session draft. It restores content and media
choices, but no session preview or approval. The persisted backend status is
reported separately; it is not restored as a model approval.

Preview requires the current saved snapshot. The adapter issues an in-memory
receipt binding the backend revision, expected release, public service and
private snapshot. Approval requires that exact receipt object and rechecks the
stored metadata and media/fact conditions. Saving or restarting the adapter
invalidates the receipt; a new bridge session must preview again. The Pilot
then binds approval to the exact backend revision, deterministic public output
hash and expected release. A review receipt is content binding, never proof of
Owner authentication.

The fixture can assert the Pilot's sanitized export contract without writing
public files. Export contains only `path`, `bytes`, `sha256`, `source_rev` and
`prev_release`; private metadata does not enter its public JSON. Export never
sets a published/live status. Backend remains the sole integrator and publisher.

## Focused cloud verification

With Node.js and a PHP 8.3 CLI executable on `PATH`, run from the repository root:

```sh
node tests/cms-neon-box-cloud.cjs
```

If PHP needs an explicit executable path:

```sh
CMS_PHP_BIN=/absolute/path/to/php8.3 node tests/cms-neon-box-cloud.cjs
```

Pass exact case names after the script to run only those cases; unknown names fail
the run and unselected cases are counted as skipped. This avoids repeating the full
fixture suite for a narrow change.

`current-main-public-baseline-roundtrip` loads the checkout's public
`includes/refresh-data.json` read-only through CLI mode `public-baseline`.
Identity, release, draft edits and private notes remain synthetic. This checks
current service/photo-schema compatibility, save/reload and preservation of all
other public records; it does not read a hosting store or prove Owner authentication.

The runner uses synthetic data and precreated `0700` temporary directories
outside the checkout and public roots, then removes its private fixtures. Only
test names/counts/categories belong in retained evidence. Do not retain draft,
source, private-note or export payloads in logs or artifacts. The focused checks
cover create/edit/save/reload, stale revisions, review invalidation, media/fact
blockers and private-data exclusion. Cloud CLI results establish no hosting
authentication, Apache denial, hosting permission or public activation behavior.

## Decisions still required before any hosting activation

No hosting access or security change is authorized by this fixture work. The
Owner and Backend need these concrete decisions and sanitized facts:

1. **Owner access boundary and principal.** Identify a proven existing
   Owner-only boundary and the trusted server identity to configure as Owner.
   If none exists, approve a specific one-owner protection change and its scope.
   The Owner enters credentials directly in the hosting facility; no credential
   belongs in source, chat, request identity fields or logs. A valid mock
   `OwnerContext` is not a real login.
2. **Session and mutation policy.** Choose the server-side identity source,
   session expiry/logout policy and CSRF verification mechanism. The hosting
   adapter must derive identity, expiry and CSRF acceptance on the server and
   demonstrate anonymous, non-owner, expired-session and rejected-CSRF behavior.
3. **Exact private storage boundary.** Confirm account home and every domain or
   subdomain document root; select the canonical private directory, such as
   `<VERIFIED_ACCOUNT_HOME>/3dkan-private/cms/`, outside all of them. Approve any
   actual directory provisioning and the exact ownership/permission scope.
   The Pilot requires an existing non-symlink private directory with no group
   or other permissions; fixture checks do not prove hosting HTTP denial.
4. **Effective PHP filesystem access.** Confirm the hosting SAPI/runtime
   identity, directory ownership and filesystem restrictions for that location.
   Hosting selection `ea-php83` and healthy public-page smoke checks, as reported
   by the coordinating team, do not establish the CMS adapter's effective UID,
   private-path access or mutation behavior.
5. **Managed authentication and source checks.** Decide how server-managed
   protection configuration fits the existing source scanner and drift contract
   without weakening them or committing an authentication/password database.
   Decide the protected route scope before installing any future endpoint.

Backend must also supply the approved baseline and last successful release SHA,
and resolve live media mapping and the intended no-selection image behavior
before a real adapter is used. After the decisions above, actual-host tests and
one reviewed publish/rollback belong to Backend's authorized integration path.
This fixture remains a design and cloud-test deliverable; the CMS is not live.
