"""Focused BRMP source and affected-service runtime gate; no hosting/network/config writes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public_html"
BASE_SHA = "96742610742375e39a3688555ed45dbe7ff48701"
BASE_PROJECTS_SHA256 = "b199918bff23ebd2f2dc6050ecf6b0baac8ac836728f1e45abc5c0206ebcf284"
BASE_DATA_GIT_BLOB = "fc9117952bee5cd0002d16cac077284e92b9a556"
SEO_SHA256 = "aa17e3a669679618fb3404f4623fa0c1c8cc6d353a6b47d7b986f78a6b052828"
R6_SHA256 = "0f2137981e0b5e6eea0e3ac5899266a0f59ced724090d5ad4b0b504dbddef828"
COPY = {
  "seo_title": "Jasa Huruf Timbul: Pilihan & Brief Pesanan | 3DKan",
  "seo_description": "Pahami pilihan huruf timbul, lihat dokumentasi interior BRMP, dan siapkan teks, logo, ukuran bidang serta foto lokasi sebelum meminta penawaran.",
  "detail_sections": [
    {
      "id": "brief-interior-brmp",
      "heading": "Dari dokumentasi interior ke brief pesanan",
      "paragraphs": [
        "Portofolio 3DKan mencantumkan 18 Juli 2026 pada entri identitas interior Kementerian Pertanian — BRMP. Foto memperlihatkan logo dan susunan tulisan pada backdrop ruang, dalam kondisi terpasang. Gunakan contoh ini untuk menjelaskan bagian komposisi yang menjadi acuan Anda; bahan, ukuran, dan rincian pemasangan pesanan tetap perlu dikonfirmasi tersendiri.",
        "Siapkan teks dan logo, foto bidang, lebar × tinggi bidang beserta satuan dan status ukur atau perkiraan, lokasi, jumlah titik, serta pilihan pencahayaan yang ingin dibahas. Buka galeri portofolio yang ditautkan di halaman ini untuk melihat dokumentasi BRMP dan menggunakan CTA Siapkan brief huruf timbul interior.",
        "Pilih Huruf timbul pada brief. Di Ringkasan kebutuhan, tulis ‘Referensi visual: BRMP’, teks/logo, ukuran bidang beserta satuan dan statusnya, lokasi, serta foto yang tersedia. Periksa pesan; file dan foto dilampirkan sendiri saat chat. Pesan dikirim setelah Anda menekan Kirim di WhatsApp."
      ],
      "links": []
    }
  ]
}
PARAGRAPHS = "    <p class=\"case-summary\">Foto memperlihatkan logo dan susunan tulisan pada backdrop ruang, dalam kondisi terpasang. Gunakan dokumentasi BRMP untuk menjelaskan bagian komposisi yang menjadi acuan Anda; bahan, ukuran, dan rincian pemasangan pesanan tetap perlu dikonfirmasi tersendiri.</p>\n    <p class=\"case-summary\">Pilih Huruf timbul pada brief. Di Ringkasan kebutuhan, tulis ‘Referensi visual: BRMP’, teks/logo, ukuran bidang beserta satuan dan statusnya, lokasi, serta foto yang tersedia. Periksa pesan; file dan foto dilampirkan sendiri saat chat. Pesan dikirim setelah Anda menekan Kirim di WhatsApp.</p>\n"
CTA = "<a class=\"case-cta\" href=\"#brief-proyek\">Siapkan brief huruf timbul interior</a><a class=\"case-cta\" href=\"/layanan/huruf-timbul\">Panduan brief huruf timbul</a>"
RAW_OLD = "      \"image\": \"produk-dbfee5defde1\"\n    },\n    \"neon-flex\": {"
RAW_NEW = "      \"image\": \"produk-dbfee5defde1\",\n      \"seo_title\": \"Jasa Huruf Timbul: Pilihan & Brief Pesanan | 3DKan\",\n      \"seo_description\": \"Pahami pilihan huruf timbul, lihat dokumentasi interior BRMP, dan siapkan teks, logo, ukuran bidang serta foto lokasi sebelum meminta penawaran.\",\n      \"detail_sections\": [\n        {\n          \"id\": \"brief-interior-brmp\",\n          \"heading\": \"Dari dokumentasi interior ke brief pesanan\",\n          \"paragraphs\": [\n            \"Portofolio 3DKan mencantumkan 18 Juli 2026 pada entri identitas interior Kementerian Pertanian — BRMP. Foto memperlihatkan logo dan susunan tulisan pada backdrop ruang, dalam kondisi terpasang. Gunakan contoh ini untuk menjelaskan bagian komposisi yang menjadi acuan Anda; bahan, ukuran, dan rincian pemasangan pesanan tetap perlu dikonfirmasi tersendiri.\",\n            \"Siapkan teks dan logo, foto bidang, lebar × tinggi bidang beserta satuan dan status ukur atau perkiraan, lokasi, jumlah titik, serta pilihan pencahayaan yang ingin dibahas. Buka galeri portofolio yang ditautkan di halaman ini untuk melihat dokumentasi BRMP dan menggunakan CTA Siapkan brief huruf timbul interior.\",\n            \"Pilih Huruf timbul pada brief. Di Ringkasan kebutuhan, tulis ‘Referensi visual: BRMP’, teks/logo, ukuran bidang beserta satuan dan statusnya, lokasi, serta foto yang tersedia. Periksa pesan; file dan foto dilampirkan sendiri saat chat. Pesan dikirim setelah Anda menekan Kirim di WhatsApp.\"\n          ],\n          \"links\": []\n        }\n      ]\n    },\n    \"neon-flex\": {"
PHP_RUNNER = r"""
$site=$argv[1]; $_SERVER['REQUEST_URI']=$argv[2];
$_SERVER['REQUEST_METHOD']='GET'; $_SERVER['HTTP_HOST']='www.3dkanadvertising.store';
$_SERVER['HTTPS']='on'; $_GET=[]; $_POST=[]; $_FILES=[];
error_reporting(E_ALL);
set_error_handler(function($level){ throw new ErrorException('isolated renderer diagnostic',0,$level); });
http_response_code(200); ob_start();
register_shutdown_function(function(){
 $body=ob_get_clean();
 echo json_encode(['status'=>http_response_code(),'body'=>$body],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
});
include $site.'/seo.php';
"""
FILES = ("seo.php","includes/refresh-data.json","includes/tracking-query.php",
         "includes/shared-brand.php","includes/site-brand.json","includes/refresh-brand-head.html",
         "includes/refresh-header.html","includes/refresh-footer.html","404.html")

def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def safe(relative):
    path = PUBLIC / relative
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(PUBLIC.resolve()):
        raise RuntimeError("Unsafe focused dependency")
    return path

class BrmpContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.projects = safe("projects.html").read_bytes().decode("utf-8")
        cls.raw_data = safe("includes/refresh-data.json").read_bytes().decode("utf-8")
        cls.data = json.loads(cls.raw_data)
        spec = importlib.util.spec_from_file_location("brmp_page",ROOT/"scripts/service_content_check.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.Page = module.Page
        cls.temp = tempfile.TemporaryDirectory(prefix="brmp-render-",dir=os.environ.get("RUNNER_TEMP"))
        cls.site = Path(cls.temp.name)
        cls.site.chmod(0o700)
        for relative in FILES:
            target = cls.site / relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe(relative),target)
        cls.php = shutil.which("php")
        if not cls.php:
            raise RuntimeError("Focused PHP renderer unavailable")
        probe = subprocess.run([cls.php,"-r","echo PHP_VERSION_ID;"],capture_output=True,check=True,timeout=10)
        version = int(probe.stdout)
        if probe.stderr or not 80300 <= version < 80400:
            raise RuntimeError("Exact PHP8.3 required")
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    def render(self,uri="/layanan/huruf-timbul"):
        command = [self.php,"-d","allow_url_fopen=0","-d","allow_url_include=0",
                   "-d","display_errors=stderr","-d","log_errors=0",
                   "-d","disable_functions=curl_exec,curl_multi_exec,fsockopen,pfsockopen,"
                         "stream_socket_client,stream_socket_server,mail,exec,shell_exec,"
                         "system,passthru,popen,proc_open",
                   "-r",PHP_RUNNER,str(self.site),uri]
        completed = subprocess.run(command,capture_output=True,timeout=10)
        self.assertEqual(completed.returncode,0,"Focused PHP runtime failed")
        self.assertEqual(completed.stderr,b"","Focused PHP emitted diagnostic")
        return json.loads(completed.stdout.decode("utf-8"))
    def test_01_exact_projects_delta_preserves_entire_other_document(self):
        self.assertEqual(self.projects.count(PARAGRAPHS),1)
        self.assertEqual(self.projects.count(CTA),1)
        restored = self.projects.replace(PARAGRAPHS,"",1).replace(CTA,"",1)
        self.assertEqual(hashlib.sha256(restored.encode("utf-8")).hexdigest(),BASE_PROJECTS_SHA256)
        page = self.Page(self.projects)
        cards = [n for n in page.root.nodes("article") if n.attrs.get("id") == "brmp"]
        self.assertEqual(len(cards),1)
        card = cards[0]
        self.assertEqual([n.attrs.get("href") for n in card.nodes("a")][:2],
                         ["#brief-proyek","/layanan/huruf-timbul"])
        self.assertEqual(len([n for n in page.root.nodes() if n.attrs.get("id") == "brief-proyek"]),1)
    def test_02_exact_data_delta_preserves_legacy_and_six_other_services(self):
        self.assertEqual(self.raw_data.count(RAW_NEW),1)
        restored = self.raw_data.replace(RAW_NEW,RAW_OLD,1)
        self.assertEqual(blob(restored.encode("utf-8")),BASE_DATA_GIT_BLOB)
        old = json.loads(restored)
        self.assertEqual(set(old),set(self.data))
        self.assertEqual(set(old["services"]),set(self.data["services"]))
        for key in old:
            if key != "services": self.assertEqual(old[key],self.data[key])
        for slug,record in old["services"].items():
            if slug != "huruf-timbul": self.assertEqual(record,self.data["services"][slug])
            else:
                self.assertEqual(len(record),7)
                for key,value in record.items(): self.assertEqual(value,self.data["services"][slug][key])
                self.assertEqual({key:value for key,value in self.data["services"][slug].items() if key not in record},COPY)
    def test_03_unchanged_php_binding_controller_and_photo(self):
        self.assertEqual(hashlib.sha256(safe("seo.php").read_bytes()).hexdigest(),SEO_SHA256)
        self.assertEqual(hashlib.sha256(safe("assets/ui/frontend.js").read_bytes()).hexdigest(),R6_SHA256)
        photo = safe("assets/portfolio-real/clean/kementerian-pertanian-brmp.webp").read_bytes()
        self.assertEqual(len(photo),448556)
        self.assertEqual(hashlib.sha256(photo).hexdigest(),"c8aae945cbf20531214c6dc7f280dcd467a8c75ee2f5b5f88660b89f8abfe162")
        self.assertFalse((self.site/"api.php").exists())
        self.assertFalse((self.site/"includes/config.php").exists())
    def test_04_actual_service_metadata_heading_and_section(self):
        response = self.render()
        self.assertEqual(response["status"],200)
        page = self.Page(response["body"])
        head = page.root.nodes("head")[0]
        main = page.root.nodes("main")[0]
        self.assertEqual([n.text() for n in head.nodes("title")],[COPY["seo_title"]])
        self.assertEqual([n.attrs.get("content") for n in head.nodes("meta") if n.attrs.get("name")=="description"],
                         [COPY["seo_description"]])
        self.assertEqual([n.text() for n in main.nodes("h1")],["Huruf Timbul. Dibuat sesuai kebutuhan Anda."])
        detail = COPY["detail_sections"][0]
        sections = [n for n in main.nodes("section") if n.attrs.get("id")=="service-detail-"+detail["id"]]
        self.assertEqual(len(sections),1)
        self.assertEqual([n.text() for n in sections[0].nodes("h2")],[detail["heading"]])
        self.assertEqual([n.text() for n in sections[0].nodes("p")],detail["paragraphs"])
        self.assertEqual(sections[0].nodes("a"),[])
    def test_05_actual_canonical_and_schema_without_new_claims(self):
        page = self.Page(self.render()["body"])
        head = page.root.nodes("head")[0]
        canonical = "https://www.3dkanadvertising.store/layanan/huruf-timbul"
        self.assertEqual([n.attrs.get("href") for n in head.nodes("link") if n.attrs.get("rel")=="canonical"],[canonical])
        graphs = [json.loads(n.text()) for n in head.nodes("script") if n.attrs.get("type")=="application/ld+json"]
        self.assertEqual(len(graphs),1)
        service = [n for n in graphs[0] if n.get("@type")=="Service"]
        self.assertEqual(len(service),1)
        self.assertEqual(service[0]["url"],canonical)
        self.assertEqual(service[0]["description"],COPY["seo_description"])
        self.assertFalse(any(n.get("@type") in {"Offer","AggregateRating","Review","VideoObject"} for n in graphs[0]))
    def test_06_existing_legacy_city_redirect_survives_data_extension(self):
        self.assertEqual(self.render("/layanan/huruf-timbul/makassar"),{"status":301,"body":""})

if __name__ == "__main__":
    unittest.main(verbosity=2)
