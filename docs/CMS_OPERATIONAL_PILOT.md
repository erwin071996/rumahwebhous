# Minimal operational CMS pilot — review proposal

Status: PROPOSED ONLY. No CMS authentication, private storage, endpoint, persistent writer, credentials, or security settings are activated by this document.

## Verified starting point

- Public source and deployment are maintained in `erwin071996/rumahwebhous`. The existing reviewed Git → GitHub Actions → guarded FTPS workflow is the sole production writer. It retains drift refusal, fresh backup, readback, exact HTTP checks, rollback, and release-state advancement last.
- Successful public SEO release `cb207d9745e41357dcc6728f8e71e021091966b3` is established. Source-only prototype PR #13 merged as `059a4414b0a7bbc48608246d79b5703ba6b96854`; its four additions are outside `public_html`, whose bytes remain unchanged.
- The prototype starts blank, keeps synthetic drafts only in RAM, and has disabled unconnected export. Exact-head checks passed 36 Node cases and nine native Chromium cases; parent reviewed 1280/390 screenshots and the matching artifact digest.
- Public `seo.php`, `includes/refresh-data.json`, `content.php`, `includes/content-index.json`, and `sitemap.php` are not evidence of authenticated private editing. Existing CMS authentication, actual account home, PHP identity, private storage permissions, and persistence remain UNVERIFIED.

## Small first release

One owner edits the existing NEON-BOX service privately. No article CRUD, project CRUD, new media upload, account-management UI, automatic publisher, repository token, or FTPS credential in PHP is included.

Editor code may be proposed at `public_html/cms/` only after an owner-only access boundary is selected and proven. Private data never belongs in that directory. Do not expose the editor, draft reads, saves, or export before the access gate passes. Missing configuration must fail closed.

## Owner access using hosting facilities

1. Read only sanitized hosting metadata to establish the exact Home Directory, all relevant domain document roots, PHP runtime identity, effective `open_basedir`, and whether owner-only web protection already exists. Do not read passwords, private payloads, or sensitive runtime config.
2. If existing protection is proven, verify it covers every editor, save, draft-read and export route; anonymous and non-owner requests must be rejected server-side. If an application session is actually introduced, expired sessions must also be rejected. A cPanel login alone does not protect a CMS URL.
3. If no suitable protection exists, the concrete proposed facility is cPanel Directory Privacy for the CMS code directory, with one owner access identity. Activation/user creation changes authentication configuration and needs explicit security-scope approval before implementation. Availability is not evidence of active protection. Never copy cPanel/FTP credentials into PHP.
4. PHP must use only an identity actually enforced by the web server or a separately approved authentication boundary. Client headers or form fields must not establish identity. Test this in the real PHP handler.
5. Mutations require server-side authorization, CSRF protection and bounded requests. Directory Privacy does not itself imply PHP application sessions. If a session mechanism is needed and approved, it uses Secure/HttpOnly cookies, explicit expiry and an appropriate SameSite policy; configuration must be verified rather than assumed.
6. Before implementation, reconcile any Directory Privacy-generated authentication configuration with the existing scanner and deployment drift contract. Never track a password database or introduce a blanket runtime/credential exemption. Changes to this protected server-owned boundary need their own reviewed contract.

