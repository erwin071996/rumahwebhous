"""Read-only semantic checks for committed service copy; no transport or publisher."""
from html.parser import HTMLParser
import json

class Node:
    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []
    def text(self):
        return "".join(c.text() if isinstance(c, Node) else c for c in self.children)
    def nodes(self, tag=None):
        out = [self] if tag is None or self.tag == tag else []
        for child in self.children:
            if isinstance(child, Node): out.extend(child.nodes(tag))
        return out

class Page(HTMLParser):
    VOID = {"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root, self.stack = Node("document"), []
        self.stack.append(self.root)
        self.feed(text); self.close()
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID: self.stack.append(node)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID: self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break
    def handle_data(self, data):
        self.stack[-1].children.append(data)

def require(condition, category):
    if not condition:
        raise RuntimeError("Reviewed service HTTP check failed: " + category)

def verify_service_content(raw, record, *, domain, slug):
    require(isinstance(raw, bytes) and isinstance(record, dict), "input type")
    try:
        page = Page(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as error:
        raise RuntimeError("Reviewed service HTTP check failed: response decoding") from error
    roots = page.root.nodes()
    heads, mains = page.root.nodes("head"), page.root.nodes("main")
    require(len(heads) == len(mains) == 1, "head/main")
    head, main = heads[0], mains[0]
    title, description, heading = (record.get(k) for k in ("seo_title","seo_description","detail_heading"))
    details = record.get("detail_sections")
    require(all(isinstance(v, str) and v for v in (title,description,heading))
            and isinstance(details, list) and len(details) == 3, "expected fields")
    canonical = domain + "/layanan/" + slug
    require([n.text() for n in head.nodes("title")] == [title], "title")
    require([n.text() for n in main.nodes("h1")] == [heading], "H1")
    require([n.attrs.get("href") for n in head.nodes("link") if n.attrs.get("rel") == "canonical"] == [canonical], "canonical")
    for attr, name, expected in [
        ("name","description",description), ("name","robots","index,follow,max-image-preview:large"),
        ("property","og:title",title), ("property","og:description",description), ("property","og:url",canonical)]:
        require([n.attrs.get("content") for n in head.nodes("meta") if n.attrs.get(attr) == name] == [expected], "metadata")
    all_ids = [n.attrs["id"] for n in roots if "id" in n.attrs]
    require(len(all_ids) == len(set(all_ids)), "duplicate IDs")
    for detail in details:
        require(isinstance(detail, dict) and all(k in detail for k in ("id","heading","paragraphs","links")), "expected section")
        sid, hid = "service-detail-" + detail["id"], "service-heading-" + detail["id"]
        sections = [n for n in main.nodes("section") if n.attrs.get("id") == sid]
        require(len(sections) == 1 and sections[0].attrs.get("aria-labelledby") == hid, "section identity")
        section = sections[0]
        h2s = section.nodes("h2")
        require(len(h2s) == 1 and h2s[0].attrs.get("id") == hid and h2s[0].text() == detail["heading"], "section heading")
        require([n.text() for n in section.nodes("p")] == detail["paragraphs"], "section paragraphs")
        require([(n.attrs.get("href"), n.text()) for n in section.nodes("a")] ==
                [(n["href"], n["label"]) for n in detail["links"]], "section links")
    try:
        graphs = [json.loads(n.text()) for n in head.nodes("script") if n.attrs.get("type") == "application/ld+json"]
    except (ValueError, TypeError) as error:
        raise RuntimeError("Reviewed service HTTP check failed: schema JSON") from error
    require(len(graphs) == 1 and isinstance(graphs[0], list), "schema envelope")
    services = [n for n in graphs[0] if isinstance(n,dict) and n.get("@type") == "Service"]
    crumbs = [n for n in graphs[0] if isinstance(n,dict) and n.get("@type") == "BreadcrumbList"]
    require(len(services) == len(crumbs) == 1, "schema duplicates")
    svc = services[0]
    require(svc.get("name") == record["name"] and svc.get("serviceType") == record["name"]
            and svc.get("description") == description and svc.get("url") == canonical
            and svc.get("provider") == {"@id":domain+"/#organization"}
            and svc.get("areaServed") == {"@type":"AdministrativeArea","name":"Sulawesi Selatan"}, "Service schema")
    require(crumbs[0].get("itemListElement") == [
        {"@type":"ListItem","position":1,"name":"Beranda","item":domain+"/"},
        {"@type":"ListItem","position":2,"name":record["name"],"item":canonical}], "Breadcrumb schema")
    return {"path":"/layanan/"+slug,"sections":3,"rendered_content":"verified"}
