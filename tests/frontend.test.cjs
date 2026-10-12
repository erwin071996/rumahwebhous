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
  assert.equal(hash(js), "55046a52fe7356287b9829f8cf15befac356a669bfcbd56346b3c2813f4534a6", "Reviewed controller bytes changed");
  assert.equal(hash(css), "af3558c60cba36d61eaa82878f72d8e4b577478d3ffdc62b2eb8a7825ab6a7ff", "Reviewed CSS bytes changed");
  assert.equal(hash(harness), "2d1e4b25f9194edc6a4091911cf6a3370aef12bd05f8fe52e8ce47e232617206", "Reviewed harness bytes changed");
  for (const name of ["index.html", "projects.html"]) {
    const html = fs.readFileSync(path.join(root, name), "utf8");
    const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), m => m[1]);
    assert.equal(new Set(ids).size, ids.length, name + ": duplicate IDs");
    for (const match of html.matchAll(/\bhref="#([^"]+)"/g)) assert.ok(ids.includes(match[1]), name + ": missing local anchor " + match[1]);
    for (const source of ["/assets/marketing-20261006/site.js", "/assets/marketing-20261006/tools.js", "/assets/ui/frontend.js", "/assets/ui/brief.js"]) {
      assert.equal(Array.from(html.matchAll(/\bsrc="([^"]+)"/g)).filter(m => m[1] === source).length, 1, name + ": script dependency must remain exactly once");
    }
    assert.ok(!html.includes('id="client-tools-js"') && !html.includes('id="real-portfolio-gallery-js"'), name + ": legacy controller must not duplicate listeners");
  }
  const result = await runFrontendControllerTests(js);
  console.log(JSON.stringify(result, null, 2));
  assert.equal(result.failed, 0, "Controller stub failed");
  assert.equal(result.passed, 32, "Expected reviewed regression suite");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
