"""Isolated read-only SharedBrand PHP previews; no hosting configuration or publisher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

ALLOWED_PHP = {"content.php", "seo.php", "sitemap.php", "portfolio.php",
               "includes/tracking-query.php", "includes/shared-brand.php"}
ROUTER = r"""<?php
error_reporting(E_ALL);
set_error_handler(function($level) { throw new ErrorException('Preview diagnostic',0,$level); });
$_POST=[]; $_FILES=[]; chdir(__DIR__);
if (!in_array($_SERVER['REQUEST_METHOD'], ['GET','HEAD'], true)) { http_response_code(405); exit; }
try {
    $path=parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH);
    $index=json_decode(file_get_contents(__DIR__.'/includes/content-index.json'),true);
    if (!is_array($index)) { http_response_code(503); exit; }
    if ($path==='/portfolio.php') { header('Content-Type: application/json'); echo '[]'; exit; }
    if (str_starts_with($path,'/assets/')) {
        $file=realpath(__DIR__.$path);
        if ($file && str_starts_with($file,__DIR__.'/assets/') && is_file($file) && !str_ends_with($file,'.php')) return false;
        http_response_code(404); exit;
    }
    $key=strtolower(rtrim($path,'/'));
    if (isset($index['routes'][$key]) || isset($index['aliases'][$key])) require __DIR__.'/content.php';
    elseif (str_starts_with($path,'/layanan/') || $path==='/seo.php') require __DIR__.'/seo.php';
    elseif ($path==='/sitemap.xml' || preg_match('~^/sitemap-([a-z]+)\\.xml$~',$path,$match)) {
        if (isset($match[1])) $_GET['bagian']=$match[1];
        require __DIR__.'/sitemap.php';
    } else {
        $entry=null;
        foreach ($index['groups']['utama'] as $candidate) if ($candidate['path']===$path) $entry=$candidate;
        if ($entry && str_ends_with($entry['file'],'.html')) {
            header('Content-Type: text/html; charset=UTF-8'); readfile(__DIR__.'/'.$entry['file']);
        } else require __DIR__.'/content.php';
    }
} catch (Throwable $error) { http_response_code(500); echo 'Preview route unavailable.'; }
"""
DISABLED="curl_exec,curl_multi_exec,fsockopen,pfsockopen,stream_socket_client,stream_socket_server,socket_create,socket_connect,socket_send,socket_sendto,mail,exec,shell_exec,system,passthru,popen,proc_open,file_put_contents,unlink,rename,copy,mkdir,rmdir,touch,chmod,chown"

def prepare(source, target):
    source=source.resolve()
    target.mkdir(mode=0o700)
    copied=0
    for file in sorted(source.rglob("*")):
        if file.is_symlink(): raise ValueError("Symlink preview source")
        if not file.is_file(): continue
        relative=file.relative_to(source).as_posix()
        if file.suffix.lower()==".php" and relative not in ALLOWED_PHP: continue
        if file.suffix.lower()==".mp4" or any(part.startswith(".") for part in file.relative_to(source).parts): continue
        if not file.resolve().is_relative_to(source): raise ValueError("Escaped preview source")
        destination=target/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(file,destination);copied+=1
    if (target/"api.php").exists() or (target/"includes/config.php").exists(): raise ValueError("Runtime source in preview")
    (target/"router.php").write_text(ROUTER,encoding="ascii")
    return copied


APPROVED_CONTENT_SHA = "50a11c45a1c741278148c4668099ca295efd3d6e9ba8ab9b24f84dd26f7bc506"

def apply_approved_projects(target):
    approval_path=Path(__file__).resolve().parent.parent/"tests/fixtures/projects-approved-content.json"
    if not approval_path.is_file() or approval_path.is_symlink() or hashlib.sha256(approval_path.read_bytes()).hexdigest()!=APPROVED_CONTENT_SHA:
        raise ValueError("Approved preview content identity mismatch")
    approval=json.loads(approval_path.read_text(encoding="ascii"))
    if approval.get("schema_version")!=1 or approval.get("path")!="public_html/projects.html" or len(approval.get("operations",[]))!=2:
        raise ValueError("Unexpected approved preview scope")
    file=target/"projects.html"
    raw=file.read_bytes()
    identity=approval["baseline_preview"]
    if len(raw)!=identity["before_bytes"] or hashlib.sha256(raw).hexdigest()!=identity["before_sha256"]:
        raise ValueError("Immutable baseline Projects preview mismatch")
    rendered=raw.decode("utf-8")
    for operation in approval["operations"]:
        if rendered.count(operation["old"])!=1:
            raise ValueError("Approved preview operation cardinality")
        rendered=rendered.replace(operation["old"],operation["new"],1)
    result=rendered.encode("utf-8")
    if len(result)!=identity["after_bytes"] or hashlib.sha256(result).hexdigest()!=identity["after_sha256"]:
        raise ValueError("Approved baseline preview result mismatch")
    file.write_bytes(result)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--candidate",type=Path)
    parser.add_argument("--baseline",type=Path)
    parser.add_argument("--approved-content",action="store_true",help="Apply only pinned approved content to the isolated baseline preview")
    parser.add_argument("--stop",type=Path)
    args=parser.parse_args()
    temporary=Path(os.environ["RUNNER_TEMP"]).resolve()
    if args.stop:
        file=args.stop.resolve()
        if not file.is_relative_to(temporary): raise ValueError("Unsafe preview state")
        state=json.loads(file.read_text())
        for pid in state["pids"]:
            try: os.kill(int(pid),signal.SIGTERM)
            except ProcessLookupError: pass
        folder=Path(state["folder"]).resolve()
        if not folder.is_relative_to(temporary) or not folder.name.startswith("shared-brand-preview-"): raise ValueError("Unsafe preview cleanup")
        shutil.rmtree(folder)
        return
    folder=Path(tempfile.mkdtemp(prefix="shared-brand-preview-",dir=temporary))
    counts=[];pids=[]
    for name,source,port in [("candidate",args.candidate,8765),("baseline",args.baseline,8766)]:
        target=folder/name
        counts.append(prepare(source,target))
        if name=="baseline" and args.approved_content: apply_approved_projects(target)
        env={key:os.environ[key] for key in ("PATH","LANG") if key in os.environ}
        process=subprocess.Popen(["php","-d","allow_url_fopen=0","-d","allow_url_include=0",
            "-d","display_errors=0","-d","log_errors=0","-d","error_reporting=-1",
            "-d","disable_functions="+DISABLED,"-S","127.0.0.1:"+str(port),"-t",str(target),str(target/"router.php")],
            cwd=target,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        pids.append(process.pid)
    state=folder/"state.json"
    state.write_text(json.dumps({"folder":str(folder),"pids":pids}),encoding="ascii")
    with open(os.environ["GITHUB_ENV"],"a",encoding="ascii") as file:
        file.write("QA_BASE_URL=http://127.0.0.1:8765\nQA_BASELINE_URL=http://127.0.0.1:8766\nQA_FIXTURE_STATE="+str(state)+"\n")
    print(json.dumps({"isolated_previews":2,"copied_files":counts,"runtime_api_config_excluded":True}))
if __name__=="__main__": main()
