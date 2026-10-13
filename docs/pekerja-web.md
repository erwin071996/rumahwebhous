# Pekerja Web dashboard — private runtime feed

The public source contains only dashboard code, validation utilities, focused
synthetic tests and an empty `status.example.json`. The example has no source
clock, task references, conversation links, evidence links, release SHA or
actual activity. It is never a fallback for the running application.

The real application requests `/pekerja-web/status.json` on the same 3DKan
hostname. That file is runtime data on protected hosting, not a Git source file.
Missing, unreadable, malformed or stale runtime data displays unknown and stops
work animation. The example is not the final deliverable: the integrator must
provide a real, evidence-backed private feed after the access gate passes.

## Access gate and publisher ownership

Do not publish page or feed until server access protects the directory and all
its descendants. `noindex`, hidden URLs and client-side code are not auth.
Existing cPanel Directory Privacy is the proposed server boundary; its
[documentation](https://docs.cpanel.net/cpanel/files/directory-privacy/) describes
inherited directory protection and server-managed access/password files.
Parent handles protection authorization and the Owner's manual account setup.
Backend remains the sole integrator using the existing authorized publisher,
with CMS consulted to avoid duplicate auth or unnecessary accounts.

Anonymous GET for the directory, `index.html`, `status.json`, `dashboard.css`
and `dashboard.js` must end in 401 on www and non-www HTTPS hosts. HTTP must
redirect to HTTPS before a challenge; the homepage must remain public. Run
`python3 scripts/check_worker_privacy.py` before publication and afterward.
This checker prints no response bodies and accepts no credentials. Passing it
proves only anonymous denial; authorized-user roster and Owner login require
separate verification. Unknown results, 404, a public 200 or failed Owner login
keep publication blocked.

No access/password file is included in this source. Never overwrite, mirror,
fetch or include managed protection/password data in Git or public backups.
Review the publisher's exact touched paths and retain server protection.

## Private feed publication contract

The browser has no write endpoint. Source code may go through a reviewed PR,
but actual reports must never enter Git history, PR bodies, test fixtures,
public logs or artifacts. The directory's ignore rules exclude `status.json`
and private JSON; real input must also remain outside the repository checkout.
The validator only reads a chosen file and prints a category-level result:

```sh
python3 scripts/validate_worker_status.py --check public_html/pekerja-web/status.example.json
python3 scripts/validate_worker_status.py --check "$TASK_PRIVATE_FEED_INPUT"
```

The current publisher deploys tracked Git changes. It does not already provide
an untracked private-feed input channel. Backend must add a narrowly scoped
private overlay to that same authorized publisher before real updates can be
claimed available; do not introduce another writer, service token or account.
The overlay contract is:

1. Accept a curated private input outside Git through an already authorized
   private handoff. Validate it without printing its content or changing source
   timestamps. Refuse publication until anonymous gate and Owner login pass.
2. Allow only the runtime destination `pekerja-web/status.json`; exclude access,
   password and unrelated files. Keep previous private bytes in memory or
   explicitly private storage for rollback, never the existing public report
   artifact tree. Logs must omit input, output and private operational text.
3. Write through the existing publisher/transport, compare previous content for
   drift, verify readback and prefer atomic replacement in the same protected
   directory where supported. On failure retain or restore the prior private
   feed; a missing/invalid feed remains unknown in the UI. Do not change the
   Git-backed successful release commit for a report-only update.
4. Publish only after a new evidence-backed report arrives. Display polling is
   every 3 seconds while visible; it is not a running task collector. No real
   3-second source API or always-running collector is supplied by this change.

Protect the private runtime feed from later source synchronization: it is not
tracked, must not be purged or imported into Git, and is outside generated route
inputs. The existing fixed-route generator writes named outputs rather than
purging arbitrary folders. This directory remains outside the route registry
and sitemap. The current publisher adds/modifies tracked files without a server
mirror; the integrator must preserve that behavior and managed runtime files.
No SharedBrand, CMS or existing deploy workflow is changed in this draft.

## Status and checks

`working` needs fresh evidence of actual execution; `inProgress` alone is not
proof. Awaiting approval is held/blocked. `done` describes the stated milestone,
not deployment. Source, test and live evidence remain distinct. Null source time
requires all-unknown empty status. Evidence older than 15 minutes becomes unknown.
Do not restamp a source timestamp just because the UI refreshed or a check ran.
A protected site can be available all day without agents being monitored all day.

```sh
python3 -m unittest discover -s tests -p 'test_worker_*.py' -v
node --test tests/worker-dashboard.test.cjs
```

These are focused synthetic tests for this dashboard, feed validation and
anonymous-check request handling. They do not prove live protection, successful
Owner login, actual activity or another team's QA results.