cPanel documents [Home Directory information](https://docs.cpanel.net/cpanel/the-cpanel-interface/the-cpanel-interface/), [domain document roots](https://docs.cpanel.net/cpanel/domains/domains/), and that [Directory Privacy](https://docs.cpanel.net/cpanel/files/directory-privacy/) changes `.htaccess`/`.htpasswd` and requires authorized users. Its protection applies to web access; local and FTP/SFTP access have separate permissions.

## Concrete private storage proposal

Proposed path rule: `<VERIFIED_ACCOUNT_HOME>/3dkan-private/cms/`. The token is a placeholder, not a discovered account path.

After approved provisioning, `realpath(storage)` must exist, be contained in the verified account home, and be outside every actual document root. It must have no public Alias or symlink exposure. Verify storage owner/group against the actual PHP runtime identity, traversal/read/write ability and effective `open_basedir` without loosening them. If this location is unavailable, stop and present the required change; do not fall back to a public directory or `noindex`.

Suggested private subdirectories are `drafts/`, `revisions/`, `approvals/`, `evidence/`, `exports/`, and `backups/`. They contain private editorial records only and never enter public Git, PRs, logs or GitHub artifacts. The existing deployment-state file is not CMS draft storage.

A proposed save obtains a per-item lock, validates the expected revision, writes a complete temporary file on the same filesystem, and replaces the committed revision only after successful persistence. Stale revisions produce a conflict. Interrupted/concurrent saves must preserve a complete prior or new committed revision. These are implementation and test requirements, not completed behavior. Private backup restore must be tested at a private location.

[PHP realpath](https://www.php.net/manual/en/function.realpath.php), [PHP filesystem security](https://www.php.net/manual/en/security.filesystem.php), [open_basedir](https://www.php.net/manual/en/ini.core.php#ini.open-basedir), and [Apache URL mapping](https://httpd.apache.org/docs/2.4/urlmapping.html) support these checks. A path outside DocumentRoot alone is insufficient if aliases or symlinks expose it.

## Private revision and approval contract

A private item has a stable ID, schema version, revision, status, factual source references and approval bound to the current immutable revision. Suggested statuses are draft → in review → approved → exported → published, with archive available later.

Editing public output, output-affecting evidence, or media invalidates approval. Approval includes the expected successful release baseline and exact public output hash. A changed baseline requires renewed review. No material, dimensions, electrical power, warranty, price or completion date may be inferred from a photograph. Private approval identities and evidence remain private.

## Exact public export allowlist

The initial pilot can change only `includes/refresh-data.json`, and only the NEON-BOX record. All other service values and unrelated data remain unchanged.

Allowed required service fields: `name`, `symbol`, `intro`, `body`, `options: string[]`, `guide: string`, `image: string|null`. Preserve an existing approved photo ID; new media publication is excluded from this pilot.

Allowed existing optional SEO fields: `seo_title`, `seo_description`, `detail_heading`, and `detail_sections[{id, heading, paragraphs:string[], links:[{label,href}]}]`.

Validate server-side types, limits, block content and safe URLs against the existing service contract. Reject unknown update fields, other services, raw HTML/JS, arbitrary paths, traversal and unauthorized media IDs. Preserve the surrounding data structure from the current verified baseline.

Export only public content. Exclude drafts, private notes/evidence URLs, original filenames, customer briefs, owner/session information, approval identities, credentials, audit records and backups.

## Manual publishing through the existing single writer

1. The authenticated owner reviews a private preview, approves the current revision and downloads the sanitized JSON candidate.
2. A private export ledger binds `source_rev`, `prev_release`, the fixed output path, byte count, SHA-256 and approval. Public PR text may include safe revision/hash/baseline metadata; private evidence stays private. Hashes prove integrity, not identity or approval. A manifest cannot expand the fixed output allowlist.
3. An already authorized publisher uses their existing personal GitHub UI session to upload only the approved JSON on a branch and open a PR. PHP receives no GitHub or FTPS token. The pipeline neither fetches the private store nor accepts a CMS API submission.
4. Review verifies exact bytes/hash, NEON-BOX-only diff, unchanged other services and current successful baseline. Existing source, schema, fact, privacy, HTTP and rollback checks run without weakened assertions.
5. Merge uses the existing writer and its fresh backup, drift refusal, readback, semantic HTTPS checks and rollback. The private ledger becomes published only after verified success and records the release commit. Identical already-published bytes are a no-op; stale baselines conflict. Deployment failure leaves the private draft/export available for review.
6. Public rollback remains the existing writer's responsibility. Private editorial backup and public rollback bundles remain separate.

## Activation acceptance and actual approval boundary

Before activation, prove in the real hosting environment:

- Anonymous and non-owner requests cannot read or mutate private content. If application sessions exist, expired or revoked sessions are rejected. CSRF mutation attempts are rejected, and no unintended editor/save/export route bypasses protection.
- Drafts, revisions, evidence, originals, backups and private ledgers cannot be fetched publicly.
- Forbidden fields/services/paths, malformed JSON, traversal and oversized requests are rejected server-side.
- Save/reload works; concurrent, stale and interrupted writes preserve complete committed revisions.
- Edits, changed baseline and altered export bytes invalidate approval.
- A synthetic private sentinel never appears in exports, logs, errors, PR material or public artifacts.
- One approved pilot publish and rollback pass the existing writer and state-last checks.

Preparing this proposal and reading sanitized metadata need no new general publishing permission. Explicit approval is required only if implementing a not-yet-authorized persistent access boundary, owner identity/credentials, private storage writer/provisioning, or changing authentication, ownership, permissions, `open_basedir` or web mapping. Present the exact proposed changes after the read-only facts are established. Never create secrets while requesting approval and never claim the CMS operational before these gates pass.

## Current handoff

Merged prototype source is review evidence, not an admin installation. Operational work starts with the sanitized hosting facts and the concrete access/storage decision above. Production publishing remains the existing authorized process; no second writer is proposed.
