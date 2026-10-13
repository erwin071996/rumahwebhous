"use strict";

// Test-only transport bridge. createModel is the unchanged prototype factory.
// No HTTP client, browser storage, identity, uploader or publisher is installed.
function createCloudModel(createModel, transport) {
    let model = createModel(), serverRevision = 0, savedSnapshot = null, reviewReady = false, operation = 0;
    const snapshot = () => {
        const v = model.view();
        return {fields: v.fields, order: v.order, rights: v.rights, cover: v.cover};
    };
    // Rights are a set; media order is independently meaningful.
    const fingerprint = s => JSON.stringify({...s, rights: [...s.rights].sort()});
    const saved = () => savedSnapshot !== null && savedSnapshot === fingerprint(snapshot());
    const localFailure = category => ({ok: false, category});
    function restore(s) {
        const fresh = createModel();
        for (const [key, value] of Object.entries(s.fields)) fresh.edit(key, value);
        for (const id of s.order) fresh.select(id, true);
        for (const id of s.rights) fresh.right(id, true);
        fresh.cover(s.cover);
        fresh.draft();
        return fresh;
    }
    return Object.freeze({
        get model() { return model; },
        view() { return {...model.view(), serverRevision, saved: saved(), reviewReady: reviewReady && saved() && model.view().previewReady}; },
        async load() {
            const op = ++operation, startingModel = model, uiRevision = model.view().revision;
            reviewReady = false;
            const reply = await transport("load", {});
            if (!reply.ok) return reply;
            if (op !== operation || model !== startingModel) return localFailure("Conflict");
            if (model.view().revision !== uiRevision) return localFailure("Unsaved");
            const fresh = reply.state.snapshot === null ? createModel() : restore(reply.state.snapshot);
            model = fresh;
            serverRevision = reply.state.revision;
            savedSnapshot = reply.state.snapshot === null ? null : fingerprint(snapshot());
            reviewReady = false;
            return reply;
        },
        async save() {
            const draft = model.draft();
            if (!draft.ok) return draft;
            const op = ++operation, startingModel = model;
            const sent = snapshot();
            reviewReady = false;
            const reply = await transport("save", {expected_revision: serverRevision, snapshot: sent});
            if (reply.ok) {
                if (op !== operation || model !== startingModel) return localFailure("Conflict");
                serverRevision = reply.state.revision;
                savedSnapshot = fingerprint(sent);
            }
            return reply;
        },
        async preview() {
            if (!saved()) return localFailure("Unsaved");
            const op = ++operation, startingModel = model, startingRevision = serverRevision;
            reviewReady = false;
            const sent = fingerprint(snapshot()), uiRevision = model.view().revision;
            const reply = await transport("preview", {expected_revision: serverRevision});
            if (!reply.ok) return reply;
            if (op !== operation || model !== startingModel || serverRevision !== startingRevision) return localFailure("Conflict");
            if (fingerprint(snapshot()) !== sent || model.view().revision !== uiRevision) return localFailure("Unsaved");
            const preview = model.preview();
            reviewReady = preview.ok;
            return preview.ok ? {...reply, preview} : preview;
        },
        async approve() {
            if (!saved() || !reviewReady || !model.view().previewReady) return localFailure("ReviewRequired");
            const op = ++operation, startingModel = model, startingRevision = serverRevision;
            // The server repeats media/fact/revision checks; no client approval flag is sent.
            const sent = fingerprint(snapshot()), uiRevision = model.view().revision;
            const reply = await transport("approve", {expected_revision: serverRevision});
            if (!reply.ok) return reply;
            if (op !== operation || model !== startingModel || serverRevision !== startingRevision
                || reply.state.revision !== startingRevision) return localFailure("Conflict");
            if (fingerprint(snapshot()) !== sent || model.view().revision !== uiRevision) { reviewReady = false; return localFailure("Unsaved"); }
            const approval = model.approve();
            return approval.ok ? reply : approval;
        },
        queue() { return model.queue(); }
    });
}

module.exports = {createCloudModel};
