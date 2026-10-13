"use strict";

// Cloud CLI integration only: synthetic private drafts, no HTTP endpoint/login/publisher.
// Output contains fixed test names and redacted categories; never dump fixture replies.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");
const readline = require("node:readline");
const {spawn} = require("node:child_process");
const {createCloudModel} = require("./fixtures/cms-neon-box-bridge.cjs");

const repo = fs.realpathSync(path.resolve(__dirname, ".."));
const fixture = path.join(__dirname, "fixtures/cms-neon-box-cloud.php");
const html = fs.readFileSync(path.join(__dirname, "fixtures/cms-posting-prototype.html"), "utf8");
const script = html.match(/<script id="cms-prototype-js">([\s\S]*?)<\/script>/);
if (!script) throw new Error("PrototypeBoundary");
let sideEffects = 0;
function forbidden() { sideEffects++; throw new Error("PrototypeSideEffect"); }
const context = {
    module: {exports: {}}, fetch: forbidden, XMLHttpRequest: forbidden, WebSocket: forbidden,
    localStorage: new Proxy({}, {get: forbidden, set: forbidden}),
    sessionStorage: new Proxy({}, {get: forbidden, set: forbidden}),
    navigator: {sendBeacon: forbidden},
};
vm.runInNewContext(script[1], context, {timeout: 1000});
const {createModel} = context.module.exports;
const clone = value => JSON.parse(JSON.stringify(value));
const snapshot = model => {
    const {fields, order, rights, cover} = model.view();
    return clone({fields, order, rights: [...rights].sort(), cover});
};
const canonicalSnapshot = value => ({...clone(value), rights: [...value.rights].sort()});
const privateFact = "SYNTHETIC_PRIVATE_FACT_DO_NOT_EXPORT";
const privateSource = "SYNTHETIC_PRIVATE_SOURCE_DO_NOT_EXPORT";
const release = "1".repeat(40);
const modes = new Set(["owner", "anonymous", "other", "expired", "csrf-missing", "next-release"]);
let temporaryRoot, runner, sequence = 0;
const processes = new Set();
const results = [];
const selectedCases = process.argv.slice(2);
let skipped = 0;

