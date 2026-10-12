"use strict";
const fs = require("node:fs");
const assert = require("node:assert/strict");
const path = require("node:path");
const root = path.resolve(__dirname, "../public_html");
let passed = 0;
function check(label, condition) {
  assert.ok(condition, label);
  passed += 1;
}
function attrs(tag) {
  const result = {};
  for (const match of tag.matchAll(/([a-zA-Z_:][\w:.-]*)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) {
    result[match[1].toLowerCase()] = match[3] ?? match[4] ?? match[5] ?? true;
  }
  return result;
}
const cases = [
  { file: "index.html", id: "home-brief-form", kind: "home", legacy: "home-v100-js", keys: ["name", "company", "type", "location", "size", "points", "note"] },
  { file: "projects.html", id: "project-brief-form", kind: "project", legacy: "project-brief-js", keys: ["company", "pic", "type", "points", "location", "target", "note"] }
];
for (const item of cases) {
  const html = fs.readFileSync(path.join(root, item.file), "utf8");
  const forms = Array.from(html.matchAll(/<form\b[^>]*>[\s\S]*?<\/form>/gi)).filter(match => attrs(match[0].match(/^<form\b[^>]*>/i)[0]).id === item.id);
  check(item.file + ": exactly one brief form", forms.length === 1);
  const form = forms[0][0];
  check(item.file + ": module context", attrs(form.match(/^<form\b[^>]*>/i)[0])["data-brief-form"] === item.kind);
  const fieldsets = Array.from(form.matchAll(/<fieldset\b[^>]*>[\s\S]*?<\/fieldset>/gi)).filter(match => Object.hasOwn(attrs(match[0].match(/^<fieldset\b[^>]*>/i)[0]), "data-brief-fields"));
  check(item.file + ": guarded fieldset", fieldsets.length === 1 && Object.hasOwn(attrs(fieldsets[0][0].match(/^<fieldset\b[^>]*>/i)[0]), "disabled"));
  const fields = Array.from(form.matchAll(/<(?:input|select|textarea)\b[^>]*>/gi)).map(match => ({ raw: match[0], index: match.index, attributes: attrs(match[0]) }));
  for (const key of item.keys) {
    const matches = fields.filter(field => field.attributes.name === key);
    check(item.file + ": field " + key + " unique and disabled before binding", matches.length === 1 && matches[0].index >= fieldsets[0].index && matches[0].index < fieldsets[0].index + fieldsets[0][0].length);
  }
  const compose = Array.from(form.matchAll(/<button\b[^>]*>/gi)).map(match => attrs(match[0])).filter(a => Object.hasOwn(a, "data-brief-compose"));
  check(item.file + ": composer cannot submit without JavaScript", compose.length === 1 && compose[0].type === "button" && Object.hasOwn(compose[0], "disabled"));
  check(item.file + ": no native submit button", !Array.from(form.matchAll(/<button\b[^>]*>/gi)).map(match => attrs(match[0])).some(a => !a.type || a.type === "submit"));
  const preview = fields.filter(field => Object.hasOwn(field.attributes, "data-brief-preview"));
  check(item.file + ": readonly preview cannot enter form payload", preview.length === 1 && /^<textarea\b/i.test(preview[0].raw) && Object.hasOwn(preview[0].attributes, "readonly") && !preview[0].attributes.name);
  const links = Array.from(form.matchAll(/<a\b[^>]*>/gi)).map(match => attrs(match[0])).filter(a => Object.hasOwn(a, "data-brief-whatsapp"));
  check(item.file + ": no stale WhatsApp URL before binding", links.length === 1 && !Object.hasOwn(links[0], "href"));
  const output = Array.from(form.matchAll(/<[^/>][^>]*>/g)).map(match => attrs(match[0])).filter(a => Object.hasOwn(a, "data-brief-output"));
  check(item.file + ": generated panel starts hidden", output.length === 1 && Object.hasOwn(output[0], "hidden"));
  const copy = Array.from(form.matchAll(/<button\b[^>]*>/gi)).map(match => attrs(match[0])).filter(a => Object.hasOwn(a, "data-brief-copy"));
  check(item.file + ": copy action is a button", copy.length === 1 && copy[0].type === "button");
  const status = Array.from(form.matchAll(/<[^/>][^>]*>/g)).map(match => attrs(match[0])).filter(a => Object.hasOwn(a, "data-brief-status"));
  check(item.file + ": accessible status", status.length === 1 && status[0].id && status[0]["aria-live"] === "polite");
  const scripts = Array.from(html.matchAll(/<script\b[^>]*>/gi)).map(match => attrs(match[0])).filter(a => a.src === "/assets/ui/brief.js");
  check(item.file + ": deferred module present once", scripts.length === 1 && Object.hasOwn(scripts[0], "defer"));
  check(item.file + ": legacy handler removed", !html.includes('id="' + item.legacy + '"') && !html.includes("generate_lead"));
  check(item.file + ": no-JavaScript alternative", /<p\b[^>]*class="brief-nojs"[^>]*>[\s\S]*?href=["']https:\/\/wa\.me\/6285340382029["'][\s\S]*?<\/p>[\s\S]*?<noscript>/i.test(form));
}
console.log(JSON.stringify({ passed, failed: 0, scope: "static HTML guards; not a browser test" }));
