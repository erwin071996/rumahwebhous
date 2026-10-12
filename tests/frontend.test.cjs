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
  assert.equal(hash(js), "e7ee2c7edb830a658623a60004f950f3cb3eacd92d0a40b90794192fdde497a9", "Reviewed controller bytes changed");
  assert.equal(hash(css), "f124f0f247e7f0300e7dd98ff333c5048772c59d6171046a725f95511cf2e7f8", "Reviewed CSS bytes changed");
  assert.equal(hash(harness), "4e4f8457dde4e218098735238671d8c44d46efc603974de82bd330c98019af9a", "Reviewed harness bytes changed");
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
  assert.equal(result.passed, 50, "Expected reviewed regression suite");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
