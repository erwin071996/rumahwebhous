"use strict";
async function run(api) {
  let passed = 0;
  const results = [];
  const assert = function (condition, message) { if (!condition) throw new Error(message); };
  const check = async function (name, fn) {
    await fn();
    passed += 1;
    results.push(name);
  };
  const home = function (extra) { return Object.assign({ type: "Neon box" }, extra); };
  await check("reject empty scope", () => assert(!api.prepare({}, "home").ok, "An empty brief must not create a link"));
  await check("accept incomplete measurements", () => {
    const r = api.prepare(home(), "home");
    assert(r.ok && r.message.includes("Ukuran perkiraan: -"), "Optional information must remain optional");
  });
  await check("fixed verified recipient", () => {
    const r = api.prepare(home({ recipient: "wrong", url: "javascript:bad" }), "home");
    const prefix = "https://wa.me/6285340382029?text=";
    assert(r.url.startsWith(prefix), "Untrusted fields must not control destination");
    const payload = r.url.slice(prefix.length);
    assert(decodeURIComponent(payload) === r.message && !/[&#?]/.test(payload), "Exactly one encoded text parameter");
  });
  await check("punctuation and Unicode roundtrip", () => {
    const note = "3 × 1 m & + # ? = % / 🛠️\nBaris berikutnya <script>alert(1)</script>";
    const r = api.prepare(home({ note }), "home");
    assert(r.ok && decodeURIComponent(r.url.split("?text=")[1]).includes(note), "User text must roundtrip as text");
  });
  await check("project PIC context preserved", () => {
    const r = api.prepare({ type: "Corporate signage", pic: "PIC sintetis", target: "November 2026" }, "project");
    assert(r.ok && r.message.includes("PIC: PIC sintetis") && r.message.includes("Target waktu: November 2026"), "Project fields must not be dropped");
  });
  await check("normalize CRLF without losing note lines", () => {
    const r = api.prepare(home({ company: "  Contoh\r\n  Uji  ", note: "  satu\r\ndua\rketiga  " }), "home");
    assert(r.ok && r.values.company === "Contoh Uji" && r.values.note === "satu\ndua\nketiga", "Single and multiline fields need different normalization");
  });
  await check("unknown selection rejected", () => assert(!api.prepare(home({ type: "javascript:alert(1)" }), "home").ok, "Selection must be allowlisted"));
  await check("unknown context rejected", () => {
    let threw = false; try { api.prepare(home(), "__proto__"); } catch (error) { threw = true; }
    assert(threw, "An invalid form context must not inherit object properties");
  });
  for (const points of ["0", "-1", "1.5", "1e3", "10 titik", "01", "1000000", "１２"]) {
    await check("reject quantity " + points, () => assert(!api.prepare(home({ points }), "home").ok, "Quantity must be a positive integer within the limit"));
  }
  for (const points of ["", "1", "29", "999999"]) {
    await check("accept quantity " + (points || "unknown"), () => assert(api.prepare(home({ points }), "home").ok, "Valid/unknown quantity rejected"));
  }
  await check("text length boundary", () => {
    assert(api.prepare(home({ name: "A".repeat(100), note: "N".repeat(1000) }), "home").ok, "Boundary values should work");
    const r = api.prepare(home({ name: "A".repeat(101) }), "home");
    assert(!r.ok && r.errors.some(e => e.field === "name") && !r.url, "Overlength field must prevent link generation");
  });
  await check("encoded link budget", () => {
    const r = api.prepare(home({ note: "漢".repeat(1000) }), "home");
    assert(!r.ok && !r.url && r.errors.some(e => e.field === "note"), "Encoded Unicode must respect the URL budget");
  });
  await check("reject malformed surrogate", () => assert(!api.prepare(home({ note: "\uD800" }), "home").ok, "Malformed Unicode must not throw URIError"));
  await check("reject hidden controls", () => assert(!api.prepare(home({ name: "PIC\u0000" }), "home").ok, "Hidden controls must not enter a link"));
  await check("reject non-text supplied values", () => assert(!api.prepare(home({ note: { toString: () => "pretend" } }), "home").ok, "Objects must not be implicitly serialized"));
  await check("input object is unchanged", () => {
    const value = home({ note: "  test  " }); const original = JSON.stringify(value);
    api.prepare(value, "home"); assert(JSON.stringify(value) === original, "Preparation must not mutate source");
  });

  class Element {
    constructor(tagName) { this.tagName = tagName || "DIV"; this.attrs = {}; this.events = {}; this.value = ""; this.disabled = false; this.hidden = false; this.type = ""; }
    setAttribute(k, v) { this.attrs[k] = String(v); }
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
    removeAttribute(k) { delete this.attrs[k]; if (k === "href") this.href = ""; }
    addEventListener(k, fn) { (this.events[k] || (this.events[k] = [])).push(fn); }
    focus() { this.focused = true; }
    select() { this.selected = true; }
    async fire(k, target) {
      const event = { target: target || this, prevented: false, preventDefault() { this.prevented = true; } };
      for (const fn of this.events[k] || []) await fn(event);
      return event;
    }
  }
  function fixture(incomplete) {
    const fields = {};
    ["name", "company", "type", "location", "size", "points", "note"].forEach(k => { fields[k] = new Element(k === "type" ? "SELECT" : "INPUT"); });
    fields.type.value = "Neon box";
    const form = new Element("FORM"); form.id = "test-home-brief";
    const status = new Element(), preview = new Element("TEXTAREA"), link = new Element("A"), copy = new Element("BUTTON"), output = new Element();
    const compose = new Element("BUTTON"); compose.type = "button"; compose.disabled = true;
    const fieldset = new Element("FIELDSET"); fieldset.disabled = true;
    form.fields = fields; form.elements = { namedItem: k => fields[k] };
    const map = { "[data-brief-status]": status, "[data-brief-preview]": preview, "[data-brief-whatsapp]": link, "[data-brief-copy]": copy, "[data-brief-output]": output, "[data-brief-compose]": compose };
    if (incomplete) delete map["[data-brief-preview]"];
    form.querySelector = k => map[k] || null;
    form.querySelectorAll = k => k === "fieldset[data-brief-fields]" ? [fieldset] : [];
    return { form, fields, status, preview, link, copy, output, compose, fieldset };
  }
  const savedFormData = globalThis.FormData;
  const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", { value: {}, writable: true, configurable: true });
  globalThis.FormData = class { constructor(form) { this.fields = form.fields; } get(k) { return this.fields[k].value; } };
  try {
    await check("incomplete markup stays disabled", () => {
      const f = fixture(true); api.bind(f.form, "home");
      assert(f.fieldset.disabled && f.compose.disabled && !f.form.getAttribute("data-brief-bound"), "Do not enable an incomplete form");
    });
    await check("missing editable control stays disabled", () => {
      const missing = fixture(); delete missing.form.fields.type; api.bind(missing.form, "home");
      assert(missing.fieldset.disabled && missing.compose.disabled, "Missing fields must not unlock the form");
    });
    const f = fixture(); api.bind(f.form, "home");
    await check("binding enables guarded form once", () => {
      api.bind(f.form, "home");
      assert(!f.fieldset.disabled && !f.compose.disabled && f.form.events.submit.length === 1, "Safe initialization must be idempotent");
      assert(f.preview.readOnly && f.fields.type.required && f.fields.note.maxLength === 1000, "Native attributes must agree with validation");
      assert(f.status.id && Object.values(f.fields).every(field => field.getAttribute("aria-describedby").split(/\s+/).includes(f.status.id)), "Errors must be described when each field receives focus");
    });
    await check("compose previews without opening or sending", async () => {
      await f.compose.fire("click");
      assert(!f.output.hidden && f.link.href.startsWith("https://wa.me/") && f.preview.value.includes("Neon box"), "Composer should create readable output");
      assert(f.status.textContent.includes("kirim pesan di sana"), "Status must not claim delivery");
    });
    await check("edited draft invalidates existing link", async () => {
      f.fields.note.value = "Draf baru"; await f.form.fire("input", f.fields.note);
      assert(f.output.hidden && !f.link.href && f.copy.disabled && !f.preview.value, "Stale output must not remain actionable");
      assert((await f.link.fire("click")).prevented, "Clicking a stale link must be prevented");
    });
    await check("native submit is prevented and validated", async () => {
      f.fields.type.value = "";
      const event = await f.form.fire("submit");
      assert(event.prevented && f.output.hidden && f.fields.type.getAttribute("aria-invalid") === "true" && f.fields.type.focused, "Invalid native submit must not navigate or expose data");
    });
    await check("recover after correcting validation error", async () => {
      f.fields.type.value = "Lainnya"; await f.form.fire("change", f.fields.type); await f.compose.fire("click");
      assert(!f.output.hidden && !f.fields.type.getAttribute("aria-invalid") && f.preview.value.includes("Draf baru"), "Corrected draft should generate fresh output");
    });
    await check("clipboard unavailable gives manual copy instruction", async () => {
      await f.copy.fire("click");
      assert(f.preview.selected && f.status.textContent.includes("menu perangkat") && !f.status.textContent.includes("tersalin"), "Fallback must not claim an unconfirmed clipboard write");
    });
    await check("clipboard success copies exact preview", async () => {
      let copied = ""; globalThis.navigator.clipboard = { writeText: async text => { copied = text; } };
      await f.copy.fire("click");
      assert(copied === f.preview.value && f.status.textContent.includes("tersalin"), "Copy should use the displayed text and report confirmed success");
    });
  } finally {
    globalThis.FormData = savedFormData;
    if (navigatorDescriptor) Object.defineProperty(globalThis, "navigator", navigatorDescriptor);
    else delete globalThis.navigator;
  }
  return { passed, failed: 0, results };
}
if (typeof module === "object" && module.exports) {
  module.exports = run;
  if (require.main === module) run(require("../public_html/assets/ui/brief.js"))
    .then(result => console.log(JSON.stringify(result, null, 2)))
    .catch(error => { console.error(error); process.exitCode = 1; });
}
