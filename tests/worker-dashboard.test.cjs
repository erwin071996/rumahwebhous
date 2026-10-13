const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'public_html/pekerja-web/dashboard.js'), 'utf8');
const sample = JSON.parse(fs.readFileSync(path.join(root, 'public_html/pekerja-web/status.example.json'), 'utf8'));

class Element {
  constructor() { this.dataset = {}; this.children = []; this.fields = {}; this.textContent = ''; this.hidden = false; }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes.flatMap(node => node.fragment ? node.children : [node]); }
  setAttribute(key, value) { this[key] = value; }
  removeAttribute(key) { delete this[key]; }
  addEventListener(key, handler) { this[key] = handler; }
  querySelector(key) { return this.fields[key] ||= new Element(); }
  cloneNode() { return new Element(); }
}

async function flush() { for (let i = 0; i < 16; i++) await Promise.resolve(); }

function browser() {
  let now = Date.parse("2000-01-01T00:00:00Z");
  const timers = new Map();
  let timerId = 0;
  const ids = {};
  const events = {};
  const requests = [];
  const document = {
    hidden: false,
    getElementById(id) {
      if (!ids[id]) ids[id] = new Element();
      if (id === 'team-card-template') ids[id].content = { firstElementChild: new Element() };
      return ids[id];
    },
    createDocumentFragment() { const node = new Element(); node.fragment = true; return node; },
    createElement() { return new Element(); },
    createTextNode(value) { const node = new Element(); node.textContent = value; return node; },
    addEventListener(key, handler) { events[key] = handler; },
    querySelectorAll() { return (ids.teams?.children || []).filter(node => node.dataset.status === 'working'); }
  };
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])); } static now() { return now; } }
  const context = {
    document, window: { addEventListener(key, handler) { events[key] = handler; } }, Date: Clock,
    Intl, URL, AbortController, TextEncoder,
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, at: now + delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url, options) {
      let resolve, reject;
      const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
      requests.push({ url, options, resolve, reject });
      options.signal.addEventListener('abort', () => reject(new Error('abort')));
      return promise;
    }
  };
  vm.runInNewContext(source, context);
  const fresh = () => {
    const data = structuredClone(sample);
    data.updatedAt = new Clock().toISOString().replace('.000Z', 'Z');
    data.release.observedAt = data.updatedAt;
    data.teams.forEach(team => { team.observedAt = data.updatedAt; });
    data.teams[0].status = 'working';
    data.teams[0].evidence = [{label: 'Synthetic evidence', url: 'https://github.com/erwin071996/rumahwebhous/pull/1'}];
    return data;
  };
  return {
    ids, document, requests, fresh,
    async respond(data, index = requests.length - 1) {
      requests[index].resolve({ ok: true, headers: { get() { return null; } }, async text() { return JSON.stringify(data); } });
      await flush();
    },
    async advance(ms) {
      const end = now + ms;
      while (true) {
        const entry = [...timers].filter(([, timer]) => timer.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!entry) break;
        now = entry[1].at;
        timers.delete(entry[0]);
        entry[1].fn();
        await flush();
      }
      now = end;
      await flush();
    },
    async visible(value) { document.hidden = !value; events.visibilitychange(); await flush(); },
    click() { ids['refresh-button'].click(); }
  };
}

test('eight factual cards and independent source/view timestamps', async () => {
  const app = browser();
  await app.respond(app.fresh());
  assert.equal(app.ids.teams.children.length, 8);
  assert.equal(app.ids.teams.children[0].dataset.status, 'working');
  assert.notEqual(app.ids['source-updated'].dateTime, undefined);
  assert.match(app.ids['view-checked'].dateTime, /Z$/);
  assert.equal(app.requests[0].options.cache, 'no-store');
});

test('visible polling every three seconds never overlaps pending request', async () => {
  const app = browser();
  app.click();
  assert.equal(app.requests.length, 1);
  await app.respond(app.fresh());
  await app.advance(2999);
  assert.equal(app.requests.length, 1);
  await app.advance(1);
  assert.equal(app.requests.length, 2);
  app.click();
  await app.advance(3000);
  assert.equal(app.requests.length, 2);
});