function inside(candidate, root) {
    return candidate === root || candidate.startsWith(root + path.sep);
}
function setup() {
    runner = fs.realpathSync(process.env.RUNNER_TEMP || os.tmpdir());
    if (inside(runner, repo)) throw new Error("TemporaryBoundary");
    temporaryRoot = fs.mkdtempSync(path.join(runner, "cms-neon-box-cloud-"));
    fs.chmodSync(temporaryRoot, 0o700);
    assert.equal(fs.realpathSync(temporaryRoot), temporaryRoot);
    assert.equal(fs.statSync(temporaryRoot).mode & 0o777, 0o700);
    assert(!inside(temporaryRoot, repo));
}
function privateRoot() {
    const root = path.join(temporaryRoot, "case-" + (++sequence));
    fs.mkdirSync(root, {mode: 0o700});
    fs.chmodSync(root, 0o700);
    return root;
}
function transport(mode = "owner", root = privateRoot()) {
    assert(modes.has(mode));
    assert(inside(root, temporaryRoot) && root !== temporaryRoot);
    const args = process.env.CMS_PHP_ARGS_JSON ? JSON.parse(process.env.CMS_PHP_ARGS_JSON) : [];
    assert(Array.isArray(args) && args.every(arg => typeof arg === "string"));
    const child = spawn(process.env.CMS_PHP_BIN || "php", [...args, fixture, mode], {
        cwd: repo,
        env: {PATH: process.env.PATH, RUNNER_TEMP: temporaryRoot, CMS_TEST_ROOT: root},
        stdio: ["pipe", "pipe", "pipe"],
    });
    processes.add(child);
    let pending = null, failure = null, tail = Promise.resolve();
    function fail(category) {
        failure = new Error(category);
        if (pending) {
            clearTimeout(pending.timer);
            pending.reject(failure);
            pending = null;
        }
    }
    child.once("error", () => fail("FixtureRuntime"));
    child.once("exit", () => {
        processes.delete(child);
        fail("FixtureExit");
    });
    // PHP warnings must fail the test without placing private text or paths in logs.
    child.stderr.on("data", () => fail("FixtureStderr"));
    child.stdin.on("error", () => fail("FixtureInput"));
    const lines = readline.createInterface({input: child.stdout});
    lines.on("line", line => {
        if (!pending) { fail("FixtureProtocol"); return; }
        let reply;
        try { reply = JSON.parse(line); }
        catch { fail("FixtureProtocol"); return; }
        if (!reply || typeof reply.ok !== "boolean") { fail("FixtureProtocol"); return; }
        const current = pending;
        pending = null;
        clearTimeout(current.timer);
        current.resolve(reply);
    });
    function raw(envelope) {
        const result = tail.then(() => new Promise((resolve, reject) => {
            if (failure) { reject(failure); return; }
            const timer = setTimeout(() => {
                fail("FixtureTimeout");
                child.kill();
            }, 15000);
            pending = {resolve, reject, timer};
            child.stdin.write(JSON.stringify(envelope) + "\n", error => {
                if (error) fail("FixtureInput");
            });
        }));
        tail = result.catch(() => {});
        return result;
    }
    const request = (action, payload) => raw({action, payload});
    request.raw = raw;
    request.root = root;
    request.close = async () => {
        if (child.exitCode !== null || child.signalCode !== null) return;
        await new Promise(resolve => {
            const timer = setTimeout(() => { child.kill(); resolve(); }, 1500);
            child.once("exit", () => { clearTimeout(timer); resolve(); });
            child.stdin.end();
        });
        lines.close();
    };
    return request;
}
async function check(name, action) {
    if (selectedCases.length && !selectedCases.includes(name)) { skipped++; return; }
    try {
        await action();
        results.push({name, status: "PASS"});
        console.log("PASS " + name);
    } catch (error) {
        const safe = new Set(["FixtureRuntime", "FixtureExit", "FixtureStderr", "FixtureInput", "FixtureProtocol", "FixtureTimeout"]);
        const category = safe.has(error?.message) ? error.message : "AssertionOrRuntime";
        results.push({name, status: "FAIL", category});
        console.log("FAIL " + name + " " + category);
    }
}
async function caseCheck(name, action) {
    await check(name, async () => {
        const request = transport();
        try { await action(createCloudModel(createModel, request), request); }
        finally { await request.close(); }
    });
}
function filled(bridge, {media = true, ready = true} = {}) {
    const model = bridge.model;
    model.edit("kind", "Layanan");
    model.edit("title", "Synthetic neon box title");
    model.edit("summary", "Synthetic neon box summary.");
    model.edit("fact", privateFact);
    model.edit("source", privateSource);
    model.edit("verified", ready);
    if (media) {
        for (const id of ["c", "a", "b"]) model.select(id, true);
        if (ready) {
            for (const id of ["b", "c", "a"]) model.right(id, true);
            model.cover("b");
        }
    }
    assert(bridge.model.draft().ok);
    return bridge;
}
function ok(reply) { assert.equal(reply.ok, true); return reply; }
function denied(reply, category) {
    assert.equal(reply.ok, false);
    if (category) assert.equal(reply.category, category);
    assert(!Object.hasOwn(reply, "state"));
    assert(!Object.hasOwn(reply, "export"));
}
async function approved(bridge) {
    ok(await bridge.save());
    const reviewed = ok(await bridge.preview());
    assert.equal(reviewed.review.revision, bridge.view().serverRevision);
    assert.match(reviewed.review.fingerprint, /^[a-f0-9]{64}$/);
    const reply = ok(await bridge.approve());
    assert.equal(reply.state.status, "approved");
    assert.equal(bridge.view().approved, true);
    return reply;
}
async function exportFor(bridge, request) {
    const reply = ok(await request("export", {expected_revision: bridge.view().serverRevision}));
    assert.deepEqual(Object.keys(reply.export).sort(), ["bytes", "path", "prev_release", "sha256", "source_rev"]);
    assert.equal(reply.export.path, "includes/refresh-data.json");
    assert.equal(reply.export.source_rev, bridge.view().serverRevision);
    assert.equal(reply.export.prev_release, release);
    assert.equal(require("node:crypto").createHash("sha256").update(reply.export.bytes).digest("hex"), reply.export.sha256);
    return reply.export;
}

