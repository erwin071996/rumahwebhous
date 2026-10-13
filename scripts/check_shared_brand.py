"""Focused SharedBrand preservation gate. Read-only; no hosting/network/runtime secrets."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import copy
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE_SHA = "dd31d7305d1571b4fde960ed0b942135a88388a1"
R6_SHA = "0f2137981e0b5e6eea0e3ac5899266a0f59ced724090d5ad4b0b504dbddef828"
CSS_SHA = "66a28499c514cb36c4e43ef1bad89782f963a5bf93146fa81f7370f7e85fef74"
GROUP_COUNTS = {"utama":8,"layanan":7,"wilayah":24,"produk":9,"panduan":12,"tutorial":400,"topik":20,"alat":14,"toko":3,"informasi":3}
FROZEN = (
 "includes/content-index.json", "includes/refresh-data.json", "content.php",
 "assets/ui/frontend.js", "assets/ui/frontend.css", "assets/ui/brief.js", "assets/ui/brief.css", "assets/ui/theme.css",
 "assets/branding/logo-3dkan-original.jpg", "assets/branding/logo-3dkan-688.webp",
 "assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
 "assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
)
ASSET_PATH = re.compile(r"/assets/(?:ui/(?:brand-tokens|design-system|frontend)\.css|ui/frontend\.js)(?:\?v=[a-f0-9]{16,64})?")
BRAND_LINK = re.compile(r'<link\b[^>]*href=["\'](/assets/ui/(?:brand-tokens|design-system)\.css(?:\?v=[a-f0-9]{16,64})?)["\'][^>]*>\s*', re.I)
FRONTEND_SCRIPT = re.compile(r'<script\b[^>]*src=["\']/assets/ui/frontend\.js(?:\?v=[a-f0-9]{16,64})?["\'][^>]*>\s*</script>\s*', re.I)
LEGACY_VERSIONS = {
 "/assets/marketing-20261006/site.js":"baf0918036519d5d847d41ee812c5f7823823a41158973d999e9ce317cfa0c5d",
 "/assets/refresh-20261006/site-v2.js":"16cf9ec47fb3d251b3439eaf717f9c9e67abe58a5eb21f8d0027bc82f27b27b4",
 "/assets/refresh-20261006/site.js":"75c087398bf581cba22e65d75a86c76e612459e9be394a613d408f5f73c910b1",
}
MAIN = re.compile(r"<main\b[^>]*>.*?</main\s*>", re.I | re.S)
HEAD = re.compile(r"<head\b[^>]*>(.*?)</head\s*>", re.I | re.S)
STYLE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.I | re.S)
LD = re.compile(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script\s*>', re.I | re.S)

class Gate:
 def __init__(self):
  self.checks = []
 def require(self, condition, name, file=None):
  self.checks.append({"name":name,"status":"PASS" if condition else "FAIL", **({"path":file} if file else {})})
 def equal(self, left, right, name, file=None):
  self.require(left == right, name, file)

def source(root, name):
 path = (root / name).resolve()
 if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
  raise ValueError("Unsafe/missing source path: " + name)
 return path.read_text(encoding="utf-8", errors="strict")

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def one(pattern, text, label):
 matches = pattern.findall(text)
 if len(matches) != 1:
  raise ValueError(label + " cardinality")
 return matches[0]

def normalized_head(text):
 head = one(HEAD, text, "head")
 head = re.sub(r"<!-- SharedBrand:head -->.*?<!-- /SharedBrand:head -->", "", head, flags=re.S)
 head = BRAND_LINK.sub("", head)
 head = FRONTEND_SCRIPT.sub("", head)
 head = head.replace("<?php kan_shared_head(); ?>", "")
 for url,sha in LEGACY_VERSIONS.items():
  head=head.replace(url+"?v="+sha[:16],url)
 return head.strip()

def accessible_main(text):
 main=one(MAIN,text,"main")
 opening=re.match(r"<main\b[^>]*>",main,re.I).group()
 if not re.search(r"\btabindex\s*=",opening,re.I):
  main=opening[:-1]+' tabindex="-1">'+main[len(opening):]
 return main


APPROVED_CONTENT_PATH = "tests/fixtures/projects-approved-content.json"
APPROVED_CONTENT_SHA = "dcef03b2601f61bb80a9b3de2a3480fba1cae2e2da74780737ce5bbd1b388110"

def approved_service_data(raw, approval):
 spec = approval.get("service_data")
 if not isinstance(spec,dict) or spec.get("path") != "public_html/includes/refresh-data.json" or spec.get("service") != "huruf-timbul" or len(spec.get("operations",[])) != 1:
  raise ValueError("Unexpected approved service data contract")
 identity = spec["candidate"]
 git_blob = hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()
 if len(raw) != identity["bytes"] or hashlib.sha256(raw).hexdigest() != identity["sha256"] or git_blob != identity["git_blob"]:
  raise ValueError("Approved service data identity mismatch")
 rendered = raw.decode("utf-8",errors="strict")
 operation = spec["operations"][0]
 if rendered.count(operation["new"]) != 1:
  raise ValueError("Approved service data cardinality")
 restored = rendered.replace(operation["new"],operation["old"],1).encode("utf-8")
 before = spec["baseline"]
 old_blob = hashlib.sha1(b"blob "+str(len(restored)).encode("ascii")+b"\0"+restored).hexdigest()
 if len(restored) != before["bytes"] or hashlib.sha256(restored).hexdigest() != before["sha256"] or old_blob != before["git_blob"]:
  raise ValueError("Approved service data restoration mismatch")
 original, current = json.loads(restored), json.loads(raw)
 expected = copy.deepcopy(original)
 record = expected["services"]["huruf-timbul"]
 editorial = spec["editorial"]
 if set(editorial) != {"seo_title","seo_description","detail_sections"} or any(key in record for key in editorial) or len(record) != 7:
  raise ValueError("Approved service fields changed")
 record.update(editorial)
 if current != expected or len(current["services"]) != 7:
  raise ValueError("Approved service/global semantic preservation failed")
 return restored

def content_approval(repo):
 path = repo / APPROVED_CONTENT_PATH
 if not path.resolve().is_relative_to(repo.resolve()) or not path.is_file() or path.is_symlink() or digest(path) != APPROVED_CONTENT_SHA:
  raise ValueError("Approved Projects content identity mismatch")
 approval = json.loads(path.read_text(encoding="ascii"))
 if approval.get("schema_version") != 1 or approval.get("path") != "public_html/projects.html" or approval.get("baseline_commit") != BASE_SHA or len(approval.get("operations", [])) != 3:
  raise ValueError("Unexpected approved Projects content contract")
 inputs = json.loads(source(repo, "config/shared-brand-inputs.json"))
 rows = [entry for entry in inputs["files"] if entry["path"] == approval["path"]]
 identity = approval["candidate"]
 if len(rows) != 1 or rows[0]["git_blob"] != identity["git_blob"] or rows[0]["bytes"] != identity["bytes"]:
  raise ValueError("Projects managed input does not match approved content")
 manifest = json.loads(source(repo, "docs/shared-brand-build.json"))
 outputs = [entry for entry in manifest["outputs"] if entry["path"] == approval["path"]]
 modules = [entry for entry in manifest["managed_sources"] if entry["path"] == approval["path"]]
 if len(outputs) != 1 or any(outputs[0][key] != identity[key] for key in ("git_blob", "bytes", "sha256")):
  raise ValueError("Projects managed output does not match approved content")
 if len(modules) != 1 or any(modules[0][key] != identity[key] for key in ("main_sha256", "pre_main_sha256")):
  raise ValueError("Projects main/module identity does not match approved content")
 data_path = repo / "public_html/includes/refresh-data.json"
 if not data_path.is_file() or data_path.is_symlink() or not data_path.resolve().is_relative_to(repo.resolve()):
  raise ValueError("Unsafe approved service data path")
 approved_service_data(data_path.read_bytes(), approval)
 return approval

def expected_main(name, text, approval):
 expected = accessible_main(text)
 if name != "projects.html":
  return expected
 if hashlib.sha256(expected.encode("utf-8")).hexdigest() != approval["normalized_main"]["before_sha256"]:
  raise ValueError("Projects baseline main identity mismatch")
 for operation in approval["operations"]:
  if expected.count(operation["old"]) != 1:
   raise ValueError("Approved Projects operation cardinality")
  expected = expected.replace(operation["old"], operation["new"], 1)
 if hashlib.sha256(expected.encode("utf-8")).hexdigest() != approval["normalized_main"]["after_sha256"]:
  raise ValueError("Projects approved main identity mismatch")
 return expected

def pre_main_gap(text):
 matches=re.findall(r"</header\s*>(.*?)<main\b",text,re.I|re.S)
 if len(matches)!=1: raise ValueError("Pre-main module gap cardinality")
 value=matches[0]
 marker="\n<!-- /SharedBrand:header -->"
 if value.startswith(marker): value=value[len(marker):]
 if "/SharedBrand:header" in value: raise ValueError("Unexpected header marker in module gap")
 return value

def registry(root):
 return json.loads(source(root, "includes/content-index.json"))

def run(baseline, candidate, approval):
 gate = Gate()
 before, after = registry(baseline), registry(candidate)
 gate.equal(before, after, "entire 500-route registry and lastmod preserved", "includes/content-index.json")
 expected = {k:len(v) for k,v in before["groups"].items()}
 gate.equal(expected, GROUP_COUNTS, "baseline family counts")
 entries = [dict(entry, family=family) for family, group in before["groups"].items() for entry in group]
 paths = [entry["path"] for entry in entries]
 gate.require(len(paths) == len(set(paths)) == 500 and len(before["routes"]) == 485, "500 unique URLs and 485 routed documents")
 files = sorted({entry["file"] for entry in entries} | {"404.html"})
 for name in files:
  old, new = source(baseline, name), source(candidate, name)
  gate.equal(expected_main(name, old, approval), one(MAIN, new, "main"), "main bytes preserve exact approved focus/content operations", name)
  if name == "projects.html":
   gate.equal(digest(candidate / name), approval["candidate"]["sha256"], "entire Projects candidate is the approved immutable content blob", name)
  gate.equal(normalized_head(old), normalized_head(new), "head metadata, canonical, schemas and original dependencies preserved", name)
  old_head=one(HEAD,old,"baseline head");new_head=one(HEAD,new,"candidate head")
  for url,sha in LEGACY_VERSIONS.items():
   old_count=len(re.findall(r'<script\b[^>]*\bsrc=["\']'+re.escape(url)+r'["\']',old_head,re.I))
   if old_count:
    versioned_count=len(re.findall(r'<script\b[^>]*\bsrc=["\']'+re.escape(url+"?v="+sha[:16])+r'["\']',new_head,re.I))
    gate.equal(versioned_count,old_count,"existing legacy script uses exact approved content-version URL",name)
  gate.equal(STYLE.findall(old), STYLE.findall(new), "inline family styles preserved", name)
  gate.equal(LD.findall(old), LD.findall(new), "business and editorial JSON-LD preserved", name)
  gate.require(bool(re.search(r'<body\b[^>]*\bclass=["\'][^"\']*\bkan-site\b', new)), "shared opt-in body", name)
  if name == "seo.php":
   expected=old
   operations=[
    ("require_once __DIR__ . '/includes/tracking-query.php';","require_once __DIR__ . '/includes/tracking-query.php';\nrequire_once __DIR__ . '/includes/shared-brand.php';"),
    ("function wa_link($message) { return 'https://wa.me/6285340382029?text=' . rawurlencode($message); }","function wa_link($message) { return kan_shared_whatsapp($message); }"),
    ("</head><body><?php readfile(__DIR__.'/includes/refresh-header.html'); ?>","<?php kan_shared_head(); ?>\n</head><body class=\"kan-site\"><?php kan_shared_header(parse_url($canonical, PHP_URL_PATH)); ?>"),
    ("<?php readfile(__DIR__.'/includes/refresh-footer.html'); ?>","<?php kan_shared_footer(); ?>"),
    ('<main id="main">','<main id="main" tabindex="-1">'),
    ('<script src="/assets/marketing-20261006/site.js" defer>','<script src="/assets/marketing-20261006/site.js?v=baf0918036519d5d" defer>'),
   ]
   for old_segment,new_segment in operations:
    if expected.count(old_segment) != 1: raise ValueError("SEO baseline binding segment cardinality")
    expected=expected.replace(old_segment,new_segment,1)
   gate.equal(expected,new,"only six exact shared PHP/focus/version bindings; redirects and renderer logic unchanged",name)
  for marker in ("SharedBrand:header", "SharedBrand:footer"):
   if name != "seo.php":
    gate.require(marker in new, "shared generated shell marker", name)
  if name != "seo.php":
   gate.equal(pre_main_gap(old),pre_main_gap(new),"pre-main non-shell modules preserve exact bytes/IDs/attributes",name)
   gate.require(len(BRAND_LINK.findall(new)) == 2 and len(FRONTEND_SCRIPT.findall(new)) == 1, "single generated tokens, design CSS and R6 controller", name)
 for name in FROZEN:
  if name == "includes/refresh-data.json":
   restored = approved_service_data((candidate / name).read_bytes(), approval)
   gate.equal(restored,(baseline / name).read_bytes(),"only three exact approved Huruf editorial fields; seven original fields, six services and global data preserved",name)
  else:
   gate.equal(digest(baseline / name), digest(candidate / name), "frozen public module/data/master bytes", name)
 exceptions={"assets/marketing-20261006/site.js","assets/refresh-20261006/site-v2.js","assets/refresh-20261006/site.js"}
 for old in sorted((baseline/"assets").rglob("*")):
  if old.is_file():
   name=old.relative_to(baseline).as_posix()
   if name not in exceptions: gate.equal(digest(old),digest(candidate/name),"original assets preserved",name)
 gate.equal(digest(candidate / "assets/ui/frontend.js"), R6_SHA, "canonical R6 source")
 css = source(candidate, "assets/ui/design-system.css")
 gate.equal(hashlib.sha256(css.encode()).hexdigest(), CSS_SHA, "canonical frontend CSS transfer")
 gate.require(len(css.encode()) == 12437 and "&gt;" not in css and "&amp;" not in css and " > " in css, "CSS selectors are actual characters, not transport entities")
 for name in ("assets/marketing-20261006/site.js","assets/refresh-20261006/site-v2.js","assets/refresh-20261006/site.js"):
  old, new = source(baseline,name),source(candidate,name)
  width = "761" if name == "assets/refresh-20261006/site.js" else "961"
  segment = "    window.matchMedia('(min-width:"+width+"px)').addEventListener('change',closeMenu);"
  replacement = "    if (document.body.classList.contains('kan-site')) document.body.classList.add('kan-nav-ready');\n    else window.matchMedia('(min-width:"+width+"px)').addEventListener('change',closeMenu);"
  gate.require(old.count(segment) == 1 and new == old.replace(segment,replacement,1), "only declared readiness/breakpoint ownership patch", name)
  gate.equal(digest(candidate/name),LEGACY_VERSIONS["/"+name],"legacy script bytes match URL version",name)
 return gate.checks

def build_fixture(gate, repo, baseline, approval):
 inputs=json.loads((repo/"config/shared-brand-inputs.json").read_text(encoding="utf-8"))
 manifest=json.loads((repo/"docs/shared-brand-build.json").read_text(encoding="utf-8"))
 selected={"config/site-brand.json","config/shared-brand-inputs.json","docs/shared-brand-build.json","public_html/assets/ui/design-system.css","public_html/assets/ui/frontend.js","public_html/assets/marketing-20261006/site.js","public_html/assets/refresh-20261006/site-v2.js","public_html/assets/refresh-20261006/site.js","public_html/includes/content-index.json","public_html/includes/refresh-data.json","templates/presentation/shared-header.html","templates/presentation/shared-footer.html","templates/presentation/shared-cta.html"}
 selected.update(entry["path"] for entry in inputs["files"])
 selected.update(entry["path"] for entry in manifest["outputs"])
 for rel in selected:
  if not re.fullmatch(r"(?:(?:config|docs|public_html)/[A-Za-z0-9_./-]+|templates/presentation/shared-(?:header|footer|cta)\.html)",rel) or ".." in Path(rel).parts or rel.endswith(("api.php","config.php")):
   raise ValueError("Unsafe fixture inventory path")
 with tempfile.TemporaryDirectory(prefix="shared-brand-acceptance-") as temporary:
  fixture=Path(temporary)
  for rel in selected:
   original=(repo/rel).resolve()
   if not original.is_relative_to(repo.resolve()) or original.is_symlink() or not original.is_file(): raise ValueError("Unsafe fixture source")
   target=fixture/rel
   target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(original,target)
  # Only the public logo files are needed by generator asset integrity validation.
  config_path=fixture/"config/site-brand.json"
  cfg=json.loads(config_path.read_text(encoding="utf-8"))
  logo=cfg["brand"]["logo_primary"]
  logo_paths=[logo["path"]]+([logo["screen_derivative"]["path"]] if logo.get("screen_derivative") else [])
  for url in logo_paths:
   if not re.fullmatch(r"/assets/branding/[A-Za-z0-9._-]+",url): raise ValueError("Unsafe fixture logo path")
   rel="public_html"+url
   target=fixture/rel
   target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(repo/rel,target)
  def build(use_baseline=False):
   command=[sys.executable,str(repo/"scripts/build_shared_brand.py"),"--repo",str(fixture)]
   if use_baseline: command.extend(["--baseline",str(baseline.parent)])
   completed=subprocess.run(command,capture_output=True,text=True,timeout=45,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
   if completed.returncode: raise ValueError("Synthetic fixture generator failed (diagnostic content intentionally not echoed)")
   m=json.loads((fixture/"docs/shared-brand-build.json").read_text(encoding="utf-8"))
   outputs={entry["path"]:digest(fixture/entry["path"]) for entry in m["outputs"]}
   return m,outputs
  first,one_output=build()
  second,two_output=build()
  gate.equal(first,second,"two managed builds have identical manifest")
  gate.equal(one_output,two_output,"two managed builds have identical output bytes")
  cfg["colors"]["primary"]="#0033cc"
  cfg["brand"]["logo_primary"]["alt"]="Synthetic SharedBrand acceptance logo"
  config_path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  changed,three_output=build()
  gate.require(first["config_sha256"]!=changed["config_sha256"],"single public config mutation changes version")
  before_registry=registry(baseline)
  families=set()
  for family,group in before_registry["groups"].items():
   for entry in group:
    if entry["file"]=="seo.php": continue
    rel="public_html/"+entry["file"]
    gate.require(one_output[rel]!=three_output[rel],"config mutation propagates to family page",entry["file"])
    text=(fixture/rel).read_text(encoding="utf-8")
    gate.require(text.count('alt="Synthetic SharedBrand acceptance logo"')==2,"both shell logos use one config",entry["file"])
    gate.equal(one(MAIN,text,"fixture main"),expected_main(entry["file"],source(baseline,entry["file"]),approval),"mutation preserves business main and exact approved focus/content operations",entry["file"])
    families.add(family)
  error_text=(fixture/"public_html/404.html").read_text(encoding="utf-8")
  gate.require(one_output["public_html/404.html"]!=three_output["public_html/404.html"] and error_text.count('alt="Synthetic SharedBrand acceptance logo"')==2,"error page consumes same public config")
  gate.equal(one(MAIN,error_text,"error main"),accessible_main(source(baseline,"404.html")),"mutation preserves error main and approved focus attribute")
  for rel in ("public_html/includes/refresh-header.html","public_html/includes/refresh-footer.html"):
   gate.require('alt="Synthetic SharedBrand acceptance logo"' in (fixture/rel).read_text(encoding="utf-8"),"service PHP fragment consumes same logo",rel)
  gate.equal(families,set(GROUP_COUNTS)-{"layanan"},"config mutation covers every static family")
  tokens=(fixture/"public_html/assets/ui/brand-tokens.css").read_text(encoding="utf-8")
  gate.require(bool(re.search(r"--kan-color-primary\s*:\s*#0033cc\s*;",tokens)),"changed color emitted once from public config")

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--baseline-dir",required=True,type=Path)
 p.add_argument("--candidate-dir",default=Path("public_html"),type=Path)
 p.add_argument("--output",type=Path)
 p.add_argument("--repo-dir",type=Path)
 p.add_argument("--skip-build-fixture",action="store_true")
 args=p.parse_args()
 try:
  repo = args.repo_dir or args.candidate_dir.parent
  approval = content_approval(repo)
  checks=run(args.baseline_dir,args.candidate_dir,approval)
  if not args.skip_build_fixture:
   gate=Gate()
   build_fixture(gate,repo,args.baseline_dir,approval)
   checks.extend(gate.checks)
 except Exception as error:
  checks=[{"name":"source gate setup","status":"FAIL","detail":str(error)}]
 report={"baselineSha":BASE_SHA,"candidateSha":__import__("os").environ.get("QA_CANDIDATE_SHA","UNKNOWN"),"checks":checks,"passed":sum(c["status"]=="PASS" for c in checks),"failed":sum(c["status"]=="FAIL" for c in checks),"limitations":["Read-only source preservation only; native rendering and visual inspection are separate.","No hosting credentials, private configuration or API source is read."]}
 if args.output:
  args.output.parent.mkdir(parents=True,exist_ok=True)
  args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:report[k] for k in ("baselineSha","candidateSha","passed","failed")},indent=2))
 for check in checks:
  if check["status"]=="FAIL": print(json.dumps(check))
 return int(report["failed"]>0)
if __name__=="__main__": sys.exit(main())
