"""Focused cloud PHP 8.3 gate; public renderers isolated from API/config and outbound IO."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public_html"
PINNED = {
    "api.php": "7636175d2ad602a7ac5265ec51dfab90acb4a0f4",
    "content.php": "1b8eead561f35714a32ae9ae22e0a76a6b61f636",
    "includes/config.php": "e4e2d2584febaa16f6503031759a2fa1ffc00c71",
    "includes/tracking-query.php": "5faa1c8e1927eecf74256c754640b94f05ca3b4d",
    "portfolio.php": "e698dc73c16e8216ed681da4a75cf15f5ffa6d28",
    "seo.php": "d3c2480a068066ee2585245581e542cb9e7665d6",
    "sitemap.php": "f977ecd3e00da93c63674f2580534168bb917c2c",
    "test-seo.php": "b70f7939fd71e234660bade22ae5170bdbcc93a1",
}
CMS = {
    "cms/neon_box_pilot.php": "6df25d8cfcd96fd543327df0d8e8e48960d9f516",
    "tests/cms-offline-pilot.php": "bec1d695dbc94463e38ebee4bac5cb95e86406f3",
}
DISABLED = (
    "curl_exec,curl_multi_exec,fsockopen,pfsockopen,stream_socket_client,stream_socket_server,"
    "socket_create,socket_connect,socket_send,socket_sendto,mail,exec,shell_exec,system,passthru,"
    "popen,proc_open,file_put_contents,unlink,rename,copy,mkdir,rmdir,touch,chmod,chown"
)
ROUTER = r"""<?php
error_reporting(E_ALL);
set_error_handler(function($level) { throw new ErrorException('isolated PHP diagnostic',0,$level); });
$_POST=[]; $_FILES=[]; chdir(__DIR__);
try {
    $path=parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH);
    $key=strtolower(rtrim($path,'/'));
    $index=json_decode(file_get_contents(__DIR__.'/includes/content-index.json'),true);
    if (isset($index['routes'][$key]) || isset($index['aliases'][$key])) {
        require __DIR__.'/content.php';
    } elseif (preg_match('~^/layanan/~i',$path) || $path==='/seo.php') {
        require __DIR__.'/seo.php';
    } elseif ($path==='/sitemap.xml' || preg_match('~^/sitemap-([a-z]+)\.xml$~',$path,$match)) {
        if (isset($match[1])) $_GET['bagian']=$match[1];
        require __DIR__.'/sitemap.php';
    } elseif ($path==='/portfolio.php') {
        require __DIR__.'/portfolio.php';
    } elseif ($path==='/test-seo.php') {
        /* Synthetic config only; this diagnostic is denied by production .htaccess. */
        require __DIR__.'/test-seo.php';
    } else {
        $entry=null;
        foreach ($index['groups']['utama'] as $candidate) if ($candidate['path']===$path) $entry=$candidate;
        if ($entry && str_ends_with($entry['file'],'.html')) {
            header('Content-Type: text/html; charset=UTF-8'); readfile(__DIR__.'/'.$entry['file']);
        } else require __DIR__.'/content.php';
    }
} catch (Throwable $error) {
    http_response_code(500); echo 'Isolated PHP diagnostic';
}
"""
results = []
coverage = {}
audit = None

def require(ok, category):
    if not ok:
        raise RuntimeError(category)

def safe(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing or unsafe source")
    return path

def digest_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def run_checked(command, *, env=None, cwd=None, timeout=30):
    process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    require(process.returncode == 0, "cloud process failed; raw diagnostics withheld")
    require(not process.stderr, "PHP warning/deprecation or process diagnostic")
    return process.stdout

def case(name, fn):
    try:
        fn()
        results.append({"name": name, "status": "PASS"})
    except Exception as error:
        # Case/category only; do not print source/config/error excerpts.
        results.append({"name": name, "status": "FAIL", "category": type(error).__name__})
        raise

def request(port, target):
    require(target.startswith("/") and not target.startswith("//"), "unsafe local target")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("GET", target, headers={"Host": "www.3dkanadvertising.store"})
        response = connection.getresponse()
        payload = response.read(4_000_001)
        require(len(payload) <= 4_000_000, "response bound")
        return response.status, {k.lower(): v for k, v in response.getheaders()}, payload
    finally:
        connection.close()

def copy_fixture(site, index):
    selected = {"content.php","seo.php","sitemap.php","portfolio.php","test-seo.php",
                "includes/tracking-query.php","includes/content-index.json",
                "includes/refresh-data.json","includes/refresh-header.html",
                "includes/refresh-footer.html","404.html"}
    for route in index["routes"].values():
        relative = route["file"]
        require(relative.startswith("includes/content-v2/") and relative.endswith(".html"), "route manifest containment")
        selected.add(relative)
    for entries in index["groups"].values():
        for entry in entries:
            for relative in entry["lastmod_files"]:
                require(".." not in Path(relative).parts and not Path(relative).is_absolute(), "lastmod manifest containment")
                selected.add(relative)
    for relative in selected:
        require(relative not in {"api.php","includes/config.php"}, "sensitive runtime source cannot enter fixture")
        source = safe(PUBLIC / relative)
        require(source.resolve().is_relative_to(PUBLIC.resolve()), "source escaped public root")
        target = site / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # Never copy actual includes/config.php or api.php into the executable fixture.
    (site / "includes/config.php").write_text(
        "<?php $config=['site_url'=>'https://example.invalid'];"
        "$produk=['neon-box'=>['name'=>'Synthetic product']];"
        "$kota_sulsel=['synthetic-city'=>'Synthetic city'];\n", encoding="ascii")
    (site / "router.php").write_text(ROUTER, encoding="ascii")
    photos = site / "foto-produk"
    (photos / "nested").mkdir(parents=True)
    for relative in ["one.jpg","nested/two.WEBP","nested/ignored.txt"]:
        (photos / relative).write_bytes(b"Synthetic bytes")
    return selected

def main():
    global audit
    php = shutil.which("php")
    require(php is not None, "PHP CLI unavailable")
    version = json.loads(run_checked([php, "-r",
        "echo json_encode(['version'=>PHP_VERSION,'id'=>PHP_VERSION_ID,'sapi'=>PHP_SAPI]);"]))
    require(80300 <= version["id"] < 80400 and version["sapi"] == "cli", "exact PHP8.3 CLI required")
    env = {k: os.environ[k] for k in ("PATH","HOME","LANG","RUNNER_TEMP") if k in os.environ}
    index = json.loads(safe(PUBLIC / "includes/content-index.json").read_bytes())
    data = json.loads(safe(PUBLIC / "includes/refresh-data.json").read_bytes())

    def integrity():
        actual = {str(p.relative_to(PUBLIC)) for p in PUBLIC.rglob("*.php")}
        require(actual == set(PINNED), "public PHP inventory changed; review required")
        for relative, sha in PINNED.items():
            require(digest_blob(safe(PUBLIC / relative).read_bytes()) == sha, "public PHP source drift")
        for relative, sha in CMS.items():
            require(digest_blob(safe(ROOT / relative).read_bytes()) == sha, "CMS source drift")
    case("Pinned full public PHP and offline CMS inventory", integrity)

    def parse_audit():
        global audit
        payload = run_checked([php, str(ROOT / "scripts/php83_source_audit.php"), str(ROOT)], env=env)
        audit = json.loads(payload)
        require(len(audit["files"]) == 9 and not audit["issues"], "source audit blocker")
        require(not any(entry["unresolved_function_names"] for entry in audit["files"]), "unavailable direct function dependency")
        required = {"Core","json","pcre","hash","filter","tokenizer"}
        require(required.issubset(set(audit["loaded_extensions"])), "required PHP extensions absent")
        for relative in list(PINNED) + list(CMS):
            lint = subprocess.run([php,"-d","error_reporting=-1","-d","display_errors=stderr",
                "-d","log_errors=0","-l",str((PUBLIC if relative in PINNED else ROOT) / relative)],
                capture_output=True, env=env, timeout=10)
            require(lint.returncode == 0 and not lint.stderr, "PHP83 parse/deprecation failure")
    case("PHP8.3 full source lint and redacted dependency/removal audit", parse_audit)

    temporary_base = os.environ.get("RUNNER_TEMP")
    with tempfile.TemporaryDirectory(prefix="php83-render-", dir=temporary_base) as folder:
        site = Path(folder) / "site"
        site.mkdir(mode=0o700)
        selected = copy_fixture(site, index)
        before = {relative: hashlib.sha256((site / relative).read_bytes()).hexdigest()
                  for relative in selected}
        bind = socket.socket()
        bind.bind(("127.0.0.1",0))
        port = bind.getsockname()[1]
        bind.close()
        server = subprocess.Popen([php,"-d","allow_url_fopen=0","-d","allow_url_include=0",
            "-d","display_errors=0","-d","log_errors=0","-d","error_reporting=-1",
            "-d","disable_functions="+DISABLED,"-S","127.0.0.1:"+str(port),
            "-t",str(site),str(site / "router.php")], cwd=site, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            ready = False
            for _ in range(60):
                require(server.poll() is None, "isolated PHP server exited")
                try:
                    status, _, _ = request(port, "/")
                    ready = status == 200
                    if ready: break
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(0.05)
            require(ready, "isolated PHP server unavailable")

            def all_routes():
                require(len(index["routes"]) == 485, "reviewed content route count changed")
                for route, entry in index["routes"].items():
                    status, headers, body = request(port, route)
                    require(status == 200, "content renderer status")
                    require(body == (site / entry["file"]).read_bytes(), "content renderer byte mismatch")
                    require(headers.get("content-language") == "id"
                            and headers.get("x-content-type-options") == "nosniff", "content headers")
                coverage["content_routes"] = len(index["routes"])
            case("All 485 registry content routes serve exact immutable HTML", all_routes)

            def services():
                require(len(data["services"]) == 7, "reviewed service count changed")
                spec = importlib.util.spec_from_file_location("service_check", ROOT / "scripts/service_content_check.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for slug in data["services"]:
                    status, _, body = request(port,"/layanan/"+slug)
                    require(status == 200 and b"<h1" in body, "service renderer")
                    text = body.decode("utf-8")
                    require(text.count("<h1") == 1 and 'rel="canonical" href="'+data["domain"]+"/layanan/"+slug+'"' in text,
                            "service canonical/heading")
                    if slug == "neon-box":
                        module.verify_service_content(body,data["services"][slug],domain=data["domain"],slug=slug)
                coverage["services"] = len(data["services"])
            case("Seven actual service renderers including NEON metadata/schema contract", services)

            def redirects():
                for alias, target in index["aliases"].items():
                    status, headers, body = request(port, alias+"?utm_source=qa%20source&private_ignored=synthetic")
                    require(status == 301 and body == b""
                            and headers.get("location") == index["domain"]+target+"?utm_source=qa%20source", "content alias redirect")
                route = next(iter(index["routes"]))
                status, headers, _ = request(port, route.upper()+"/?utm_medium=synthetic")
                require(status == 301 and headers.get("location") == index["domain"]+route+"?utm_medium=synthetic", "canonical content redirect")
                for target, expected in [
                    ("/layanan/neon-box/makassar?utm_source=synthetic&produk=ignored",
                     data["domain"]+"/kota/makassar?utm_source=synthetic#layanan-neon-box"),
                    ("/seo.php?produk=neon-box&utm_source=synthetic",
                     data["domain"]+"/layanan/neon-box?utm_source=synthetic")]:
                    status, headers, body = request(port,target)
                    require(status == 301 and body == b"" and headers.get("location") == expected, "SEO canonical redirect")
                coverage["redirect_cases"] = len(index["aliases"]) + 3
            case("Actual alias/service redirects preserve bounded attribution only", redirects)

            def invalid_inputs():
                for target in ["/layanan/unknown","/seo.php?produk[]=neon-box",
                               "/seo.php?produk=neon-box&kota[]=makassar","/unreviewed-route"]:
                    status, headers, body = request(port,target)
                    require(status == 404 and headers.get("x-robots-tag") == "noindex, follow"
                            and body == (site / "404.html").read_bytes(), "invalid public input")
                status, _, _ = request(port,"/sitemap.xml?bagian[]=utama")
                require(status == 404, "sitemap array parameter")
            case("Array/unknown route rejection emits no PHP8.3 diagnostic", invalid_inputs)

            def sitemaps():
                ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
                status, headers, body = request(port,"/sitemap.xml")
                require(status == 200 and "application/xml" in headers.get("content-type",""), "sitemap index")
                document = ET.fromstring(body)
                require(document.tag == ns+"sitemapindex" and len(document) == 10, "sitemap index count")
                total = 0
                for group, entries in index["groups"].items():
                    status, _, body = request(port,"/sitemap-"+group+".xml")
                    require(status == 200, "sitemap part")
                    document = ET.fromstring(body)
                    found = [entry.find(ns+"loc").text for entry in document]
                    require(found == [index["domain"]+entry["path"] for entry in entries], "sitemap exact registry")
                    total += len(found)
                require(total == 500, "sitemap public URL count")
                coverage["sitemap_documents"] = 11
                coverage["sitemap_urls"] = total
            case("Actual eleven sitemap renders contain exact 500 URL registry", sitemaps)

            def static_pages():
                require(len(index["groups"]["utama"]) == 8, "static public count")
                for entry in index["groups"]["utama"]:
                    status, _, body = request(port, entry["path"])
                    require(status == 200 and body == (site / entry["file"]).read_bytes(), "static fixture bytes")
                coverage["static_pages"] = 8
            case("Eight primary static pages remain byte-identical in isolated fixture", static_pages)

            def synthetic_legacy():
                status, _, body = request(port,"/portfolio.php")
                require(status == 200 and sorted(json.loads(body)) == ["nested/two.WEBP","one.jpg"], "synthetic portfolio enumeration")
                status, _, body = request(port,"/test-seo.php")
                require(status == 200 and b"Total: 4 halaman" in body and b"Synthetic city" not in body,
                        "synthetic diagnostic renderer")
            case("Legacy portfolio enumeration and denied diagnostic with synthetic config only", synthetic_legacy)

            def no_mutation():
                require(before == {relative: hashlib.sha256((site / relative).read_bytes()).hexdigest()
                                   for relative in selected}, "fixture source mutated")
                require(not (site / "api.php").exists(), "API accidentally executable")
                require((site / "includes/config.php").read_text().startswith("<?php $config=['site_url'=>'https://example.invalid'];"),
                        "actual runtime config copied")
            case("Read-only renderer fixture and external/API exclusion", no_mutation)
        finally:
            server.terminate()
            try: server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)

    return version

if __name__ == "__main__":
    runtime = None
    try:
        runtime = main()
    except Exception as error:
        if not results or results[-1]["status"] != "FAIL":
            results.append({"name":"Compatibility runner setup","status":"FAIL","category":type(error).__name__})
    output = ROOT / "artifacts/php83-compatibility/results.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    report = {
        "candidate_sha": os.environ.get("PHP83_CANDIDATE_SHA","UNKNOWN"),
        "runtime": runtime, "results": results, "coverage": coverage, "source_audit": audit,
        "reused_evidence": {"offline_cms": {"run": 38351847581, "candidate_sha": "c073b6cfc480719cc0034415c1c31160eea43ab8", "php_version": "8.3.6", "passed": 49, "failed": 0, "library_and_test_blobs_verified_unchanged": True}},
        "not_run": [
            "Actual hosting PHP handler/extension/INI parity and permissions",
            "Public API/config runtime, database/mail/auth integrations and real form sends",
            "Apache rewrite behavior; fixture follows the existing reviewed route precedence",
            "CMS hosting activation/authentication; CMS remains offline/inactive"
        ]
    }
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":sum(r["status"]=="PASS" for r in results),
        "failed":sum(r["status"]=="FAIL" for r in results),"coverage":coverage,
        "runtime":runtime,"result_file":"artifacts/php83-compatibility/results.json"},indent=2))
    raise SystemExit(1 if any(r["status"]=="FAIL" for r in results) else 0)