async function run() {
    setup();
    await caseCheck("initial-empty-and-unsaved-boundary", async (bridge) => {
        const result = ok(await bridge.load());
        assert.deepEqual(result.state, {revision: 0, status: "empty", snapshot: null});
        assert.equal(bridge.view().serverRevision, 0);
        assert.equal(bridge.view().saved, false);
        assert.equal(bridge.view().reviewReady, false);
        denied(await bridge.preview(), "Unsaved");
        denied(await bridge.approve(), "ReviewRequired");
        denied(bridge.queue());
    });
    await caseCheck("full-save-fresh-load-edit-roundtrip", async (bridge, request) => {
        filled(bridge);
        const original = snapshot(bridge.model), uiRevision = bridge.view().revision;
        const saved = ok(await bridge.save());
        assert.equal(saved.state.revision, 1);
        assert.equal(saved.state.status, "draft");
        assert.deepEqual(canonicalSnapshot(saved.state.snapshot), original);
        assert.equal(bridge.view().revision, uiRevision);
        assert(uiRevision > bridge.view().serverRevision);
        assert.equal(bridge.view().saved, true);
        const freshRequest = transport("owner", request.root);
        try {
            const fresh = createCloudModel(createModel, freshRequest), oldModel = fresh.model;
            ok(await fresh.load());
            assert.notEqual(fresh.model, oldModel);
            assert.deepEqual(snapshot(fresh.model), original);
            assert.equal(fresh.view().saved, true);
            assert.equal(fresh.view().serverRevision, 1);
            assert.equal(fresh.view().approved, false);
            assert.equal(fresh.view().reviewReady, false);
            fresh.model.edit("summary", "Synthetic edited summary.");
            assert.equal(fresh.view().saved, false);
            assert.equal(fresh.view().serverRevision, 1);
            assert.equal(ok(await fresh.save()).state.revision, 2);
            ok(await bridge.load());
            assert.deepEqual(snapshot(bridge.model), snapshot(fresh.model));
        } finally { await freshRequest.close(); }
    });
    await caseCheck("review-and-approval-require-saved-current-draft", async (bridge, request) => {
        filled(bridge);
        denied(await bridge.preview(), "Unsaved");
        ok(await bridge.save());
        denied(await bridge.approve(), "ReviewRequired");
        denied(await request("approve", {expected_revision: 1}));
        await approved(bridge);
        denied(bridge.queue());
        const reload = ok(await bridge.load());
        assert.equal(reload.state.status, "approved");
        assert.equal(bridge.view().approved, false);
        assert.equal(bridge.view().reviewReady, false);
        denied(await bridge.approve(), "ReviewRequired");
    });
    for (const gate of ["rights", "cover", "fact"]) {
        await caseCheck("pending-" + gate + "-saves-and-reviews-but-cannot-approve", async (bridge, request) => {
            filled(bridge);
            if (gate === "rights") bridge.model.right("a", false);
            if (gate === "cover") bridge.model.cover(null);
            if (gate === "fact") bridge.model.edit("verified", false);
            ok(await bridge.save());
            ok(await bridge.preview());
            denied(await request("approve", {expected_revision: 1}), "Invalid");
            denied(await bridge.approve());
            assert.equal(bridge.view().approved, false);
            assert.equal(ok(await request("load", {})).state.status, "draft");
        });
    }
    await caseCheck("no-media-no-fact-can-be-approved", async (bridge, request) => {
        filled(bridge, {media: false});
        bridge.model.edit("fact", "");
        bridge.model.edit("source", "");
        await approved(bridge);
        const output = JSON.parse((await exportFor(bridge, request)).bytes);
        assert.equal(output.services["neon-box"].image, null);
    });
    await caseCheck("private-edits-and-resave-revoke-approval", async (bridge) => {
        filled(bridge);
        const edits = [
            model => model.edit("source", privateSource + "_CHANGED"),
            model => model.right("a", false),
            model => model.move("a", -1),
            model => model.cover("a"),
            model => model.edit("verified", false),
        ];
        for (const edit of edits) {
            bridge.model.edit("verified", true);
            bridge.model.right("a", true);
            await approved(bridge);
            const revision = bridge.view().serverRevision;
            edit(bridge.model);
            assert.equal(bridge.view().approved, false);
            assert.equal(bridge.view().reviewReady, false);
            assert.equal(bridge.view().saved, false);
            assert.equal(bridge.view().needsReload, false);
            assert.equal(bridge.view().serverRevision, revision);
            denied(await bridge.approve(), "ReviewRequired");
            const saved = ok(await bridge.save());
            assert.equal(saved.state.status, "draft");
            assert.equal(saved.state.revision, revision + 1);
        }
    });
    await caseCheck("stale-saver-review-and-recovery", async (bridge, request) => {
        filled(bridge);
        ok(await bridge.save());
        ok(await bridge.preview());
        const secondRequest = transport("owner", request.root);
        try {
            const second = createCloudModel(createModel, secondRequest);
            ok(await second.load());
            second.model.edit("summary", "Synthetic concurrent edit.");
            assert.equal(ok(await second.save()).state.revision, 2);
            denied(await bridge.approve(), "Conflict");
            denied(await request("preview", {expected_revision: 1}), "Conflict");
            bridge.model.edit("title", "Synthetic stale edit");
            denied(await bridge.save(), "Conflict");
            assert.equal(bridge.view().approved, false);
            assert.equal(bridge.view().reviewReady, false);
            ok(await bridge.load());
            assert.equal(bridge.view().serverRevision, 2);
            assert.equal(bridge.view().needsReload, false);
            assert.deepEqual(snapshot(bridge.model), snapshot(second.model));
        } finally { await secondRequest.close(); }
    });
    await caseCheck("two-session-conflict-revokes-local-approved-state", async (bridge, request) => {
        filled(bridge);
        await approved(bridge);
        const before = snapshot(bridge.model), uiRevision = bridge.view().revision;
        const secondRequest = transport("owner", request.root);
        try {
            const second = createCloudModel(createModel, secondRequest);
            ok(await second.load());
            second.model.edit("summary", "Synthetic second-session draft.");
            assert.equal(ok(await second.save()).state.revision, 2);
            denied(await bridge.approve(), "Conflict");
            assert.equal(bridge.view().approved, false);
            assert.equal(bridge.view().reviewReady, false);
            assert.equal(bridge.view().previewReady, false);
            assert.equal(bridge.view().saved, false);
            assert.equal(bridge.view().needsReload, true);
            assert.equal(bridge.view().serverRevision, 1);
            assert.equal(bridge.view().revision, uiRevision);
            assert.deepEqual(snapshot(bridge.model), before);
            bridge.model.edit("title", "Synthetic unsaved local edit");
            const edited = snapshot(bridge.model);
            denied(await bridge.save(), "Conflict");
            assert.deepEqual(snapshot(bridge.model), edited);
            denied(await request("export", {expected_revision: 1}), "Conflict");
            ok(await bridge.load());
            assert.equal(bridge.view().serverRevision, 2);
            assert.equal(bridge.view().needsReload, false);
            assert.deepEqual(snapshot(bridge.model), snapshot(second.model));
        } finally { await secondRequest.close(); }
    });
    await caseCheck("fresh-process-cannot-forge-or-replay-review", async (bridge, request) => {
        filled(bridge);
        ok(await bridge.save());
        const review = ok(await bridge.preview()).review;
        const reloadedRequest = transport("owner", request.root);
        try {
            ok(await reloadedRequest("load", {}));
            denied(await reloadedRequest("approve", {expected_revision: 1}));
            denied(await reloadedRequest("approve", {expected_revision: 1, review}), "Invalid");
            assert.equal(ok(await request("load", {})).state.status, "draft");
        } finally { await reloadedRequest.close(); }
    });
    await caseCheck("backend-public-validation-is-stricter-than-prototype", async (bridge, request) => {
        filled(bridge);
        const valid = snapshot(bridge.model);
        const edits = [
            s => { s.fields.kind = "Proyek"; },
            s => { s.fields.kind = "Artikel"; },
            s => { s.fields.title = "<img src=x onerror=alert(1)>"; },
            s => { s.fields.summary = "javascript:alert(1)"; },
            s => { s.fields.title = "x".repeat(121); },
            s => { s.fields.summary = "x".repeat(501); },
            s => { s.fields.title = " "; },
        ];
        for (const edit of edits) {
            const invalid = clone(valid); edit(invalid);
            denied(await request("save", {expected_revision: 0, snapshot: invalid}), "Invalid");
            assert.equal(ok(await request("load", {})).state.revision, 0);
        }
        ok(await bridge.save());
    });
    await caseCheck("backend-validates-entire-media-and-private-schema", async (bridge, request) => {
        filled(bridge);
        const valid = snapshot(bridge.model);
        const edits = [
            s => { s.order.push("d"); },
            s => { s.order.push("a"); },
            s => { s.rights.push("d"); },
            s => { s.rights.push("a"); },
            s => { s.order = ["a"]; s.rights = ["b"]; s.cover = "a"; },
            s => { s.order = ["a"]; s.rights = ["a"]; s.cover = "b"; },
            s => { s.cover = "fixture-photo-a"; },
            s => { s.fields.verified = "true"; },
            s => { s.fields.source = "synthetic\u0000private"; },
            s => { s.fields.fact = "x".repeat(2001); },
            s => { s.fields.source = "x".repeat(501); },
            // Newlines are allowed as private text, but JSON encoding exceeds the note limit.
            s => { s.fields.fact = "\n".repeat(2000); },
            s => { delete s.fields.source; },
            s => { s.fields.identity = "synthetic-owner"; },
            s => { s.public_service = {}; },
        ];
        for (const edit of edits) {
            const invalid = clone(valid); edit(invalid);
            denied(await request("save", {expected_revision: 0, snapshot: invalid}), "Invalid");
            assert.equal(ok(await request("load", {})).state.revision, 0);
        }
        ok(await bridge.save());
    });
    await caseCheck("stored-private-envelope-refuses-load-and-overwrite", async (bridge, request) => {
        filled(bridge);
        ok(await bridge.save());
        const statePath = path.join(request.root, "neon-box-state.json");
        const original = JSON.parse(fs.readFileSync(statePath, "utf8"));
        const valid = snapshot(bridge.model), mismatched = clone(valid);
        mismatched.fields.title = "Synthetic mismatched private title";
        const notes = [
            "Synthetic legacy plain note",
            JSON.stringify({schema_version: 2, snapshot: valid}),
            JSON.stringify({schema_version: 1, snapshot: mismatched}),
        ];
        for (const private_note of notes) {
            const bytes = JSON.stringify({...original, private_note}) + "\n";
            fs.writeFileSync(statePath, bytes, {mode: 0o600});
            denied(await request("load", {}), "Invalid");
            denied(await request("save", {expected_revision: 1, snapshot: valid}), "Invalid");
            assert.equal(fs.readFileSync(statePath, "utf8"), bytes);
        }
    });
    await caseCheck("strict-wire-refuses-request-identity-and-client-approval", async (bridge, request) => {
        filled(bridge);
        const valid = snapshot(bridge.model);
        for (const envelope of [
            {action: "load", payload: {}, identity: "synthetic-owner"},
            {action: "load", payload: {identity: "synthetic-owner"}},
            {action: "save", payload: {expected_revision: 0, snapshot: valid, csrf: true}},
            {action: "approve", payload: {expected_revision: 0, approved: true}},
            {action: "publish", payload: {}},
        ]) denied(await request.raw(envelope), "Invalid");
        assert.equal(ok(await request("load", {})).state.revision, 0);
    });
    for (const mode of ["anonymous", "other", "expired"]) {
        await check("synthetic-" + mode + "-context-denies-access", async () => {
            const request = transport(mode);
            try {
                const bridge = filled(createCloudModel(createModel, request));
                const draft = snapshot(bridge.model);
                for (const [action, payload] of [
                    ["load", {}], ["save", {expected_revision: 0, snapshot: draft}],
                    ["preview", {expected_revision: 1}], ["approve", {expected_revision: 1}],
                    ["export", {expected_revision: 1}],
                ]) denied(await request(action, payload), "Denied");
                assert.deepEqual(fs.readdirSync(request.root), []);
            } finally { await request.close(); }
        });
    }
    await caseCheck("synthetic-csrf-missing-context-refuses-mutations", async (bridge, ownerRequest) => {
        filled(bridge);
        await approved(bridge);
        const request = transport("csrf-missing", ownerRequest.root);
        try {
            ok(await request("load", {}));
            ok(await request("preview", {expected_revision: 1}));
            denied(await request("save", {expected_revision: 1, snapshot: snapshot(bridge.model)}), "Denied");
            denied(await request("approve", {expected_revision: 1}), "Denied");
            denied(await request("export", {expected_revision: 1}), "Denied");
        } finally { await request.close(); }
    });
    await caseCheck("public-export-excludes-private-snapshot-and-other-record-edits", async (bridge, request) => {
        filled(bridge);
        await approved(bridge);
        const first = await exportFor(bridge, request);
        const output = JSON.parse(first.bytes);
        assert.equal(output.services["neon-box"].name, bridge.view().fields.title);
        assert.equal(output.services["neon-box"].intro, bridge.view().fields.summary);
        assert.equal(output.services["neon-box"].image, "fixture-photo-b");
        const retained = {
            symbol: "N", body: "Synthetic service description.",
            options: ["Synthetic choice A", "Synthetic choice B"],
            guide: "Confirm synthetic requirements.", seo_title: "Synthetic retained SEO title",
        };
        for (const [key, value] of Object.entries(retained)) {
            assert.deepEqual(output.services["neon-box"][key], value);
        }
        assert.deepEqual(Object.keys(output.services).sort(), ["huruf-timbul", "nametag", "neon-box", "neon-flex", "papan-nama", "reklame", "stiker-cutting"]);
        for (const [id, service] of Object.entries(output.services)) {
            if (id === "neon-box") continue;
            assert.deepEqual(service, {
                name: "Synthetic " + id, intro: "Synthetic introduction.", image: null, ...retained,
            });
        }
        const {services, ...publicMetadata} = output;
        assert.deepEqual(publicMetadata, {
            domain: "https://www.3dkanadvertising.store", asset: "/assets/synthetic",
            logo: "/assets/synthetic/logo.svg", phone: "0000000000",
            cities: {"synthetic-city": {name: "Synthetic City"}}, legacy_services: ["synthetic-legacy"],
            photos: ["a", "b", "c"].map(id => ({id: "fixture-photo-" + id, src: "/assets/synthetic/" + id + ".webp"})),
            organization: {name: "Synthetic organization", url: "https://www.3dkanadvertising.store"},
        });
        for (const secret of [privateFact, privateSource, '"snapshot"', '"private_note"', '"verified"', '"rights"', '"review"']) {
            assert.equal(first.bytes.includes(secret), false);
        }
        // Private-only changes must keep deterministic public bytes while requiring a new review.
        bridge.model.move("a", -1);
        bridge.model.edit("source", privateSource + "_CHANGED");
        bridge.model.edit("verified", true);
        await approved(bridge);
        const second = await exportFor(bridge, request);
        assert.equal(second.bytes, first.bytes);
        assert.equal(second.sha256, first.sha256);
        // Changing the cover can affect only this service's image in the baseline clone.
        bridge.model.cover("a");
        await approved(bridge);
        const third = JSON.parse((await exportFor(bridge, request)).bytes);
        output.services["neon-box"].image = "fixture-photo-a";
        assert.deepEqual(third, output);
    });
    await caseCheck("synthetic-next-release-refuses-old-release-export", async (bridge, ownerRequest) => {
        filled(bridge);
        await approved(bridge);
        const request = transport("next-release", ownerRequest.root);
        try {
            denied(await request("load", {}), "Conflict");
            denied(await request("save", {expected_revision: 1, snapshot: snapshot(bridge.model)}), "Conflict");
            denied(await request("export", {expected_revision: 1}), "Conflict");
            denied(await request("preview", {expected_revision: 1}), "Conflict");
            denied(await request("approve", {expected_revision: 1}));
        } finally { await request.close(); }
    });
    await check("deferred-old-approval-cannot-approve-new-server-revision", async () => {
        let revision = 0, stored = null, releaseApproval;
        const delayed = (action, payload) => {
            if (action === "save") {
                assert.equal(payload.expected_revision, revision);
                stored = clone(payload.snapshot);
                return {ok: true, state: {revision: ++revision, status: "draft", snapshot: stored}};
            }
            if (action === "preview") return {ok: true, review: {revision, fingerprint: "0".repeat(64)}};
            if (action === "approve") {
                const approvedRevision = revision;
                return new Promise(resolve => {
                    releaseApproval = () => resolve({ok: true, state: {revision: approvedRevision, status: "approved", snapshot: stored}});
                });
            }
            throw new Error("UnexpectedSyntheticAction");
        };
        const bridge = filled(createCloudModel(createModel, delayed));
        ok(await bridge.save());
        ok(await bridge.preview());
        const oldApproval = bridge.approve();
        assert.equal(typeof releaseApproval, "function");
        ok(await bridge.save());
        ok(await bridge.preview());
        assert.equal(bridge.view().serverRevision, 2);
        releaseApproval();
        denied(await oldApproval, "Conflict");
        assert.equal(bridge.view().serverRevision, 2);
        assert.equal(bridge.view().approved, false);
    });
    await check("deferred-load-preserves-newer-unsaved-local-edit", async () => {
        const storedModel = filled(createCloudModel(createModel, () => { throw new Error("UnexpectedSyntheticAction"); }));
        const stored = snapshot(storedModel.model);
        let releaseLoad;
        const bridge = createCloudModel(createModel, action => {
            assert.equal(action, "load");
            return new Promise(resolve => {
                releaseLoad = () => resolve({ok: true, state: {revision: 1, status: "draft", snapshot: stored}});
            });
        });
        const original = bridge.model, loading = bridge.load();
        bridge.model.edit("title", "Synthetic new local edit");
        releaseLoad();
        denied(await loading, "Unsaved");
        assert.equal(bridge.model, original);
        assert.equal(bridge.view().fields.title, "Synthetic new local edit");
        assert.equal(bridge.view().serverRevision, 0);
        assert.equal(bridge.view().saved, false);
    });
    await check("pending-first-save-survives-local-unsaved-preview", async () => {
        let releaseSave;
        const bridge = filled(createCloudModel(createModel, (action, payload) => {
            assert.equal(action, "save");
            return new Promise(resolve => {
                releaseSave = () => resolve({ok: true, state: {revision: 1, status: "draft", snapshot: clone(payload.snapshot)}});
            });
        }));
        const saving = bridge.save();
        denied(await bridge.preview(), "Unsaved");
        denied(await bridge.approve(), "ReviewRequired");
        releaseSave();
        ok(await saving);
        assert.equal(bridge.view().serverRevision, 1);
        assert.equal(bridge.view().saved, true);
        assert.equal(bridge.view().approved, false);
    });
    await check("deferred-old-save-cannot-lower-loaded-server-revision", async () => {
        let releaseSave, stored;
        const bridge = filled(createCloudModel(createModel, (action, payload) => {
            if (action === "save") {
                stored = clone(payload.snapshot);
                return new Promise(resolve => {
                    releaseSave = () => resolve({ok: true, state: {revision: 1, status: "draft", snapshot: stored}});
                });
            }
            assert.equal(action, "load");
            return {ok: true, state: {revision: 2, status: "draft", snapshot: stored}};
        }));
        const saving = bridge.save();
        ok(await bridge.load());
        const currentModel = bridge.model;
        releaseSave();
        denied(await saving, "Conflict");
        assert.equal(bridge.model, currentModel);
        assert.equal(bridge.view().serverRevision, 2);
        assert.equal(bridge.view().saved, true);
        assert.equal(bridge.view().approved, false);
    });
    await check("prototype-has-no-external-side-effects", () => assert.equal(sideEffects, 0));
    await check("superseded-conflict-preserves-newer-approved-state", async () => {
        let revision = 0, stored = null, rejectOldApproval, approvals = 0;
        const delayed = (action, payload) => {
            if (action === "save") {
                assert.equal(payload.expected_revision, revision);
                stored = clone(payload.snapshot);
                return {ok: true, state: {revision: ++revision, status: "draft", snapshot: stored}};
            }
            if (action === "preview") return {ok: true, review: {revision, fingerprint: "0".repeat(64)}};
            if (action === "approve") {
                if (++approvals === 1) return new Promise(resolve => {
                    rejectOldApproval = () => resolve({ok: false, category: "Conflict"});
                });
                return {ok: true, state: {revision, status: "approved", snapshot: stored}};
            }
            throw new Error("UnexpectedSyntheticAction");
        };
        const bridge = filled(createCloudModel(createModel, delayed));
        ok(await bridge.save());
        ok(await bridge.preview());
        const oldApproval = bridge.approve();
        ok(await bridge.save());
        ok(await bridge.preview());
        ok(await bridge.approve());
        const before = snapshot(bridge.model);
        rejectOldApproval();
        denied(await oldApproval, "Conflict");
        assert.equal(bridge.view().serverRevision, 2);
        assert.equal(bridge.view().approved, true);
        assert.equal(bridge.view().reviewReady, true);
        assert.equal(bridge.view().needsReload, false);
        assert.deepEqual(snapshot(bridge.model), before);
    });
}

(async () => {
    try {
        await run();
        if (selectedCases.some(name => !results.some(result => result.name === name))) {
            results.push({name: "focused-case-selection", status: "FAIL", category: "UnknownCase"});
        }
    }
    catch {
        results.push({name: "cloud-fixture-setup", status: "FAIL", category: "SetupBoundary"});
        console.log("FAIL cloud-fixture-setup SetupBoundary");
    } finally {
        for (const child of processes) child.kill();
        if (temporaryRoot && inside(temporaryRoot, runner) && !inside(temporaryRoot, repo)) {
            try { fs.rmSync(temporaryRoot, {recursive: true, force: true}); }
            catch {
                results.push({name: "temporary-private-fixture-cleanup", status: "FAIL", category: "CleanupBoundary"});
                console.log("FAIL temporary-private-fixture-cleanup CleanupBoundary");
            }
        }
    }
    const passed = results.filter(result => result.status === "PASS").length;
    const failed = results.length - passed;
    console.log(JSON.stringify({passed, failed, skipped, execution: "Cloud CLI synthetic bridge; no live CMS"}));
    if (failed) process.exitCode = 1;
})();