test('hidden aborts request and pauses polling; visible refreshes immediately', async () => {
  const app = browser();
  const signal = app.requests[0].options.signal;
  await app.visible(false);
  assert.equal(signal.aborted, true);
  await app.advance(60000);
  assert.equal(app.requests.length, 1);
  await app.visible(true);
  assert.equal(app.requests.length, 2);
});

test('rapid hide/show queues an immediate refresh after the aborted request settles', async () => {
  const app = browser();
  await Promise.all([app.visible(false), app.visible(true)]);
  await app.advance(0);
  assert.equal(app.requests.length, 2);
  assert.equal(app.requests[0].options.signal.aborted, true);
});

test('timeout and repeated errors back off; successful response resets cadence', async () => {
  const app = browser();
  await app.advance(5000);
  assert.equal(app.requests[0].options.signal.aborted, true);
  await app.advance(5999);
  assert.equal(app.requests.length, 1);
  await app.advance(1);
  assert.equal(app.requests.length, 2);
  app.requests[1].reject(new Error('offline'));
  await flush();
  await app.advance(11999);
  assert.equal(app.requests.length, 2);
  await app.advance(1);
  assert.equal(app.requests.length, 3);
  await app.respond(app.fresh());
  await app.advance(3000);
  assert.equal(app.requests.length, 4);
});

test('stale or unreadable evidence stops work and preserves labelled history', async () => {
  const app = browser();
  const data = app.fresh();
  data.teams[0].observedAt = new Date(Date.parse(data.updatedAt) - 901000).toISOString().replace('.000Z', 'Z');
  await app.respond(data);
  assert.equal(app.ids.teams.children[0].dataset.status, 'unknown');
  app.click();
  await app.respond(app.fresh());
  assert.equal(app.ids.teams.children[0].dataset.status, 'working');
  await app.advance(3000);
  app.requests.at(-1).reject(new Error('offline'));
  await flush();
  assert.equal(app.ids.teams.children[0].dataset.status, 'unknown');
  assert.match(app.ids.teams.children[0].fields['.team-history'].textContent, /riwayat|terakhir tercatat/);
});

test('malformed feeds and foreign evidence URLs fail closed', async () => {
  for (const mutate of [f => f.teams[1].id = 'backend', f => f.teams[0].evidence[0].url = 'https://github.com/other/repo/pull/1', f => f.teams[0].observedAt = null, f => f.rawChat = 'raw transcript']) {
    const app = browser();
    const data = app.fresh();
    mutate(data);
    await app.respond(data);
    assert.ok(app.ids.teams.children.every(card => card.dataset.status === 'unknown'));
    assert.equal(app.ids['connection-badge'].dataset.state, 'error');
  }
});

test('stale feed time demotes all cards even when JSON can still be fetched', async () => {
  const app = browser();
  const data = app.fresh();
  data.updatedAt = new Date(Date.parse(data.updatedAt) - 901000).toISOString().replace('.000Z', 'Z');
  data.release.observedAt = data.updatedAt;
  data.teams.forEach(team => { team.observedAt = data.updatedAt; });
  await app.respond(data);
  assert.ok(app.ids.teams.children.every(card => card.dataset.status === 'unknown'));
  assert.equal(app.ids['connection-badge'].dataset.state, 'stale');
});


test('empty example is unknown without invented source timestamps', async () => {
  const app = browser();
  await app.respond(structuredClone(sample));
  assert.ok(app.ids.teams.children.every(card => card.dataset.status === 'unknown'));
  assert.equal(app.ids['source-updated'].dateTime, undefined);
  assert.equal(app.ids['connection-badge'].dataset.state, 'unknown');
  assert.equal(app.ids['connection-badge'].textContent, 'Belum ada bukti sumber');
});

test('missing private runtime feed fails closed without fetching the example', async () => {
  const app = browser();
  app.requests[0].resolve({ok: false, status: 404});
  await flush();
  assert.ok(app.ids.teams.children.every(card => card.dataset.status === 'unknown'));
  assert.equal(app.ids['connection-badge'].dataset.state, 'error');
  assert.ok(app.requests.every(request => request.url === './status.json'));
});

test('null source timestamp cannot claim a known team or release', async () => {
  for (const mutate of [f => f.teams[0].status = 'working', f => f.release.stage = 'live']) {
    const app = browser();
    const data = structuredClone(sample);
    mutate(data);
    await app.respond(data);
    assert.equal(app.ids['connection-badge'].dataset.state, 'error');
  }
});
