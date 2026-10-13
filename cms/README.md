# Offline NEON-BOX CMS backend pilot

This library is source preparation only. It is outside `public_html`, has no HTTP endpoint or admin route, and installs no account, authentication configuration, hosting directory or publisher. It needs PHP 8.1 or newer; the actual hosting PHP runtime is not verified.

## Supported boundary

Only the existing `neon-box` service record is editable. The baseline uses the website's current `includes/refresh-data.json` structure. Required public fields are `name`, `symbol`, `intro`, `body`, `options`, `guide`, and `image`; existing optional SEO/detail fields are allowed by the library's explicit validator. Existing approved photo references are retained; there is no media uploader.

An `OwnerContext` is a trusted **mock adapter boundary**, not a login system. Test identity, expiry and CSRF inputs must never be copied from HTTP request headers or form fields. A future hosting adapter must establish these facts server-side and pass its own anonymous/non-owner/expired/CSRF acceptance tests before any endpoint can be activated. Supplying a valid mock object is not proof of authentication on Rumahweb.

The configured private directory must already exist, be canonical, not be a symlink, be outside all supplied public document roots, and satisfy the library's restrictive directory checks. Tests provision it only under GitHub Actions `RUNNER_TEMP`; the library does not provision a hosting account directory.

## Revision, persistence and export

- `load` requires the configured owner and a current context.
- `save` also requires CSRF validation and an expected revision. The initial expected revision is zero. A successful save increments the revision, sets draft status and invalidates approval.
- `approve` binds the current revision, exact deterministic public output hash and expected successful release.
- `export` requires the same approved revision and current release, plus owner/CSRF checks. It returns only `path`, `bytes`, `sha256`, `source_rev`, and `prev_release`.
- The public path is fixed to `includes/refresh-data.json`. The exporter clones the supplied public baseline and replaces only the NEON-BOX record. Other services and top-level data remain unchanged. Private notes and approval identity never enter output.
- Unauthorized access is refused before private state reads/writes. Invalid content and stored public state that no longer matches its approval fail with category-only exceptions. Hashes provide integrity checks; they do not authenticate a malicious party already able to rewrite the entire private store.
- A lock and expected revision protect cooperating writers. A complete temporary file on the same filesystem is flushed before replacement; revision advancement follows persistence. Offline tests cover save/reload, stale revisions and a real two-process race where the cloud runtime supports it. Power-loss durability, adversarial filesystem races, Apache exposure and hosting permissions are not established by those tests.

No network, repository token, FTPS credential, storage service or second production writer is introduced. The authorized publisher still reviews sanitized public JSON in GitHub and uses the existing guarded writer. Do not mark an item published from an export alone.

## Cloud test evidence

The dedicated PR workflow checks the exact checkout SHA, library/test/document bytes and unchanged `public_html`, then executes PHP CLI with synthetic data in an isolated temporary private directory. It publishes only redacted counts/test names/categories. Draft files, exports and private sentinel values are excluded from artifacts and logs. The test runtime is separate from the unverified hosting runtime.

The tests are not an application authentication audit or a real CMS deployment. They exercise mocked authorization, server-side data validation, revision/approval invalidation, deterministic export, persistence, tamper refusal and filesystem boundaries in the cloud CLI environment.

## Read-only hosting facts and next decisions

Pinned source [root routing rules](https://github.com/erwin071996/rumahwebhous/blob/059a4414b0a7bbc48608246d79b5703ba6b96854/public_html/.htaccess) enforce the established HTTPS/www hostname, deny public `includes` access and preserve PHP routing. They do not prove owner-only CMS authentication. Generated service links use the verified canonical /layanan/<service> routes. No CMS auth or password files were inspected. Available connected tools did not expose sanitized cPanel account-home/PHP metadata; no laptop or hosting configuration was read or changed.

Before activation, the Owner needs a concrete decision based on sanitized metadata:

1. Prove the exact account home, all domain document roots, PHP version/runtime identity and effective filesystem restrictions.
2. Prove a suitable existing owner-only access boundary. If absent, authorize a specific one-owner hosting protection change; credentials are provided directly by the Owner through the hosting facility, not put in PHP, public Git, logs or chat.
3. Verify the proposed private location `<VERIFIED_ACCOUNT_HOME>/3dkan-private/cms/` against those facts. Any actual provisioning, ownership/permission or access-policy change needs explicit scope approval before execution.
4. Reconcile any server-managed authentication configuration with the source scanner and drift contract without weakening their protection or tracking a password database.
5. Only then test actual host authorization, private HTTP denial, save/reload and a single reviewed public publish/rollback.

No new blanket permission is needed for this offline implementation or ordinary already-authorized public publishing. The required future approvals apply only to the concrete persistent access/storage/security changes above.

PHP reference: [advisory flock](https://www.php.net/manual/en/function.flock.php), [fsync](https://www.php.net/manual/en/function.fsync.php), and [array_is_list](https://www.php.net/manual/en/function.array-is-list.php). The lock protects cooperating callers; cloud results do not establish every hosting SAPI/filesystem behavior.
