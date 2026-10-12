"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");
const { runFrontendControllerTests } = require("./frontend-controller-harness.cjs");
const root = path.resolve(__dirname, "../public_html");
function hash(content) { return crypto.createHash("sha256").update(content).digest("hex"); }
async function main() {
  const js = fs.readFileSync(path.join(root, "assets/ui/frontend.js"), "utf8");
  const css = fs.readFileSync(path.join(root, "assets/ui/frontend.css"), "utf8");
  const harness = fs.readFileSync(path.join(__dirname, "frontend-controller-harness.cjs"), "utf8");
  assert.equal(hash(js), "e2a55d98273daabe61b3636e2bf8ee50bc0ca6bad86e6da075c7ac3cce4ed971", "Reviewed controller bytes changed");
  assert.equal(hash(css), "15cb99e7acd5aa9ab8a08764b0b98d89ddb8cf04bf0ff6f757007a70400c9908", "Reviewed CSS bytes changed");
  assert.equal(hash(harness), "85b9b4a0de644a4b2b7440e749167b23922e06c80ef6c0bb60f1ca480c1b4b92", "Reviewed harness bytes changed");
  for (const name of ["index.html", "projects.html"]) {
    const html = fs.readFileSync(path.join(root, name), "utf8");
    const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), m => m[1]);
    assert.equal(new Set(ids).size, ids.length, name + ": duplicate IDs");
    for (const match of html.matchAll(/\bhref="#([^"]+)"/g)) assert.ok(ids.includes(match[1]), name + ": missing local anchor " + match[1]);
    for (const source of ["/assets/marketing-20261006/site.js", "/assets/marketing-20261006/tools.js", "/assets/ui/frontend.js", "/assets/ui/brief.js"]) {
      assert.equal(Array.from(html.matchAll(/\bsrc="([^"]+)"/g)).filter(m => m[1] === source).length, 1, name + ": script dependency must remain exactly once");
    }
    assert.ok(!html.includes('id="client-tools-js"') && !html.includes('id="real-portfolio-js"'), name + ": legacy controller must not duplicate listeners");
  }
  const result = await runFrontendControllerTests(js);
  console.log(JSON.stringify(result, null, 2));
  assert.equal(result.failed, 0, "Controller stub failed");
  assert.equal(result.passed, 39, "Expected reviewed regression suite");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
